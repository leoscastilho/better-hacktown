#!/usr/bin/env python3
"""
HackTown multi-year event sync — dispatcher.

Reads config/years.json and, for each target year, picks that year's PROVIDER
(how to fetch its schedule) and runs it through the shared core (sync_common),
so every year is saved identically under events/<year>/.

    scrape_hacktown.py            (this dispatcher)
      ├── sync_common.py          shared output format / writers / locations
      ├── provider_yazo.py        2025 — Yazo API, paginated per day
      └── provider_supabase.py    2026 — Supabase/PostgREST, one request

Each year entry in config/years.json declares a `provider` ("yazo" | "supabase")
and an `api` block with the connection details that provider needs.

Usage:
    python scrape_hacktown.py                 # sync activeYear (default)
    python scrape_hacktown.py --year 2026     # sync a specific year
    python scrape_hacktown.py --all-years     # sync every configured year

The year may also be supplied via the HACKTOWN_YEAR environment variable.

License: MIT
"""

import argparse
import inspect
import json
import logging
import os
import sys
import time

import sync_common

# ============================================================================
# CONFIGURATION
# ============================================================================

# Central multi-year registry, shared with the web app (index.html).
YEARS_CONFIG_FILE = os.path.join("config", "years.json")

# Base directory holding one sub-directory of scraped data per year.
EVENTS_BASE_DIR = "events"

# ---------------------------------------------------------------------------
# Safety guard against a tampered/broken feed wiping data. If more than
# GUARD_MAX_REMOVED_FRACTION of the currently-active events vanish in a single
# run (and there were at least GUARD_MIN_EVENTS to begin with), the sync refuses
# to soft-delete that many at once: it writes nothing and exits non-zero. Pass
# --force (or HACKTOWN_FORCE=1) to push a legitimately large change through.
# Both thresholds are env-overridable.
# ---------------------------------------------------------------------------
GUARD_MIN_EVENTS = int(os.environ.get("HACKTOWN_GUARD_MIN_EVENTS", "20"))
GUARD_MAX_REMOVED_FRACTION = float(os.environ.get("HACKTOWN_GUARD_MAX_REMOVED", "0.30"))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================================
# REGISTRY + PROVIDER RESOLUTION
# ============================================================================

def load_years_registry():
    """Load and return the multi-year registry from config/years.json."""
    try:
        with open(YEARS_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"❌ Years registry {YEARS_CONFIG_FILE} not found!")
        raise
    except Exception as e:
        logger.error(f"❌ Error loading years registry {YEARS_CONFIG_FILE}: {e}")
        raise


def year_is_scrapeable(year_cfg):
    """
    A year can be synced only if it is enabled and has both an API endpoint and
    event dates configured. Returns (bool, reason_if_not).
    """
    if not year_cfg.get("enabled", False):
        return False, "not enabled"
    if not year_cfg.get("api", {}).get("base_url"):
        return False, "no API base_url configured"
    if not year_cfg.get("dates"):
        return False, "no event dates configured"
    return True, ""


def resolve_target_years(registry, requested_year=None, all_years=False):
    """
    Decide which year(s) to sync:
    - all_years=True  -> every year defined in the registry (filtered later)
    - requested_year  -> just that year
    - otherwise       -> the registry's activeYear (default behaviour)
    """
    years = registry.get("years", {})
    if all_years:
        return list(years.keys())
    if requested_year:
        return [str(requested_year)]
    active = registry.get("activeYear")
    if not active:
        raise ValueError(f"No 'activeYear' set in {YEARS_CONFIG_FILE} and no --year provided")
    return [str(active)]


def select_provider(name):
    """Import and return the provider module for a given provider name."""
    if name == "supabase":
        import provider_supabase
        return provider_supabase
    if name in ("yazo", "", None):
        import provider_yazo
        return provider_yazo
    raise ValueError(f"Unknown provider '{name}' in {YEARS_CONFIG_FILE}")


def build_year_context(year, registry):
    """Resolve everything needed to sync one year into a context dict."""
    years = registry.get("years", {})
    if year not in years:
        raise ValueError(f"Year '{year}' is not defined in {YEARS_CONFIG_FILE}")
    cfg = years[year]
    provider_name = cfg.get("provider", "yazo")
    return {
        "year": str(year),
        "output_dir": os.path.join(EVENTS_BASE_DIR, str(year)),
        "locations_config_file": os.path.join("config", str(year), "locations_config.json"),
        "id_map_file": os.path.join(EVENTS_BASE_DIR, str(year), "id_map.json"),
        "updates_file": os.path.join(EVENTS_BASE_DIR, str(year), "updates.json"),
        "dates": [d["date"] for d in cfg.get("dates", []) if d.get("date")],
        "provider_name": provider_name,
        "provider": select_provider(provider_name),
        "api_config": cfg.get("api", {}),
    }


# ============================================================================
# ORCHESTRATION (shared across all providers)
# ============================================================================

async def run_year(ctx, force=False):
    """
    Sync a single, resolved year: load its locations, fetch via its provider,
    then write events/filters/locations/summary through the shared core.
    Returns True on success, False if it failed or was blocked by the guard.
    """
    year = ctx["year"]
    dates = ctx["dates"]
    provider = ctx["provider"]

    logger.info("=" * 60)
    logger.info(f"🚀 Syncing HackTown {year}  (provider: {ctx['provider_name']})")
    logger.info("=" * 60)
    logger.info(f"Dates: {', '.join(dates)}")
    logger.info(f"Output: {os.path.abspath(ctx['output_dir'])}")

    # Shared core: point writers at this year + load its location config.
    sync_common.configure(ctx["output_dir"], ctx["locations_config_file"])
    sync_common.load_location_config()
    sync_common.generate_locations_json()

    # Provider: fetch the raw/canonical events (async for yazo, sync for supabase).
    provider.configure(ctx["api_config"])
    start = time.time()
    result = provider.fetch(dates)
    if inspect.isawaitable(result):
        result = await result
    all_events = result or {}

    total_events = 0
    successful_dates = 0
    aborted = False

    if getattr(provider, "REMAP_IDS", False):
        total_events, successful_dates, wrote_anything, aborted = _write_remapped(ctx, all_events, force)
    else:
        total_events, successful_dates, wrote_anything = _write_plain(ctx, all_events)

    if aborted:
        # Safety guard tripped: nothing was written. Fail loudly so the run is
        # visible and the daily Action does not commit a suspicious change.
        logger.error("=" * 60)
        logger.error(f"🛑 {year}: sync ABORTED by safety guard — no files touched.")
        logger.error("=" * 60)
        return False

    elapsed = time.time() - start
    # On success every configured date now has a file, so nothing "failed".
    failed_dates = [] if successful_dates > 0 else list(dates)
    summary_path = os.path.join(ctx["output_dir"], "summary.json")
    if wrote_anything or not os.path.exists(summary_path):
        ok = sync_common.save_summary(
            year, dates, all_events, total_events, successful_dates, failed_dates, elapsed
        )
    else:
        # Nothing changed at all — leave summary (and its timestamp) untouched
        # so a no-op sync produces zero git changes.
        logger.info("↔️  nothing changed — summary left untouched")
        ok = successful_dates > 0

    logger.info("=" * 60)
    logger.info(f"🏁 {year}: {total_events} events across {successful_dates}/{len(dates)} days in {elapsed:.1f}s")
    logger.info("✅ Status: SUCCESS" if ok else "❌ Status: FAILED")
    logger.info("=" * 60)
    return ok


def _write_remapped(ctx, all_events, force=False):
    """
    Write path for sources with long/unstable natural ids (e.g. 2026/Supabase):
    map ids to stable integers, guard against a mass wipe, soft-delete anything
    that vanished, and rewrite ONLY the day files that changed. Returns
    (total_events, successful_dates, wrote_anything, aborted).
    """
    dates = ctx["dates"]
    output_dir = ctx["output_dir"]

    # Add location fields first so they're part of each event's content hash.
    for _d, evs in all_events.items():
        sync_common.add_location_fields(evs)

    # Assign stable ids + detect changes (removals not applied yet).
    id_map = sync_common.load_id_map(ctx["id_map_file"])
    recon = sync_common.reconcile_events(all_events, id_map)
    active_before = recon["active_before"]
    vanished = recon["vanished"]
    frac = (len(vanished) / active_before) if active_before else 0.0
    logger.info(
        f"🔢 id map: {len(id_map['events'])} known, next id {id_map['next_id']}; "
        f"+{recon['new']} new, ~{recon['changed']} changed, ↩{recon['reactivated']} reactivated, "
        f"−{len(vanished)} vanished ({frac:.0%} of {active_before} active)"
    )

    # ---- SAFETY GUARD: refuse to soft-delete a suspicious fraction at once ----
    if active_before >= GUARD_MIN_EVENTS and frac > GUARD_MAX_REMOVED_FRACTION and not force:
        logger.error(
            f"🛑 SAFETY GUARD: {len(vanished)}/{active_before} active events "
            f"({frac:.0%}) disappeared from the feed in a single run — over the "
            f"{GUARD_MAX_REMOVED_FRACTION:.0%} limit. Refusing to remove that many "
            f"at once; nothing was written. If this change is real, re-run with "
            f"--force (or set HACKTOWN_FORCE=1)."
        )
        return 0, 0, False, True

    # Guard passed → soft-delete the vanished events, then persist the map.
    changed = recon["changed_dates"]
    removal_updates = sync_common.apply_removals(id_map, vanished, changed)
    sync_common.save_id_map(ctx["id_map_file"], id_map)

    # Update the per-year change tracker that feeds the frontend notifications:
    # append the new changes (cancelled / place / time) and drop the stale
    # "cancelled" notices of any event that came back.
    tracked = recon["updates"] + removal_updates
    added, purged = sync_common.update_change_log(
        ctx["updates_file"], tracked, recon["reactivated_ids"]
    )
    if added or purged:
        by_kind = {}
        for u in tracked:
            by_kind[u["change"]] = by_kind.get(u["change"], 0) + 1
        parts = [f"{k}={v}" for k, v in sorted(by_kind.items())]
        if purged:
            parts.append(f"cancelamentos removidos={purged}")
        logger.info("🔔 tracked changes: " + ", ".join(parts))

    total_events = 0
    successful_dates = 0
    wrote_anything = False
    for date in dates:
        active = all_events.get(date) or []
        if active:
            total_events += len(active)
            successful_dates += 1
        path = os.path.join(output_dir, f"hacktown_events_{date}.json")
        if date in changed or not os.path.exists(path):
            # Preserve soft-removed events for this day (flagged removed:true),
            # then write in a deterministic (chronological, id tie-break) order so
            # identical data always yields byte-identical files.
            removed = sync_common.carried_removed_for_date(date, id_map)
            merged = sorted(active + removed, key=lambda e: (e.get("start_time") or "", e.get("id")))
            sync_common.save_events_to_file(date, merged)
            wrote_anything = True
            note = f" (+{len(removed)} removed kept)" if removed else ""
            logger.info(f"✅ {date}: {len(active)} events written{note}")
        else:
            logger.info(f"↔️  {date}: unchanged — kept existing file")

    # Any missing filter file forces a regeneration — otherwise adding a new
    # one (e.g. filter_tracks.json) would never be written on a quiet sync.
    filters_missing = not all(
        os.path.exists(os.path.join(output_dir, name))
        for name in ("filter_locations.json", "filter_speakers.json", "filter_tracks.json")
    )
    if changed or filters_missing:
        # Filters + counts reflect ACTIVE events only (all_events = current fetch).
        sync_common.save_filter_data({d: all_events.get(d, []) for d in dates})
        wrote_anything = True
    else:
        logger.info("↔️  filters unchanged — kept existing files")

    return total_events, successful_dates, wrote_anything, False


def _write_plain(ctx, all_events):
    """
    Write path for sources that already carry stable ids (e.g. 2025/yazo):
    write every configured date, with empty files for legitimately-empty days on
    a successful fetch. Returns (total_events, successful_dates, wrote_anything).
    """
    dates = ctx["dates"]
    total_events = 0
    successful_dates = 0
    empty_dates = []
    for date in dates:
        events = all_events.get(date) or []
        if events:
            sync_common.save_events_to_file(date, events)
            total_events += len(events)
            successful_dates += 1
            logger.info(f"✅ {date}: {len(events)} events saved")
        else:
            empty_dates.append(date)

    if successful_dates > 0:
        for date in empty_dates:
            sync_common.save_events_to_file(date, [])
            logger.info(f"📭 {date}: no events yet — wrote empty file")
        sync_common.save_filter_data({d: all_events.get(d, []) for d in dates})

    return total_events, successful_dates, successful_dates > 0


async def main():
    """Parse CLI args, load the registry, and sync the requested year(s)."""
    parser = argparse.ArgumentParser(description="HackTown multi-year event sync")
    parser.add_argument(
        "--year", dest="year", default=os.environ.get("HACKTOWN_YEAR"),
        help="Year to sync (e.g. 2026). Defaults to activeYear in config/years.json "
             "(or the HACKTOWN_YEAR environment variable if set)."
    )
    parser.add_argument(
        "--all-years", dest="all_years", action="store_true",
        help="Sync every scrapeable year defined in config/years.json."
    )
    parser.add_argument(
        "--force", dest="force", action="store_true",
        default=os.environ.get("HACKTOWN_FORCE", "").lower() in ("1", "true", "yes"),
        help="Bypass the mass-removal safety guard for a legitimately large change."
    )
    args = parser.parse_args()

    registry = load_years_registry()
    defined_years = registry.get("years", {})
    target_years = resolve_target_years(
        registry, requested_year=args.year, all_years=args.all_years
    )

    logger.info("=" * 60)
    logger.info("🗂️  HackTown multi-year sync")
    logger.info(f"   Registry: {YEARS_CONFIG_FILE}")
    logger.info(f"   Active year (default): {registry.get('activeYear')}")
    logger.info(f"   Target year(s): {', '.join(target_years)}")
    logger.info("=" * 60)

    explicit_single = bool(args.year) and not args.all_years
    scraped_any = False
    overall_success = False

    for year in target_years:
        if year not in defined_years:
            msg = f"Year '{year}' is not defined in {YEARS_CONFIG_FILE}"
            if explicit_single:
                logger.error(f"❌ {msg}")
                sys.exit(1)
            logger.warning(f"⏭️  Skipping: {msg}")
            continue

        scrapeable, reason = year_is_scrapeable(defined_years[year])
        if not scrapeable:
            msg = f"Year '{year}' is not scrapeable ({reason})"
            if explicit_single:
                logger.error(
                    f"❌ {msg}. Fill in its 'dates' and 'api' in {YEARS_CONFIG_FILE} "
                    f"and set 'enabled': true."
                )
                sys.exit(1)
            logger.warning(f"⏭️  Skipping: {msg}")
            continue

        ctx = build_year_context(year, registry)
        scraped_any = True
        year_ok = await run_year(ctx, force=args.force)
        overall_success = overall_success or year_ok

    if not scraped_any:
        logger.error(f"❌ No scrapeable years were processed. Check {YEARS_CONFIG_FILE}.")
        sys.exit(1)

    if not overall_success:
        sys.exit(1)


# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Sync interrupted by user (Ctrl+C)")
        print("📝 Partial results may have been saved to the events/ directory")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error occurred: {e}")
        print("🔧 Check the logs above for detailed error information")
        sys.exit(1)
