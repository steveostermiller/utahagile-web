#!/usr/bin/env python3
"""
Fetch upcoming events from the Utah Agile Meetup iCal feed and write them to
data/events.json. Zero third-party dependencies (stdlib only) so it runs
anywhere, including a stock GitHub Actions runner.

Meetup's iCal feed does not carry a venue or event photo, even when both are
public on the event page — confirmed by inspecting the raw feed and the
page's own structured data. So each event is additionally (best-effort)
enriched by fetching its own Meetup page and reading the schema.org Event
JSON-LD block embedded there, which does include a location and image(s).
This enrichment step is optional per event: if the fetch fails or Meetup
changes that markup, the event still ships with its reliable iCal fields
(title/date/RSVP link) — it just won't have a location or thumbnail.

Run locally:   python3 scripts/build_events.py
In CI:         invoked on a schedule by .github/workflows/update-events.yml
"""

import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ICAL_URL = "https://www.meetup.com/utahagile/events/ical/"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "events.json"
ENRICH_LIMIT = 10  # cap how many event pages we fetch per run
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5  # seconds


def fetch_ical(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "utahagile-web/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_with_retry(fetch_fn, attempts=RETRY_ATTEMPTS, delay=RETRY_DELAY):
    """Retry a flaky network call before giving up — see build_videos.py's
    copy of this for the production incident that motivated it. Only used
    for the main iCal fetch, not per-event enrichment (enrich_event already
    fails soft and shouldn't slow down a whole run retrying each event)."""
    for attempt in range(1, attempts + 1):
        try:
            return fetch_fn()
        except Exception as e:
            if attempt == attempts:
                raise
            print(f"WARNING: fetch attempt {attempt}/{attempts} failed ({e}); "
                  f"retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)


def unfold(text: str) -> str:
    # iCal "folds" long lines by starting continuations with a space or tab.
    return re.sub(r"\r?\n[ \t]", "", text)


def parse_dt(value: str) -> str:
    """Return an ISO 8601 string. Handles 'YYYYMMDDTHHMMSSZ' and date-only."""
    value = value.strip()
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            dt = datetime.strptime(value, fmt)
            if fmt.endswith("Z"):
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            continue
    return value  # fall back to raw string rather than crash


def unescape(value: str) -> str:
    return (value.replace("\\n", " ").replace("\\,", ",")
                 .replace("\\;", ";").replace("\\\\", "\\")).strip()


def parse_events(ical: str) -> list:
    ical = unfold(ical)
    events = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", ical, re.DOTALL):
        ev = {}
        for line in block.strip().splitlines():
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            key = key.split(";", 1)[0]  # drop params like DTSTART;TZID=...
            if key == "SUMMARY":
                ev["title"] = unescape(val)
            elif key == "DTSTART":
                ev["start"] = parse_dt(val)
            elif key == "DTEND":
                ev["end"] = parse_dt(val)
            elif key == "LOCATION":
                ev["location"] = unescape(val)
            elif key == "URL":
                ev["url"] = val.strip()
            elif key == "DESCRIPTION":
                ev["description"] = unescape(val)
        if ev.get("title") and ev.get("start"):
            ev.setdefault("url", "https://www.meetup.com/utahagile/events/")
            events.append(ev)
    events.sort(key=lambda e: e["start"])
    return events


def looks_like_ical(text: str) -> bool:
    return "BEGIN:VCALENDAR" in text


def fetch_event_page(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "utahagile-web/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_event_schema(html: str):
    """Return the schema.org Event dict embedded in a Meetup event page's
    JSON-LD, or None if it's missing/malformed. A page can have several
    JSON-LD blocks (Organization, BreadcrumbList, ...); only one is the
    Event itself."""
    for block in re.findall(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL
    ):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        for item in (data if isinstance(data, list) else [data]):
            if isinstance(item, dict) and item.get("@type") == "Event":
                return item
    return None


def location_from_schema(event_schema: dict):
    place = event_schema.get("location")
    if not isinstance(place, dict):
        return None
    address = place.get("address")
    street = address.get("streetAddress") if isinstance(address, dict) else None
    parts = [p for p in (place.get("name"), street) if p]
    return " · ".join(parts) if parts else None


def thumbnail_from_schema(event_schema: dict):
    images = event_schema.get("image")
    if isinstance(images, list) and images:
        return images[0]
    if isinstance(images, str):
        return images
    return None


def enrich_event(ev: dict) -> dict:
    """Best-effort: fetch the event's own Meetup page and merge in a venue
    and thumbnail image from its embedded schema.org data — fields the iCal
    feed doesn't carry. Never raises; on any failure ev is returned
    unchanged, so title/date/RSVP still work even if this fails."""
    url = ev.get("url")
    if not url:
        return ev
    try:
        schema = extract_event_schema(fetch_event_page(url))
        if not schema:
            return ev
        location = location_from_schema(schema)
        if location:
            ev["location"] = location
        thumbnail = thumbnail_from_schema(schema)
        if thumbnail:
            ev["thumbnail"] = thumbnail
    except Exception as e:
        print(f"WARNING: could not enrich event '{ev.get('title')}': {e}", file=sys.stderr)
    return ev


def main() -> int:
    try:
        ical = fetch_with_retry(lambda: fetch_ical(ICAL_URL))
    except Exception as e:  # network hiccup shouldn't wipe a good file
        print(f"ERROR fetching iCal: {e}", file=sys.stderr)
        return 1

    # Zero *events* is a normal state (no upcoming meetup scheduled right
    # now), so we don't guard on an empty result the way build_videos.py
    # does. But if Meetup stops returning a calendar at all (redirect, error
    # page, feed retired), that's a real break — don't let it silently wipe
    # a good events.json with an empty list.
    if not looks_like_ical(ical):
        print("ERROR: fetched content doesn't look like an iCal calendar "
              "(no BEGIN:VCALENDAR) — refusing to overwrite events.json", file=sys.stderr)
        return 1

    events = parse_events(ical)
    for ev in events[:ENRICH_LIMIT]:
        enrich_event(ev)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(events, indent=2) + "\n")
    print(f"Wrote {len(events)} event(s) to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
