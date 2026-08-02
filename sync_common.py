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
        "total_events": len(processed_events),
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
