#!/usr/bin/env python3
"""
Weekly external-link checker for the Utah Agile site.

Crawls index.html, privacy.html, and 404.html for external http(s) links
(sponsor sites, social icons, Meetup, YouTube, etc.) and requests each one,
flagging anything that comes back 4xx/5xx or fails to connect.

Deliberately NOT part of scripts/check_site.py, which runs on every push/PR —
requests to third-party sites are inherently flaky (rate limits, bot
blocking, transient outages) and would make that fast, deterministic check
unreliable. This only runs on its own weekly schedule
(.github/workflows/check-links.yml) or on demand.

Some sites (LinkedIn especially) reliably return 403/429/999 to any scripted
request regardless of whether the page is real — that's bot-blocking, not
breakage, and treating it as a hard failure would make this check cry wolf
on the same handful of links every single week. Those codes are reported as
informational "BLOCKED" rather than failing the run — as is a server that
accepts the connection and then hangs up without any response (some WAFs do
this to Python's TLS fingerprint instead of sending a 403). Only signals that
actually mean the resource is gone (404/410), the server errored (5xx), or
the connection failed outright (DNS, refused, timeout, TLS) count as a real
failure.

Run locally:   python3 scripts/check_links.py
"""

import html.parser
import http.client
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML_FILES = ["index.html", "privacy.html", "404.html"]
TIMEOUT = 15
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; utahagile-web-link-check/1.0)"}

# Status codes that mean "a script isn't welcome here," not "this is broken."
BOT_BLOCKED_CODES = {401, 403, 429, 999}

# Returned by check() when the server accepts the TLS connection and then hangs
# up without sending any HTTP response, for both HEAD and GET. A dead site
# fails earlier (DNS error, refused connection, timeout); this is what WAFs
# that fingerprint Python's TLS handshake do instead of sending a 403 —
# agilealliance.org started doing it in Nov 2026 while loading fine in curl
# and browsers. Treated like BOT_BLOCKED_CODES, not as a broken link.
DROPPED = "connection dropped without response"


class LinkCollector(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = set()

    def handle_starttag(self, tag, attrs):
        self._collect(attrs)

    def handle_startendtag(self, tag, attrs):
        self._collect(attrs)

    def _collect(self, attrs):
        for attr, value in attrs:
            if attr in ("href", "src") and value and re.match(r"^https?://", value):
                self.links.add(value)


def collect_links() -> list:
    links = set()
    for rel in HTML_FILES:
        path = ROOT / rel
        if not path.is_file():
            continue
        p = LinkCollector()
        p.feed(path.read_text(encoding="utf-8"))
        links |= p.links
    return sorted(links)


def check(url: str):
    """Return an HTTP status int on success, DROPPED if the server hangs up on
    both HEAD and GET without responding, or an error string on any other
    failure."""
    try:
        req = urllib.request.Request(url, headers=HEADERS, method="HEAD")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        if e.code not in (405, 501):  # a real HTTP error, not "HEAD unsupported"
            return e.code
    except http.client.RemoteDisconnected:
        pass  # some servers drop HEAD but serve GET — try it before concluding
    except Exception as e:
        return str(e)

    try:  # retry with GET — some servers reject HEAD but serve GET fine
        req = urllib.request.Request(url, headers=HEADERS, method="GET")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except http.client.RemoteDisconnected:
        return DROPPED
    except Exception as e:
        return str(e)


def classify(result) -> str:
    """Map a check() result to "ok", "blocked" (bot protection — informational,
    doesn't fail the run), or "fail" (resource gone, server error, or the
    connection failed outright: DNS, refused, timeout, TLS)."""
    if isinstance(result, int) and result < 400:
        return "ok"
    if result == DROPPED or (isinstance(result, int) and result in BOT_BLOCKED_CODES):
        return "blocked"
    return "fail"


def main():
    links = collect_links()
    print(f"Checking {len(links)} external link(s)...\n")
    broken, blocked = [], []
    for url in links:
        result = check(url)
        kind = classify(result)
        if kind == "ok":
            print(f"  OK      {result}  {url}")
        elif kind == "blocked":
            print(f"  BLOCKED {result}  {url}")
            blocked.append((url, result))
        else:
            print(f"  FAIL    {result}  {url}")
            broken.append((url, result))

    print("\n" + ("-" * 48))
    if blocked:
        print(f"{len(blocked)} link(s) returned a bot-blocking signal (403/429/999/401, or a "
              "connection dropped without any response) — "
              "not treated as failures, but worth a manual glance if the list grows:")
        for url, result in blocked:
            print(f"  {result}  {url}")

    if broken:
        print(f"\nFAILED: {len(broken)} broken link(s)")
        for url, result in broken:
            print(f"::error::broken link {url} -> {result}")
        sys.exit(1)
    print("\nPASSED: no broken links (see above for any bot-blocked ones)")


if __name__ == "__main__":
    main()
