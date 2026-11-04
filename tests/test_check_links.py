#!/usr/bin/env python3
"""
Offline unit tests for scripts/check_links.py — no network access.

Pins down which outcomes fail the weekly link check and which are treated as
informational bot-blocking. The "connection dropped" case exists because
agilealliance.org began hanging up on Python's TLS handshake in Nov 2026
(site fine in curl/browsers) and failed the run for something that isn't a
broken link.
"""

import http.client
import socket
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_links  # noqa: E402


def _ok_response(status=200):
    resp = MagicMock()
    resp.status = status
    resp.__enter__.return_value = resp
    return resp


class ClassifyTests(unittest.TestCase):
    def test_success_statuses_are_ok(self):
        for status in (200, 202, 301, 399):
            self.assertEqual(check_links.classify(status), "ok", status)

    def test_bot_blocking_statuses_are_blocked(self):
        for status in (401, 403, 429, 999):
            self.assertEqual(check_links.classify(status), "blocked", status)

    def test_dropped_connection_is_blocked(self):
        self.assertEqual(check_links.classify(check_links.DROPPED), "blocked")

    def test_gone_or_server_error_statuses_fail(self):
        for status in (404, 410, 500, 503):
            self.assertEqual(check_links.classify(status), "fail", status)

    def test_other_connection_errors_still_fail(self):
        for msg in ("<urlopen error [Errno -2] Name or service not known>",
                    "timed out",
                    "<urlopen error [Errno 111] Connection refused>",
                    "<urlopen error [SSL: CERTIFICATE_VERIFY_FAILED]>"):
            self.assertEqual(check_links.classify(msg), "fail", msg)


class CheckTests(unittest.TestCase):
    def test_returns_status_on_success(self):
        with patch("check_links.urllib.request.urlopen", return_value=_ok_response(200)):
            self.assertEqual(check_links.check("https://example.com/"), 200)

    def test_dropped_on_head_and_get_returns_dropped(self):
        drop = http.client.RemoteDisconnected("Remote end closed connection without response")
        with patch("check_links.urllib.request.urlopen", side_effect=drop):
            self.assertEqual(check_links.check("https://example.com/"), check_links.DROPPED)

    def test_dropped_head_but_working_get_is_ok(self):
        drop = http.client.RemoteDisconnected("Remote end closed connection without response")
        with patch("check_links.urllib.request.urlopen",
                   side_effect=[drop, _ok_response(200)]):
            self.assertEqual(check_links.check("https://example.com/"), 200)

    def test_timeout_is_an_error_string_not_dropped(self):
        with patch("check_links.urllib.request.urlopen", side_effect=socket.timeout("timed out")):
            result = check_links.check("https://example.com/")
        self.assertNotEqual(result, check_links.DROPPED)
        self.assertEqual(check_links.classify(result), "fail")

    def test_404_is_returned_as_status(self):
        err = urllib.error.HTTPError("https://example.com/", 404, "Not Found", {}, None)
        with patch("check_links.urllib.request.urlopen", side_effect=err):
            self.assertEqual(check_links.check("https://example.com/"), 404)

    def test_head_405_falls_back_to_get(self):
        err = urllib.error.HTTPError("https://example.com/", 405, "Method Not Allowed", {}, None)
        with patch("check_links.urllib.request.urlopen",
                   side_effect=[err, _ok_response(200)]):
            self.assertEqual(check_links.check("https://example.com/"), 200)


if __name__ == "__main__":
    unittest.main()
