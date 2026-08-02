#!/usr/bin/env python3
"""
Supabase / PostgREST provider (HackTown 2026).

The 2026 schedule lives in a public Supabase project (the Lovable embed on
hacktown.com.br/programacao/ reads it directly). One request returns the whole
schedule with venues, tracks and speakers joined — no pagination needed at the
current size. This module fetches that payload and transforms each row into the
canonical event shape that sync_common writes out, so 2026 is stored exactly
like 2025.

Connection details come from config/years.json → years.2026.api.

License: MIT
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# This source keys events by UUID; ask the dispatcher to remap them to stable
# integer ids (via sync_common's id map) so favorites + share URLs stay small.
REMAP_IDS = True

# America/Sao_Paulo is UTC-3 year-round (Brazil dropped DST in 2019). The API
# sends event_date + start_time/end_time as local wall-clock with no offset;
# we stamp -03:00 so the stored instant renders at the real local time.
SP_OFFSET = "-03:00"

# The exact join the embed uses. Overridable via api.select in the registry.
DEFAULT_SELECT = (
    "id,title,description,event_date,start_time,end_time,age_rating,status,"
    "venue:venue_id(name,area),"
    "event_tracks(tracks(id,name,code)),"
    "event_speakers(cargo_empresa,mini_bio,photo_url,"
    "speakers(id,name,cargo_empresa,mini_bio,photo_url))"
)

_config: Dict[str, Any] = {}


def configure(api_config: Dict[str, Any]) -> None:
    """Store the year's api config block (base_url, apikey, select, …)."""
    global _config
    _config = api_config or {}


def _request(table: str, params: Dict[str, str], page: int = 1000) -> List[Dict[str, Any]]:
    """GET a PostgREST table with Range pagination; returns all rows."""
    base = _config["base_url"].rstrip("/")
    key = _config["apikey"]
    rows: List[Dict[str, Any]] = []
    offset = 0
    while True:
        qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        req = urllib.request.Request(
            f"{base}/{table}?{qs}",
            headers={
                "apikey": key,
                "Accept": "application/json",
                "Range-Unit": "items",
                "Range": f"{offset}-{offset + page - 1}",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            batch = json.load(resp)
        rows.extend(batch)
        if len(batch) < page:
            return rows
        offset += page


def _iso(date: str, clock: str):
    """Combine 'YYYY-MM-DD' + 'HH:MM:SS' into an ISO datetime with the SP offset."""
    if not date or not clock:
        return None
    return f"{date}T{clock}{SP_OFFSET}"


def _map_speaker(event_speaker: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map an event_speakers row to the canonical speaker shape. Per-event overrides
    (cargo_empresa / mini_bio / photo_url on the join row) win over the base
    speaker record, per the API notes.
    """
    base = event_speaker.get("speakers") or {}
    return {
        "id": base.get("id"),
        "name": base.get("name") or "",
        "role": event_speaker.get("cargo_empresa") or base.get("cargo_empresa") or "",
        "bio": event_speaker.get("mini_bio") or base.get("mini_bio") or "",
        "picture": event_speaker.get("photo_url") or base.get("photo_url") or "",
        "company": "",
    }


def _to_canonical(row: Dict[str, Any]) -> Dict[str, Any]:
    """Transform one Supabase event row into the canonical (app-facing) event."""
    venue = row.get("venue") or {}
    speakers = [
        _map_speaker(es)
        for es in (row.get("event_speakers") or [])
        if es.get("speakers")
    ]
    # Tracks (trilhas) → tags[]; names only, for future use (no filter yet).
    tags = [
        t["tracks"]["name"]
        for t in (row.get("event_tracks") or [])
        if t.get("tracks") and t["tracks"].get("name")
    ]
    return {
        "id": row.get("id"),
        "start_time": _iso(row.get("event_date"), row.get("start_time")),
        "end_time": _iso(row.get("event_date"), row.get("end_time")),
        "title": row.get("title") or "",
        "description": row.get("description") or "",
        "place": venue.get("name") or "",
        "speakers": speakers,
        "tags": tags,
    }


def fetch(dates: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch the whole schedule and return canonical events grouped by event_date.
    `dates` (from config) is used only to log/flag mismatches — the API returns
    every day in one call.
    """
    table = _config.get("events_table", "events")
    params = {
        "select": _config.get("select", DEFAULT_SELECT),
        "order": "event_date.asc,start_time.asc",
    }
    # status = _config.get("status_filter", "eq.publicado")
    # if status:
    #     params["status"] = status

    logger.info(f"🌐 Fetching the full 2026 schedule from Supabase ({table})...")
    rows = _request(table, params)
    logger.info(f"✅ Fetched {len(rows)} events in a single request")

    by_date: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        by_date.setdefault(row.get("event_date"), []).append(_to_canonical(row))

    # Flag any drift between the data's dates and the configured day tabs.
    if dates:
        data_dates = set(by_date)
        config_dates = set(dates)
        extra = sorted(data_dates - config_dates)
        missing = sorted(config_dates - data_dates)
        if extra:
            logger.warning(f"⚠️  API has events on dates not in config/years.json: {', '.join(extra)}")
        if missing:
            logger.warning(f"⚠️  Config lists dates with no events in the API: {', '.join(missing)}")

    for d in sorted(by_date):
        logger.info(f"   • {d}: {len(by_date[d])} events")
    return by_date
