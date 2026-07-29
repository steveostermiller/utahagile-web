#!/usr/bin/env python3
"""
Offline unit tests for scripts/build_events.py — no network access.

Feeds small fixture iCal documents through parse_events() so a change to
Meetup's feed shape shows up as a failing test, and exercises the
looks_like_ical() guard that stops a non-calendar response (redirect/error
page) from silently wiping a good data/events.json.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_events  # noqa: E402

SAMPLE_ICAL = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Sprint Planning Deep Dive
DTSTART:20260901T180000Z
DTEND:20260901T193000Z
LOCATION:Zoom
URL:https://www.meetup.com/utahagile/events/12345/
DESCRIPTION:Come learn about sprint planning.
END:VEVENT
BEGIN:VEVENT
SUMMARY:Retro Roundtable
DTSTART:20260815T180000Z
END:VEVENT
END:VCALENDAR
"""

NOT_ICAL = "<html><body>Sorry, this feed has moved.</body></html>"

# Shaped like a real Meetup event page (captured 2026-07-28): several JSON-LD
# blocks, only one of which is the @type Event.
EVENT_PAGE_HTML = """<html><head>
<script type="application/ld+json">{"@type":"Organization","name":"Meetup"}</script>
<script type="application/ld+json">{"@type":"Event","name":"End of Summer Networking",
  "image":["https://secure-content.meetupstatic.com/images/a/676x676.jpg",
           "https://secure-content.meetupstatic.com/images/a/676x380.jpg"],
  "location":{"@type":"Place","name":"Olympic Park",
              "address":{"@type":"PostalAddress","streetAddress":"2700 W Parkside Dr, Lehi, UT"}}}
</script>
</head><body></body></html>"""

NO_EVENT_SCHEMA_HTML = """<html><head>
<script type="application/ld+json">{"@type":"Organization","name":"Meetup"}</script>
</head><body></body></html>"""

MALFORMED_JSONLD_HTML = """<html><head>
<script type="application/ld+json">{not valid json</script>
</head><body></body></html>"""


class ParseEventsTests(unittest.TestCase):
    def test_extracts_and_sorts_events_by_start(self):
        events = build_events.parse_events(SAMPLE_ICAL)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["title"], "Retro Roundtable")       # Aug, earlier
        self.assertEqual(events[1]["title"], "Sprint Planning Deep Dive")  # Sep, later
        self.assertEqual(events[1]["location"], "Zoom")
        self.assertEqual(events[1]["url"], "https://www.meetup.com/utahagile/events/12345/")

    def test_event_missing_summary_is_skipped(self):
        ical = "BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART:20260901T180000Z\nEND:VEVENT\nEND:VCALENDAR\n"
        self.assertEqual(build_events.parse_events(ical), [])

    def test_default_url_applied_when_missing(self):
        ical = ("BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:No URL Event\n"
                "DTSTART:20260901T180000Z\nEND:VEVENT\nEND:VCALENDAR\n")
        events = build_events.parse_events(ical)
        self.assertEqual(events[0]["url"], "https://www.meetup.com/utahagile/events/")

    def test_empty_calendar_is_a_valid_zero_event_result(self):
        # No upcoming events scheduled is a normal state, not an error.
        ical = "BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n"
        self.assertEqual(build_events.parse_events(ical), [])


class LooksLikeIcalTests(unittest.TestCase):
    def test_valid_calendar_passes(self):
        self.assertTrue(build_events.looks_like_ical(SAMPLE_ICAL))

    def test_non_calendar_content_fails(self):
        self.assertFalse(build_events.looks_like_ical(NOT_ICAL))


class ExtractEventSchemaTests(unittest.TestCase):
    def test_finds_the_event_block_among_several(self):
        schema = build_events.extract_event_schema(EVENT_PAGE_HTML)
        self.assertIsNotNone(schema)
        self.assertEqual(schema["name"], "End of Summer Networking")

    def test_returns_none_when_no_event_block_present(self):
        self.assertIsNone(build_events.extract_event_schema(NO_EVENT_SCHEMA_HTML))

    def test_returns_none_on_malformed_json(self):
        self.assertIsNone(build_events.extract_event_schema(MALFORMED_JSONLD_HTML))


class LocationFromSchemaTests(unittest.TestCase):
    def test_combines_venue_name_and_street_address(self):
        schema = build_events.extract_event_schema(EVENT_PAGE_HTML)
        self.assertEqual(build_events.location_from_schema(schema),
                          "Olympic Park · 2700 W Parkside Dr, Lehi, UT")

    def test_none_when_location_missing(self):
        self.assertIsNone(build_events.location_from_schema({}))

    def test_none_when_location_is_not_a_place(self):
        self.assertIsNone(build_events.location_from_schema({"location": "online"}))


class ThumbnailFromSchemaTests(unittest.TestCase):
    def test_takes_first_image_from_list(self):
        schema = build_events.extract_event_schema(EVENT_PAGE_HTML)
        self.assertEqual(build_events.thumbnail_from_schema(schema),
                          "https://secure-content.meetupstatic.com/images/a/676x676.jpg")

    def test_accepts_a_bare_string_image(self):
        self.assertEqual(build_events.thumbnail_from_schema({"image": "https://x/y.jpg"}),
                          "https://x/y.jpg")

    def test_none_when_image_missing(self):
        self.assertIsNone(build_events.thumbnail_from_schema({}))


class EnrichEventTests(unittest.TestCase):
    def test_merges_location_and_thumbnail_on_success(self):
        ev = {"title": "End of Summer Networking", "url": "https://meetup.com/x/1"}
        with patch.object(build_events, "fetch_event_page", return_value=EVENT_PAGE_HTML):
            enriched = build_events.enrich_event(ev)
        self.assertEqual(enriched["location"], "Olympic Park · 2700 W Parkside Dr, Lehi, UT")
        self.assertTrue(enriched["thumbnail"].startswith("https://"))

    def test_leaves_event_unchanged_when_fetch_fails(self):
        ev = {"title": "Sprint Planning", "url": "https://meetup.com/x/2"}
        with patch.object(build_events, "fetch_event_page", side_effect=OSError("timed out")):
            enriched = build_events.enrich_event(dict(ev))
        self.assertEqual(enriched, ev)  # unchanged — no crash, no partial data

    def test_leaves_event_unchanged_when_page_has_no_event_schema(self):
        ev = {"title": "Sprint Planning", "url": "https://meetup.com/x/3"}
        with patch.object(build_events, "fetch_event_page", return_value=NO_EVENT_SCHEMA_HTML):
            enriched = build_events.enrich_event(dict(ev))
        self.assertEqual(enriched, ev)

    def test_noop_when_event_has_no_url(self):
        ev = {"title": "No URL Event"}
        self.assertEqual(build_events.enrich_event(dict(ev)), ev)


if __name__ == "__main__":
    unittest.main()
