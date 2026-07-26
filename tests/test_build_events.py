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


if __name__ == "__main__":
    unittest.main()
