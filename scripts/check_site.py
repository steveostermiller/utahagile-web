#!/usr/bin/env python3
"""
Static-site sanity checks for the Utah Agile site.

Runs in CI (and locally) with nothing but the Python standard library, so it
never depends on external network calls or third-party actions. It guards the
kinds of breakage that actually happen when hand-editing a static, multi-page
site plus a couple of generated JSON feeds:

  1. Malformed HTML    — unclosed or stray tags.
  2. Broken assets     — a local href/src (css, js, image, favicon) that
                         points at a file that isn't in the repo.
  3. Broken anchors    — an in-page href="#id" with no matching element id,
                         or a cross-page href="index.html#id" (the pattern
                         privacy.html/404.html use to link back to a section)
                         with no matching id on index.html.
  4. Bad data files    — data/events.json / data/videos.json that are missing,
                         not valid JSON, not a list, or whose items are
                         missing required keys (catches the Meetup/YouTube
                         feed silently changing shape).
  5. Missing script ids — an element id that inline <script> logic reaches
                         via getElementById (e.g. the newsletter cookie-
                         consent gate) going missing or getting renamed,
                         which wouldn't otherwise show up as a broken link.
  6. SEO/GEO basics    — robots.txt and sitemap.xml exist and are well-formed,
                         each HTML page has the expected canonical link and
                         Open Graph meta tags, index.html's Organization
                         JSON-LD is present and valid JSON with the required
                         fields, and 404.html is marked noindex.

External URLs (https://, mailto:, etc.) are intentionally NOT fetched — that
would make CI flaky and is out of scope for a build-time check.

Exit code 0 = all good; 1 = problems found (fails the CI job).
"""

import html.parser
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_FILES = ["index.html", "privacy.html", "404.html"]

VOID = {"meta", "link", "img", "br", "hr", "input", "area", "base",
        "col", "embed", "source", "track", "wbr"}

DATA_FILES = {
    "data/events.json": ["title", "start"],
    "data/videos.json": ["id", "title", "url", "embed", "thumbnail"],
}

# Element ids that inline <script> logic depends on by getElementById — a
# rename/removal here wouldn't break check_html_file's anchor check (nothing
# links to these via href="#..."), so it needs its own guard. Currently just
# the newsletter cookie-consent gate in index.html.
REQUIRED_IDS = {
    "index.html": {
        "subscribe", "cookie-banner", "cookie-accept", "cookie-decline",
        "newsletter-form-wrap", "newsletter-consent-notice", "newsletter-consent-accept",
    },
}

# Open Graph properties every indexable page should have; keyed by the
# meta name="..."/property="..." attribute value.
REQUIRED_OG = {"og:title", "og:description", "og:url", "og:image"}
INDEXABLE_HTML_FILES = ["index.html", "privacy.html"]  # 404.html is noindex, checked separately

ORGANIZATION_JSONLD_REQUIRED_FIELDS = ["name", "url"]


class SiteParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []            # open (non-void) tags
        self.tag_errors = []       # malformed-tag messages
        self.ids = set()           # every id="" on the page
        self.local_refs = []       # local href/src values to check
        self.anchor_refs = []      # in-page "#fragment" links
        self.cross_page_refs = []  # "otherpage.html#fragment" links
        self.meta = {}             # meta name/property -> content
        self.canonical = None      # <link rel="canonical" href="...">
        self.robots_meta = None    # <meta name="robots" content="...">
        self.jsonld_blocks = []    # parsed dicts from <script type="application/ld+json">
        self.jsonld_errors = []    # malformed JSON-LD messages
        self._in_jsonld = False
        self._jsonld_buffer = ""

    def handle_starttag(self, tag, attrs):
        self._collect(tag, attrs)
        if tag == "script" and dict(attrs).get("type") == "application/ld+json":
            self._in_jsonld = True
            self._jsonld_buffer = ""
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self._collect(tag, attrs)  # e.g. <img ... /> — treat as void

    def handle_data(self, data):
        if self._in_jsonld:
            self._jsonld_buffer += data

    def handle_endtag(self, tag):
        if tag == "script" and self._in_jsonld:
            self._in_jsonld = False
            try:
                self.jsonld_blocks.append(json.loads(self._jsonld_buffer))
            except json.JSONDecodeError as e:
                self.jsonld_errors.append(f"malformed JSON-LD: {e}")
        if tag in VOID:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        elif tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.tag_errors.append(
                    f"<{self.stack[-1]}> is not closed before </{tag}>")
                self.stack.pop()
            if self.stack:
                self.stack.pop()
        else:
            self.tag_errors.append(f"stray </{tag}> with no matching open tag")

    def _collect(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        for attr in ("href", "src"):
            if attr in a and a[attr] is not None:
                self._classify(a[attr])
        if tag == "meta":
            key = a.get("property") or a.get("name")
            if key and a.get("content") is not None:
                self.meta[key] = a["content"]
            if a.get("name") == "robots":
                self.robots_meta = a.get("content")
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href")

    def _classify(self, value):
        v = value.strip()
        if not v:
            return
        m = re.match(r"^([\w./-]+\.html)#(.+)$", v)
        if v.startswith("#"):
            self.anchor_refs.append(v)
        elif m:
            self.cross_page_refs.append((m.group(1), m.group(2)))
        elif re.match(r"^(https?:|mailto:|tel:|data:|//)", v):
            return  # external / non-file — out of scope
        else:
            self.local_refs.append(v)


def check_html_file(rel):
    problems = []
    abspath = os.path.join(ROOT, rel)
    with open(abspath, encoding="utf-8") as fh:
        source = fh.read()

    p = SiteParser()
    p.feed(source)

    for err in p.tag_errors:
        problems.append(f"[html] {err}")
    for leftover in p.stack:
        problems.append(f"[html] <{leftover}> is never closed")

    base = os.path.dirname(abspath)
    for ref in p.local_refs:
        clean = ref.split("?", 1)[0].split("#", 1)[0]  # drop ?v=/query + fragment
        target = os.path.normpath(os.path.join(base, clean))
        if not os.path.isfile(target):
            problems.append(f"[asset] '{ref}' -> missing file {os.path.relpath(target, ROOT)}")

    for frag in p.anchor_refs:
        anchor = frag[1:]
        if anchor and anchor not in p.ids:
            problems.append(f"[anchor] '{frag}' has no matching id on this page")

    for err in p.jsonld_errors:
        problems.append(f"[seo] {err}")

    if rel in INDEXABLE_HTML_FILES:
        if not p.canonical:
            problems.append("[seo] missing <link rel=\"canonical\">")
        missing_og = REQUIRED_OG - p.meta.keys()
        for prop in sorted(missing_og):
            problems.append(f"[seo] missing <meta property=\"{prop}\">")
    else:
        if not p.robots_meta or "noindex" not in p.robots_meta:
            problems.append('[seo] expected <meta name="robots" content="noindex"> on a non-indexable page')

    if rel == "index.html":
        orgs = [b for b in p.jsonld_blocks if isinstance(b, dict) and b.get("@type") == "Organization"]
        if not orgs:
            problems.append("[seo] no Organization JSON-LD block found")
        else:
            missing_fields = [f for f in ORGANIZATION_JSONLD_REQUIRED_FIELDS if not orgs[0].get(f)]
            if missing_fields:
                problems.append(f"[seo] Organization JSON-LD missing field(s): {', '.join(missing_fields)}")

    return problems, p


def check_data_files():
    problems = []
    for rel, required_keys in DATA_FILES.items():
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            problems.append(f"[data] {rel} does not exist")
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as e:
            problems.append(f"[data] {rel} is not valid JSON: {e}")
            continue
        if not isinstance(data, list):
            problems.append(f"[data] {rel} should contain a JSON list, got {type(data).__name__}")
            continue
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                problems.append(f"[data] {rel}[{i}] should be an object, got {type(item).__name__}")
                continue
            missing = [k for k in required_keys if not item.get(k)]
            if missing:
                problems.append(f"[data] {rel}[{i}] missing required field(s): {', '.join(missing)}")
        print(f"{rel}: {len(data)} item(s)" + (" OK" if not problems else ""))
    return problems


def check_robots_and_sitemap():
    problems = []

    robots_path = os.path.join(ROOT, "robots.txt")
    if not os.path.isfile(robots_path):
        problems.append("[seo] robots.txt does not exist")
    else:
        text = open(robots_path, encoding="utf-8").read()
        if "Sitemap:" not in text:
            problems.append("[seo] robots.txt has no Sitemap: line")
        if "User-agent:" not in text:
            problems.append("[seo] robots.txt has no User-agent: line")

    sitemap_path = os.path.join(ROOT, "sitemap.xml")
    if not os.path.isfile(sitemap_path):
        problems.append("[seo] sitemap.xml does not exist")
    else:
        try:
            root = ET.parse(sitemap_path).getroot()
        except ET.ParseError as e:
            problems.append(f"[seo] sitemap.xml is not valid XML: {e}")
        else:
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            locs = [el.text for el in root.findall("sm:url/sm:loc", ns)]
            if not any(loc == "https://utahagile.org/" for loc in locs):
                problems.append("[seo] sitemap.xml has no <loc>https://utahagile.org/</loc> entry")
            print(f"sitemap.xml: {len(locs)} URL(s)")

    return problems


def main():
    total = 0
    parsed = {}
    for rel in HTML_FILES:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            print(f"::error::{rel} not found")
            total += 1
            continue
        problems, p = check_html_file(rel)
        parsed[rel] = (problems, p)
        print(f"\n{rel}: {len(p.local_refs)} local asset(s), "
              f"{len(p.anchor_refs)} in-page anchor(s), "
              f"{len(p.cross_page_refs)} cross-page anchor(s), {len(p.ids)} id(s)")

        missing_ids = REQUIRED_IDS.get(rel, set()) - p.ids
        for missing_id in sorted(missing_ids):
            problems.append(f"[script-id] required id '{missing_id}' not found "
                             f"(inline <script> logic depends on it via getElementById)")

    # Cross-page anchors (e.g. privacy.html linking to index.html#events) need
    # every page's id set gathered first, so resolve them in a second pass.
    for rel, (problems, p) in parsed.items():
        for target_file, anchor in p.cross_page_refs:
            target = parsed.get(target_file)
            if target is None:
                problems.append(f"[anchor] links to '{target_file}#{anchor}' but {target_file} wasn't checked")
                continue
            if anchor not in target[1].ids:
                problems.append(f"[anchor] '{target_file}#{anchor}' has no matching id on {target_file}")

    for rel, (problems, _p) in parsed.items():
        if problems:
            for msg in problems:
                print(f"::error file={rel}::{msg}")
            total += len(problems)
        else:
            print(f"  OK — no issues")

    print()
    data_problems = check_data_files()
    for msg in data_problems:
        print(f"::error::{msg}")
    total += len(data_problems)

    print()
    seo_problems = check_robots_and_sitemap()
    for msg in seo_problems:
        print(f"::error::{msg}")
    total += len(seo_problems)

    print("\n" + ("-" * 48))
    if total:
        print(f"FAILED: {total} problem(s) found")
        sys.exit(1)
    print("PASSED: all checks green")


if __name__ == "__main__":
    main()
