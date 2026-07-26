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
informational "BLOCKED" rather than failing the run; only signals that
actually mean the resource is gone (404/410), the server errored (5xx), or
the connection failed outright count as a real failure.

Run locally:   python3 scripts/check_links.py
"""

import html.parser
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
    """Return an HTTP status int on success, or an error string on failure."""
    try:
        req = urllib.request.Request(url, headers=HEADERS, method="HEAD")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        if e.code not in (405, 501):  # a real HTTP error, not "HEAD unsupported"
            return e.code
    except Exception as e:
        return str(e)

    try:  # retry with GET — some servers reject HEAD but serve GET fine
        req = urllib.request.Request(url, headers=HEADERS, method="GET")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return str(e)


def main():
    links = collect_links()
    print(f"Checking {len(links)} external link(s)...\n")
    broken, blocked = [], []
    for url in links:
        result = check(url)
        if isinstance(result, int) and result < 400:
            print(f"  OK      {result}  {url}")
        elif isinstance(result, int) and result in BOT_BLOCKED_CODES:
            print(f"  BLOCKED {result}  {url}")
            blocked.append((url, result))
        else:
            print(f"  FAIL    {result}  {url}")
            broken.append((url, result))

    print("\n" + ("-" * 48))
    if blocked:
        print(f"{len(blocked)} link(s) returned a bot-blocking status (403/429/999/401) — "
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
