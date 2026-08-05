#!/usr/bin/env python3
"""
Offline unit tests for scripts/build_videos.py — no network access.

Feeds small fixture Atom documents (shaped like YouTube's real channel feed,
captured 2026-07) through parse_videos() so a future change to that feed's
XML structure shows up as a failing test here, instead of silently shipping
an empty Past Meetup Events section to the live site. Also exercises the
save() guard that refuses to overwrite a good data/videos.json with an
empty result.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_videos  # noqa: E402

SAMPLE_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
 <title>Utah Agile</title>
 <entry>
  <id>yt:video:AAAAAAAAAAA</id>
  <yt:videoId>AAAAAAAAAAA</yt:videoId>
  <title>Newest Talk</title>
  <published>2026-06-01T00:00:00+00:00</published>
 </entry>
 <entry>
  <id>yt:video:BBBBBBBBBBB</id>
  <yt:videoId>BBBBBBBBBBB</yt:videoId>
  <title>Second Newest Talk</title>
  <published>2026-05-01T00:00:00+00:00</published>
 </entry>
 <entry>
  <id>yt:video:CCCCCCCCCCC</id>
  <yt:videoId>CCCCCCCCCCC</yt:videoId>
  <title>Third Talk (should be dropped by LIMIT)</title>
  <published>2026-04-01T00:00:00+00:00</published>
 </entry>
</feed>
"""

EMPTY_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Utah Agile</title></feed>
"""

ENTRY_MISSING_VIDEO_ID = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
 <entry><title>No video ID here</title></entry>
</feed>
"""


class ParseVideosTests(unittest.TestCase):
    def test_extracts_expected_fields_newest_first(self):
        videos = build_videos.parse_videos(SAMPLE_FEED)
        self.assertEqual(len(videos), build_videos.LIMIT)  # feed order limited to LIMIT
        first = videos[0]
        self.assertEqual(first["id"], "AAAAAAAAAAA")
        self.assertEqual(first["title"], "Newest Talk")
        self.assertEqual(first["url"], "https://www.youtube.com/watch?v=AAAAAAAAAAA")
        self.assertEqual(first["embed"], "https://www.youtube.com/embed/AAAAAAAAAAA?autoplay=1")
        self.assertEqual(first["thumbnail"], "https://i.ytimg.com/vi/AAAAAAAAAAA/hqdefault.jpg")
        self.assertEqual(videos[1]["id"], "BBBBBBBBBBB")

    def test_empty_feed_parses_to_empty_list(self):
        self.assertEqual(build_videos.parse_videos(EMPTY_FEED), [])

    def test_entry_missing_video_id_is_skipped(self):
        self.assertEqual(build_videos.parse_videos(ENTRY_MISSING_VIDEO_ID), [])


class SaveGuardTests(unittest.TestCase):
    def test_refuses_to_overwrite_good_file_with_empty_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "videos.json"
            out_path.write_text('[{"id": "existing"}]\n')
            ok = build_videos.save([], out_path)
            self.assertFalse(ok)
            self.assertIn("existing", out_path.read_text())  # untouched

    def test_writes_nonempty_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "videos.json"
            videos = build_videos.parse_videos(SAMPLE_FEED)
            ok = build_videos.save(videos, out_path)
            self.assertTrue(ok)
            self.assertEqual(len(json.loads(out_path.read_text())), build_videos.LIMIT)


class FetchWithRetryTests(unittest.TestCase):
    def test_succeeds_immediately_without_sleeping(self):
        with patch("build_videos.time.sleep") as mock_sleep:
            result = build_videos.fetch_with_retry(lambda: "ok")
        self.assertEqual(result, "ok")
        mock_sleep.assert_not_called()

    def test_succeeds_after_transient_failures_within_budget(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise OSError("transient blip")
            return "ok"

        with patch("build_videos.time.sleep") as mock_sleep:
            result = build_videos.fetch_with_retry(flaky, attempts=3, delay=5)
        self.assertEqual(result, "ok")
        self.assertEqual(calls["n"], 3)
        self.assertEqual(mock_sleep.call_count, 2)  # slept between attempts 1->2 and 2->3

    def test_raises_after_exhausting_all_attempts(self):
        def always_fails():
            raise OSError("persistent failure")

        with patch("build_videos.time.sleep"):
            with self.assertRaises(OSError):
                build_videos.fetch_with_retry(always_fails, attempts=3, delay=5)


if __name__ == "__main__":
    unittest.main()
