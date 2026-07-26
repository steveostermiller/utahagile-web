# Utah Agile website

Static replacement for the Wix site (utahagile.org). No paid hosting, no manual
event entry, no backend to maintain.

- **Pages** — a single page, `index.html` (everything is an anchor section:
  Events, About, Team, Get Involved, Sponsorship), plus a standalone
  `privacy.html`. Plain static HTML/CSS, no build step.
- **Events** — pulled automatically from the Meetup iCal feed by
  `scripts/build_events.py`, on a schedule via GitHub Actions. No admin area.
- **Past meetup videos** — the 2 most recent YouTube uploads are pulled
  automatically by `scripts/build_videos.py`, on the same schedule. No admin
  area; upload to YouTube and the site updates itself.
- **Newsletter** — not yet live. The Subscribe button/section is commented out
  in `index.html` until a MailerLite embed is added (see below).
- **Checks** — every push/PR runs `scripts/check_site.py` and the offline
  unit tests (see below), which catch broken HTML, missing local
  assets/images, dead anchor links, malformed `data/*.json`, and broken
  Meetup/YouTube feed-parsing logic before they reach the live site. A
  Lighthouse accessibility gate also runs on every push/PR, and a weekly job
  checks that external links (sponsors, socials, LinkedIn) still resolve.

---

## Local preview

No build step. From the project root:

```bash
python3 -m http.server 8000
# open http://localhost:8000
```

Refresh events locally with:

```bash
python3 scripts/build_events.py
python3 scripts/build_videos.py
```

---

## How events work

1. `.github/workflows/update-events.yml` runs `scripts/build_events.py` hourly.
2. The script reads `https://www.meetup.com/utahagile/events/ical/` and writes
   `data/events.json`.
3. The site renders that JSON client-side (`assets/js/site.js`). Any element with
   a `data-events` attribute becomes an events list (`data-events="3"` limits to 3).

**You never touch the site to update events** — just manage them in Meetup.

---

## How past-meetup videos work

1. `.github/workflows/update-videos.yml` runs `scripts/build_videos.py` hourly.
2. The script reads the Utah Agile YouTube channel's public Atom feed
   (`https://www.youtube.com/feeds/videos.xml?channel_id=...`, no API key
   needed) and writes the 2 most recent uploads to `data/videos.json`, using
   YouTube's hosted thumbnail for each.
3. The site renders that JSON client-side. Any element with a `data-videos`
   attribute becomes a video-thumbnail grid (`data-videos="2"` limits to 2).

**You never touch the site to update past-meetup videos** — just upload to
YouTube. (The "Past Conference Events" videos below it are still hand-picked
Vimeo embeds in `index.html`, since those are a fixed historical set, not an
ongoing feed.)

---

## Checks (CI)

1. `.github/workflows/checks.yml` runs `scripts/check_site.py` on every push
   and pull request — no network calls, pure stdlib, so it's fast and never
   flaky.
2. It validates `index.html`, `privacy.html`, and `404.html` for: unclosed/stray
   HTML tags, local `href`/`src` references that point at a missing file, and
   anchor links (`#section` and cross-page `index.html#section`, the pattern
   `privacy.html`/`404.html` use) that don't resolve to a real `id`.
3. It also validates `data/events.json` and `data/videos.json` are present,
   valid JSON, a list, and that every item has its required fields — this is
   what would catch Meetup or YouTube silently changing their feed format and
   `build_events.py`/`build_videos.py` writing out garbage.
4. `tests/` has offline `unittest` tests (`test_build_events.py`,
   `test_build_videos.py`) that feed small fixture iCal/Atom documents
   through the real parsing functions — no network calls, so they're fast
   and never flaky. These are what actually catch Meetup or YouTube changing
   their feed's shape, since `check_site.py` only validates the *output*
   JSON, not the parsing logic that produced it. Also cover the "refuse to
   overwrite a good file with an empty result" guard in both scripts
   (`save()` in `build_videos.py`, `looks_like_ical()` in `build_events.py`)
   — a feed that starts returning garbage now fails the build loudly instead
   of silently blanking a section of the live site.

Run everything locally with:

```bash
python3 scripts/check_site.py
python3 -m unittest discover -s tests -v
```

A failing check fails the GitHub Actions run but does **not** block `main`
from deploying by itself (there's no branch protection requiring it to pass)
— it's a visible red X in the Actions tab, not a hard gate, unless you want
to turn that on later.

---

## Accessibility check (Lighthouse)

`.github/workflows/lighthouse.yml` runs on every push/PR. It serves the
checked-out files with `python3 -m http.server` (same as local preview above)
and runs Lighthouse against `index.html`, `privacy.html`, and `404.html`.
Only the **accessibility** category is a hard gate — `.lighthouserc.json`
fails the build if any page scores below 0.9 (contrast, missing alt text,
ARIA issues, etc.). Performance/SEO/best-practices scores are collected and
uploaded but don't fail the build; this check is scoped to accessibility
specifically, not general page-speed policing.

Run it locally (needs Node — not otherwise required by this repo):

```bash
npx @lhci/cli@0.14.x autorun
```

---

## External link check (weekly)

`.github/workflows/check-links.yml` runs `scripts/check_links.py` every
Monday (and on demand via workflow_dispatch) to catch sponsor/social/profile
links that have gone dead. It's deliberately **not** part of the push/PR
checks above, since network requests to third-party sites are flaky.

It only hard-fails on signals that actually mean "broken" — 404/410, 5xx, or
a connection error. Codes like 403/429/999 (LinkedIn blocks almost all
scripted requests this way, regardless of whether the profile is real) are
reported as informational "BLOCKED," not failures — otherwise this check
would cry wolf on the same handful of LinkedIn links every week and train you
to ignore it.

Run it locally with `python3 scripts/check_links.py`.

---

## Turn on the newsletter (MailerLite)

The Subscribe section is currently hidden (commented out) in `index.html` since
no signup form exists yet. To launch it:

1. Create a free MailerLite account.
2. **Import subscribers**: use the CSV you exported from Wix
   (*Marketing & SEO → Contacts → Export*). MailerLite → Subscribers → Import.
3. Build an **Embedded form** in MailerLite, copy its HTML snippet.
4. In `index.html`, un-comment the `<!-- Subscribe (hidden until MailerLite is
   built) -->` section and the Subscribe buttons in the nav/hero, and paste the
   embed snippet in place of the `#mailerlite-form` placeholder.
5. Update `privacy.html` — the "What personal data we collect" section
   currently states no data is collected, since the form doesn't exist yet.
   Once the form is live, update that section (and the related "how long we
   retain," "where we send," and "automated decision making" sections) to
   describe the real behavior.

---

## Deploy (free hosting)

**GitHub Pages:**
Repo → **Settings → Pages → Build and deployment → Source: "Deploy from a branch"**
→ Branch **`main`**, folder **`/ (root)`** → **Save**. Publishes at
`https://steveostermiller.github.io/utahagile-web/`, and auto-redeploys on every
push (including the hourly events commit). A `.nojekyll` file disables Jekyll.

### Point the domain (Squarespace registrar)

Once the site is live on Pages, in Squarespace **Domains → DNS settings**, replace
the current Wix records with GitHub Pages' records. Do this only after the new
site looks right — it's the cutover.

**Order of operations:** export Wix contacts → import to MailerLite (when ready)
→ verify new site → repoint DNS → cancel Wix.

---

## Still to do

- [ ] Add MailerLite embed and un-hide the Subscribe section (above)
- [ ] Update `privacy.html` once MailerLite goes live (above)
- [ ] Verify a real event renders correctly (schedule one on Meetup)
