#!/usr/bin/env python3
"""
Shared core for the HackTown multi-year sync tools.

This module owns everything that is IDENTICAL across years: the on-disk output
format (events/<year>/…), location normalization, filter-file generation and
the summary. Per-year "providers" (provider_yazo, provider_supabase) only fetch
their API and hand back event dicts in the canonical shape; this module writes
them out so every year is saved the same way.

Canonical event (the fields the web app reads):
    id, start_time, end_time, title, description, place, speakers[], tags[]
`filterLocation` / `nearLocation` are added here (from place) via the year's
config/<year>/locations_config.json — providers do NOT compute them.

License: MIT
"""

import hashlib
import json
import os
import logging
from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# ============================================================================
# PER-RUN STATE (set by configure() before a year is processed)
# ============================================================================
OUTPUT_DIR = "events"
LOCATIONS_CONFIG_FILE = os.path.join("config", "locations_config.json")

# Location normalization state
location_cache: Dict[str, tuple] = {}
location_mappings: Dict[str, Any] = {}
unmapped_locations: set = set()


def configure(output_dir: str, locations_config_file: str) -> None:
    """Point the shared writers at a specific year's output dir + location config."""
    global OUTPUT_DIR, LOCATIONS_CONFIG_FILE
    OUTPUT_DIR = output_dir
    LOCATIONS_CONFIG_FILE = locations_config_file
    location_cache.clear()
    location_mappings.clear()
    unmapped_locations.clear()


def brt_now_iso() -> str:
    """Current time in America/Sao_Paulo as an ISO 8601 string."""
    return datetime.now(ZoneInfo('UTC')).astimezone(ZoneInfo('America/Sao_Paulo')).isoformat()


# ============================================================================
# LOCATION NORMALIZATION
# ============================================================================

def load_location_config() -> None:
    """Load config/<year>/locations_config.json into location_mappings."""
    global location_mappings
    try:
        with open(LOCATIONS_CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            location_mappings = config.get('location_mappings', {})
            logger.info(f"✅ Loaded {len(location_mappings)} location mappings from {LOCATIONS_CONFIG_FILE}")
    except FileNotFoundError:
        logger.error(f"❌ Location config file {LOCATIONS_CONFIG_FILE} not found!")
        logger.error(f"Please create {LOCATIONS_CONFIG_FILE} with location mappings")
        location_mappings = {}
    except Exception as e:
        logger.error(f"❌ Error loading location config: {e}")
        location_mappings = {}


def generate_locations_json() -> None:
    """Generate events/<year>/locations.json (venue → gmaps) from the config."""
    locations_data = []
    seen_locations = set()

    for key, config in location_mappings.items():
        filter_location = config.get('filter_location', key)
        gmaps = config.get('gmaps', '')
        if filter_location not in seen_locations:
            locations_data.append({"name": filter_location, "gmaps": gmaps})
            seen_locations.add(filter_location)

    if "Other" not in seen_locations:
        locations_data.append({"name": "Other", "gmaps": ""})

    locations_data.sort(key=lambda x: x['name'])

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    locations_file = os.path.join(OUTPUT_DIR, "locations.json")
    with open(locations_file, 'w', encoding='utf-8') as f:
        json.dump(locations_data, f, ensure_ascii=False, indent=2)
    logger.info(f"📍 Generated {locations_file} with {len(locations_data)} locations")


def normalize_and_locate(place: str) -> tuple:
    """
    Map a raw venue string to (filter_location, near_location) using the loaded
    config. Substring, case-insensitive match on each mapping's possible_names.
    Unmapped places keep their original name and near_location=None.
    """
    if not place:
        return "Other", "Other"

    if place in location_cache:
        return location_cache[place]

    place_upper = place.upper()
    filter_location = "Other"
    near_location = "Other"

    for location_key, config in location_mappings.items():
        possible_names = config.get('possible_names', [])
        for possible_name in possible_names:
            if possible_name.upper() in place_upper:
                filter_location = config.get('filter_location', location_key)
                near_location = config.get('near_location', 'Other')
                break
        if filter_location != "Other":
            break
    else:
        # Unmapped: preserve original name, flag for later mapping.
        filter_location = place
        near_location = None
        unmapped_locations.add(place)

    result = (filter_location, near_location)
    location_cache[place] = result
    return result


def add_location_fields(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add filterLocation / nearLocation to each event based on its `place`."""
    for event in events:
        filter_location, near_location = normalize_and_locate(event.get('place', ''))
        event['filterLocation'] = filter_location
        event['nearLocation'] = near_location
    return events


# ============================================================================
# OUTPUT WRITERS
# ============================================================================

def save_events_to_file(date: str, events: List[Dict[str, Any]]) -> None:
    """Write events/<year>/hacktown_events_<date>.json (adds location fields)."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    processed_events = add_location_fields(events)

    filepath = os.path.join(OUTPUT_DIR, f"hacktown_events_{date}.json")
    output_data = {
        "date": date,
        # Count active events only; soft-removed ones are carried for the record.
        "total_events": sum(1 for e in processed_events if not e.get("removed")),
        "scraped_at": brt_now_iso(),
        "events": processed_events,
    }
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    logger.info(f"Successfully saved {len(processed_events)} events to {filepath}")
    logger.info(f"File size: {os.path.getsize(filepath):,} bytes")


def extract_unique_filter_locations(all_events_data: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """Sorted unique filterLocation values across all dates."""
    unique_locations = set()
    for _date, events in all_events_data.items():
        for event in (events or []):
            fl = event.get('filterLocation', '')
            if fl and fl.strip():
                unique_locations.add(fl.strip())
    return sorted(unique_locations)


def extract_unique_speakers(all_events_data: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """Sorted unique speaker names across all dates (from speakers[].name)."""
    unique_speakers = set()
    for _date, events in all_events_data.items():
        for event in (events or []):
            speakers_data = event.get('speakers', [])
            if isinstance(speakers_data, list):
                for speaker in speakers_data:
                    if isinstance(speaker, dict):
                        name = speaker.get('name', '')
                        if name and isinstance(name, str) and name.strip():
                            unique_speakers.add(name.strip())

    common_words = {'tbd', 'tba', 'a definir', 'em breve', 'soon', 'coming', 'undefined', 'null', 'none', ''}
    cleaned = {s for s in unique_speakers if len(s) > 2 and s.lower() not in common_words}
    result = sorted(cleaned)
    logger.info(f"🎤 Extracted {len(result)} unique speaker names")
    return result


def save_filter_data(all_events_data: Dict[str, List[Dict[str, Any]]]) -> None:
    """Write filter_locations.json + filter_speakers.json for the dropdowns."""
    logger.info("🔍 Extracting unique values for filter dropdowns...")
    unique_locations = extract_unique_filter_locations(all_events_data)
    unique_speakers = extract_unique_speakers(all_events_data)
    generated_at = brt_now_iso()

    locations_file = os.path.join(OUTPUT_DIR, "filter_locations.json")
    with open(locations_file, 'w', encoding='utf-8') as f:
        json.dump({
            "generated_at": generated_at,
            "total_locations": len(unique_locations),
            "locations": unique_locations,
        }, f, ensure_ascii=False, indent=2)
    logger.info(f"📍 Saved {len(unique_locations)} filter locations to {locations_file}")

    speakers_file = os.path.join(OUTPUT_DIR, "filter_speakers.json")
    with open(speakers_file, 'w', encoding='utf-8') as f:
        json.dump({
            "generated_at": generated_at,
            "total_speakers": len(unique_speakers),
            "speakers": unique_speakers,
        }, f, ensure_ascii=False, indent=2)
    logger.info(f"🎤 Saved {len(unique_speakers)} filter speakers to {speakers_file}")


def save_summary(year: str, dates: List[str], all_events: Dict[str, List[Dict[str, Any]]],
                 total_events: int, successful_dates: int, failed_dates: List[str],
                 elapsed_time: float) -> bool:
    """
    Write events/<year>/summary.json. On total failure, preserve the previous
    summary and record the failed attempt. Returns True if any date succeeded.
    """
    summary_file = os.path.join(OUTPUT_DIR, "summary.json")
    existing_summary = {}
    if os.path.exists(summary_file):
        try:
            with open(summary_file, 'r', encoding='utf-8') as f:
                existing_summary = json.load(f)
        except Exception as e:
            logger.warning(f"⚠️  Could not load existing summary: {e}")

    now_iso = brt_now_iso()
    fetch_successful = successful_dates > 0

    if fetch_successful:
        summary_data = {
            "scraping_completed": now_iso,
            "total_events": total_events,
            "successful_dates": successful_dates,
            "failed_dates": failed_dates,
            "dates_processed": dates,
            "files_created": [f"hacktown_events_{d}.json" for d in dates if d not in failed_dates],
            "filter_files_created": ["filter_locations.json", "filter_speakers.json"],
            "scraping_time_seconds": round(elapsed_time, 2),
            "events_per_second": round(total_events / elapsed_time, 2) if elapsed_time > 0 else 0,
            "location_cache_size": len(location_cache),
            "location_mappings_loaded": len(location_mappings),
            "unmapped_locations": sorted(list(unmapped_locations)),
        }
    else:
        summary_data = {
            "scraping_completed": existing_summary.get("scraping_completed", "Never"),
            "total_events": existing_summary.get("total_events", 0),
            "successful_dates": existing_summary.get("successful_dates", 0),
            "failed_dates": failed_dates,
            "dates_processed": dates,
            "files_created": existing_summary.get("files_created", []),
            "scraping_time_seconds": round(elapsed_time, 2),
            "last_failed_attempt": now_iso,
            "consecutive_failures": existing_summary.get("consecutive_failures", 0) + 1,
            "unmapped_locations": existing_summary.get("unmapped_locations", []),
        }
        logger.error("❌ Scraping failed completely - preserving existing summary data")

    try:
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)
        logger.info(f"📋 Summary saved to: {summary_file}")
    except Exception as e:
        logger.error(f"❌ Failed to save summary file: {e}")

    if unmapped_locations:
        logger.warning(f"⚠️  Unmapped locations ({len(unmapped_locations)}): {', '.join(sorted(unmapped_locations))}")
        logger.info(f"💡 Add them to {LOCATIONS_CONFIG_FILE} via: python add_location.py --year {year}")

    return fetch_successful


# ============================================================================
# STABLE INTEGER IDs (for sources whose natural id is long, e.g. a UUID)
# ============================================================================
# Some sources (2026 / Supabase) key events by UUID. UUIDs bloat the favorites
# stored in localStorage and the share URLs built from them, so we map each
# natural key to a small, STABLE integer id that never changes once assigned.
# The map is persisted per year (committed) so ids survive re-syncs and CI runs.
# We also store a content hash per event so we know which days actually changed
# and can leave the rest untouched (no needless rewrites / commits).
#
# Map shape:
#   { "next_id": N,
#     "events": { "<key>": {"id": int, "hash": str, "date": str, "removed_at": str|null} } }
#
# SOFT DELETE: an event that stops appearing in the feed is NEVER deleted from
# the map or the data. Its record keeps its id forever and gets a `removed_at`
# timestamp; its last-known object is carried forward in the day file flagged
# `removed: true`. The frontend hides removed events. If it reappears, it is
# reactivated (removed_at cleared) with fresh data. Mass disappearances are
# caught upstream by the dispatcher's safety guard (see scrape_hacktown.py).

def event_content_hash(event: Dict[str, Any]) -> str:
    """
    Short, stable hash of an event's content. Excludes 'id' (a derived, remapped
    value) and 'removed' (a local soft-delete flag, not source content) so those
    never spuriously mark an event as changed.
    """
    content = {k: v for k, v in event.items() if k not in ("id", "removed")}
    blob = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def load_id_map(path: str) -> Dict[str, Any]:
    """Load the natural-key → {id,hash,date,removed_at} map (or a fresh one)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, ValueError):
        data = {}
    data.setdefault("next_id", 1)
    data.setdefault("events", {})
    return data


def save_id_map(path: str, id_map: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(id_map, f, ensure_ascii=False, indent=2)


# ============================================================================
# EVENT CHANGE TRACKER (events/<year>/updates.json)
# ============================================================================
# An append-only log of the changes that matter to an attendee, so the frontend
# can surface them as notifications:
#   • "removed" — the event was cancelled (vanished from the feed)
#   • "place"   — the venue changed
#   • "time"    — start_time and/or end_time changed
# Nothing else is tracked (title/description edits are noise here), and a
# cancel → re-enable cycle is deliberately NOT logged as a change.
#
# Baselines live in the id map (place/start_time/end_time per event), so a
# change is detected by comparing the incoming event against the last synced
# values. Entries are only persisted after the safety guard approves a run.

# Keep the log bounded so it can't grow without limit across a long season.
MAX_UPDATE_ENTRIES = 2000


def clean_place(value: Any) -> str:
    """
    Normalize a venue value for comparison/display. Guards against placeholder
    junk ever reaching a notification as a literal "None"/"null" string.
    """
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in ("none", "null", "undefined") else text


def snapshot_tracked_fields(rec: Dict[str, Any], event: Dict[str, Any]) -> None:
    """Store the current tracked values on the id-map record (the next baseline)."""
    rec["place"] = clean_place(event.get("place"))
    rec["start_time"] = event.get("start_time")
    rec["end_time"] = event.get("end_time")
    rec["title"] = event.get("title") or ""


def detect_tracked_changes(rec: Dict[str, Any], event: Dict[str, Any], now: str) -> List[Dict[str, Any]]:
    """
    Compare an incoming event against its id-map baseline and return tracker
    entries for the changes we care about (place / time).

    Records written before this feature existed carry no baseline; those are
    seeded silently (no entries) so the first run after deploy doesn't report
    every event as changed.
    """
    if "place" not in rec:      # no baseline yet → seed only
        return []

    entries = []
    base = {
        "id": rec["id"],
        # Day the event now sits on, so a notification can deep-link to it.
        "date": (event.get("start_time") or "")[:10] or rec.get("date"),
        "title": event.get("title") or "",
    }

    new_place = clean_place(event.get("place"))
    old_place = clean_place(rec.get("place"))
    if old_place != new_place:
        entries.append({**base, "at": now, "change": "place",
                        "from": old_place, "to": new_place})

    new_start, new_end = event.get("start_time"), event.get("end_time")
    if rec.get("start_time") != new_start or rec.get("end_time") != new_end:
        entries.append({**base, "at": now, "change": "time",
                        "from": {"start_time": rec.get("start_time"), "end_time": rec.get("end_time")},
                        "to": {"start_time": new_start, "end_time": new_end}})

    return entries


def load_updates_log(path: str) -> List[Dict[str, Any]]:
    """Load the existing tracker entries (oldest first)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, ValueError):
        return []
    return data.get("updates", []) if isinstance(data, dict) else []


def update_change_log(path: str, entries: List[Dict[str, Any]],
                      reactivated_ids: List[int]) -> tuple:
    """
    Update events/<year>/updates.json (chronological, oldest first):

      • append the new entries, and
      • drop the "removed" entries of events that came back, so a cancellation
        notice disappears once the event is re-enabled instead of lingering as
        a stale warning.

    Returns (added, purged). A no-op when there is nothing to add or purge, so
    an unchanged sync leaves the file untouched.
    """
    log = load_updates_log(path)

    purged = 0
    if reactivated_ids:
        back = set(reactivated_ids)
        before = len(log)
        log = [u for u in log
               if not (u.get("change") == "removed" and u.get("id") in back)]
        purged = before - len(log)

    if not entries and not purged:
        return 0, 0

    log.extend(entries)
    if len(log) > MAX_UPDATE_ENTRIES:
        log = log[-MAX_UPDATE_ENTRIES:]

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": brt_now_iso(),
            "total": len(log),
            "updates": log,
        }, f, ensure_ascii=False, indent=2)
    return len(entries), purged


def reconcile_events(events_by_date: Dict[str, List[Dict[str, Any]]], id_map: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assign STABLE integer ids to the fetched events and detect what changed,
    WITHOUT yet applying removals (so the caller can veto a suspicious run first).

    Mutates each fetched event (event['id'] = int) and the id_map (mints ids,
    updates hash/date/tracked baselines, reactivates events that came back).
    Returns a report:
        {
          "changed_dates": set[str],   # dates whose files must be rewritten
          "active_before": int,        # events that were active before this run
          "vanished": list[str],       # active keys missing from this fetch
          "new": int, "changed": int, "reactivated": int,
          "updates": list[dict],       # place/time changes for the tracker
          "reactivated_ids": list[int],# events back from cancellation
        }
    """
    events = id_map["events"]
    changed_dates = set()
    seen = set()
    new = changed = reactivated = 0
    active_before = sum(1 for r in events.values() if not r.get("removed_at"))
    now = brt_now_iso()
    updates = []
    reactivated_ids = []

    for date, day_events in events_by_date.items():
        for event in day_events:
            key = str(event.get("id"))
            seen.add(key)
            h = event_content_hash(event)
            rec = events.get(key)
            if rec is None:
                rec = {"id": id_map["next_id"], "hash": h, "date": date, "removed_at": None}
                id_map["next_id"] += 1
                events[key] = rec
                changed_dates.add(date)
                new += 1
            else:
                came_back = bool(rec.get("removed_at"))
                if came_back:                     # was soft-removed, now back
                    rec["removed_at"] = None
                    changed_dates.add(date)
                    if rec.get("date"):
                        changed_dates.add(rec["date"])
                    reactivated += 1
                    # Its "cancelled" notice is now wrong — drop it from the log.
                    reactivated_ids.append(rec["id"])
                # Track the user-visible changes (place / time). Skipped when the
                # event just came back — a cancel→re-enable cycle is not tracked.
                if not came_back:
                    updates.extend(detect_tracked_changes(rec, event, now))
                if rec.get("hash") != h:
                    rec["hash"] = h
                    changed_dates.add(date)
                    changed += 1
                if rec.get("date") != date:
                    if rec.get("date"):
                        changed_dates.add(rec["date"])   # left its previous day
                    rec["date"] = date
                    changed_dates.add(date)
            # (Re)seed the tracked baselines + title snapshot for the next run.
            snapshot_tracked_fields(rec, event)
            event["id"] = rec["id"]

    vanished = [k for k, r in events.items() if k not in seen and not r.get("removed_at")]
    return {
        "changed_dates": changed_dates,
        "active_before": active_before,
        "vanished": vanished,
        "new": new,
        "changed": changed,
        "reactivated": reactivated,
        "updates": updates,
        "reactivated_ids": reactivated_ids,
    }


def apply_removals(id_map: Dict[str, Any], vanished: List[str], changed_dates: set) -> List[Dict[str, Any]]:
    """
    Soft-delete the vanished keys: stamp removed_at (keep id + date) and mark
    their day for rewrite. Called only after the safety guard approves the run.
    Returns one "removed" update entry per event, for the change tracker.
    """
    now = brt_now_iso()
    entries = []
    day_cache: Dict[str, Dict[int, str]] = {}

    def title_from_day_file(date: str, event_id: int) -> str:
        """Look a title up in the last written day file — used for records that
        predate the title snapshot (an event can't be snapshotted on the run it
        disappears), so a cancellation notice is never left nameless."""
        if not date:
            return ""
        if date not in day_cache:
            titles = {}
            try:
                with open(os.path.join(OUTPUT_DIR, f"hacktown_events_{date}.json"), "r", encoding="utf-8") as f:
                    for e in json.load(f).get("events", []):
                        titles[e.get("id")] = e.get("title") or ""
            except (FileNotFoundError, ValueError):
                pass
            day_cache[date] = titles
        return day_cache[date].get(event_id, "")

    for key in vanished:
        rec = id_map["events"].get(key)
        if rec is None:
            continue
        rec["removed_at"] = now
        if rec.get("date"):
            changed_dates.add(rec["date"])
        title = rec.get("title") or title_from_day_file(rec.get("date"), rec["id"])
        entries.append({
            "at": now,
            "id": rec["id"],
            "change": "removed",
            "date": rec.get("date"),
            "title": title,
        })
    return entries


def carried_removed_for_date(date: str, id_map: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Last-known objects of soft-removed events belonging to `date`, read from the
    existing day file and flagged `removed: true`, so a rewrite preserves them
    instead of dropping them.
    """
    removed_ids = {
        rec["id"] for rec in id_map["events"].values()
        if rec.get("removed_at") and rec.get("date") == date
    }
    if not removed_ids:
        return []
    path = os.path.join(OUTPUT_DIR, f"hacktown_events_{date}.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            old = json.load(f)
    except (FileNotFoundError, ValueError):
        return []
    carried = []
    for e in old.get("events", []):
        if e.get("id") in removed_ids:
            e = dict(e)
            e["removed"] = True
            carried.append(e)
    return carried
