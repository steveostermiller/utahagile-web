#!/usr/bin/env python3
"""
Fetch the most recent videos from the Utah Agile YouTube channel and write
them to data/videos.json. Uses YouTube's public per-channel Atom feed (no API
key required). Zero third-party dependencies (stdlib only).

Run locally:   python3 scripts/build_videos.py
In CI:         invoked on a schedule by .github/workflows/update-videos.yml
"""

import json
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

CHANNEL_ID = "UCXn0hT3Kcd0kHqpHdxrf0Ng"  # Utah Agile
FEED_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "videos.json"
LIMIT = 2
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5  # seconds

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}


def fetch_feed(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "utahagile-web/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def fetch_with_retry(fetch_fn, attempts=RETRY_ATTEMPTS, delay=RETRY_DELAY):
    """Retry a flaky network call before giving up. Smooths over the kind of
    one-off transient blip that's actually happened in production (two
    hourly runs failed the same way, but the very next run succeeded fine)
    without masking a real, persistent failure — the last exception still
    propagates once all attempts are exhausted."""
    for attempt in range(1, attempts + 1):
        try:
            return fetch_fn()
        except Exception as e:
            if attempt == attempts:
                raise
            print(f"WARNING: fetch attempt {attempt}/{attempts} failed ({e}); "
                  f"retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)


def parse_videos(xml_bytes: bytes) -> list:
    root = ET.fromstring(xml_bytes)
    videos = []
    for entry in root.findall("atom:entry", NS):
        video_id = entry.findtext("yt:videoId", default="", namespaces=NS)
        title = entry.findtext("atom:title", default="", namespaces=NS)
        if not video_id or not title:
            continue
        videos.append({
            "id": video_id,
            "title": title,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "embed": f"https://www.youtube.com/embed/{video_id}?autoplay=1",
            "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        })
    return videos[:LIMIT]


def save(videos: list, out_path: Path) -> bool:
    """Write videos to out_path. Refuses to overwrite with an empty result —
    an active channel's feed should never legitimately return zero videos, so
    a feed-format change fails loudly here instead of silently blanking the
    Past Meetup Events section."""
    if not videos:
        print(f"ERROR: parsed 0 videos from feed — refusing to overwrite {out_path}",
              file=sys.stderr)
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(videos, indent=2) + "\n")
    print(f"Wrote {len(videos)} video(s) to {out_path}")
    return True


def main() -> int:
    try:
        xml_bytes = fetch_with_retry(lambda: fetch_feed(FEED_URL))
    except Exception as e:  # network hiccup shouldn't wipe a good file
        print(f"ERROR fetching YouTube feed: {e}", file=sys.stderr)
        return 1

    videos = parse_videos(xml_bytes)
    return 0 if save(videos, OUT_PATH) else 1


if __name__ == "__main__":
    raise SystemExit(main())
