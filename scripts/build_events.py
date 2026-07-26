#!/usr/bin/env python3
"""
Fetch upcoming events from the Utah Agile Meetup iCal feed and write them to
data/events.json. Zero third-party dependencies (stdlib only) so it runs
anywhere, including a stock GitHub Actions runner.

Run locally:   python3 scripts/build_events.py
In CI:         invoked on a schedule by .github/workflows/update-events.yml
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ICAL_URL = "https://www.meetup.com/utahagile/events/ical/"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "events.json"


def fetch_ical(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "utahagile-web/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


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


def main() -> int:
    try:
        ical = fetch_ical(ICAL_URL)
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
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(events, indent=2) + "\n")
    print(f"Wrote {len(events)} event(s) to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
