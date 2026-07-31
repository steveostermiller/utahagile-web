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
- **Newsletter** — live via Sender.net (see below). The signup form is
  cookie-gated behind a consent banner, since Sender's embed script sets
  cookies for anyone it loads for.
- **Analytics** — Cloudflare Web Analytics, cookie-free, site-wide (see below).
- **SEO/GEO** — `robots.txt`, `sitemap.xml`, `llms.txt`, Open Graph/Twitter
  tags, canonical links, and schema.org structured data (see below).
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

**Venue and photo enrichment:** Meetup's iCal feed doesn't include a venue or
event photo, even when both are public on the event page (confirmed by
inspecting the raw feed directly). So for each event (up to `ENRICH_LIMIT`,
currently 10), the script also fetches that event's own Meetup page and reads
the `schema.org/Event` JSON-LD block embedded there, which does have both. This
is best-effort: if a fetch fails or Meetup changes that markup, the event still
ships with its reliable iCal fields (title/date/RSVP link) — it just won't have
a `location` or `thumbnail`. As long as the venue and a photo are public on the
Meetup event itself, this picks them up automatically — there's no specific
iCal field to fill in (Meetup's iCal feed doesn't carry either one at all,
confirmed by inspecting the raw feed directly, which is why this reads the
event page instead).

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
5. It also validates SEO/GEO basics (see that section below): `robots.txt`
   and `sitemap.xml` exist and are well-formed, `index.html`/`privacy.html`
   have canonical links and required Open Graph properties, `index.html`'s
   Organization JSON-LD is present and valid, and `404.html` is noindex.

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

## How the newsletter works

The Subscribe section (`#subscribe` in `index.html`) uses **Sender.net**, not
MailerLite — MailerLite's free plan caps out at 250 subscribers, below the
400+ already imported from Wix, while Sender.net's free plan covers up to
2,500. Subscribers collect first name, last name, and email; opt-in is
single-step (Sender's free plan doesn't offer double opt-in).

**Cookie consent gate:** Sender's embed script (`universal.js`) sets several
cookies for anyone it loads for (`sender_subscriber_id`, `sender_country`,
etc. — inspecting the script directly confirmed this), not just people who
submit the form. Since the site otherwise sets no cookies at all, the script
is never loaded by default:

1. On first visit, a banner at the bottom of the page asks the visitor to
   Accept or Decline.
2. The Subscribe section itself shows a short explanation + "Accept & show
   form" button instead of the real form until a choice is made.
3. Only after Accept does the page inject Sender's script and reveal the
   actual embedded form (`data-sender-form-id="erkDOL"`). Decline hides the
   banner and leaves the form hidden, but the visitor can still change their
   mind later via that same "Accept & show form" button — or email
   `subscribe@utahagile.org` to be added manually, with zero cookies involved on
   their end. That mailto fallback is the only cookie-free way to sign up;
   there's no way to submit the form itself without accepting Sender's
   script (see the "cookie-free integration" dead end noted in git history —
   Sender's real API requires a private key that can't safely live in
   client-side HTML on a backend-less static site).
4. The choice is remembered in `localStorage` (`cookieConsent`), so returning
   visitors aren't asked again.

All of this logic lives in a `<script>` block at the bottom of `index.html`
(not `site.js`, since it's specific to this one page/section). `privacy.html`
documents the exact cookies and the consent mechanism under "Cookies" and
"What personal data we collect."

**Resolved gotcha:** the form initially rendered empty when tested — script
loaded, no console errors, but zero network requests to Sender's API. Turned
out the form was still a draft in Sender's dashboard; publishing it fixed
rendering immediately, confirmed live. If this ever recurs, check the form's
publish state in Sender.net before assuming it's a code or domain issue.

---

## Analytics

Cloudflare Web Analytics, added to all three pages (`index.html`,
`privacy.html`, `404.html`) via a `<script type="module">` beacon tag before
`</body>`. Free, no DNS/nameserver changes needed, and — per Cloudflare's own
docs — uses no cookies, localStorage, or IP/user-agent fingerprinting, so it
needed no consent-gate treatment (unlike the Sender.net newsletter embed
above). View traffic in the Cloudflare dashboard under Web Analytics for
`utahagile.org`. `privacy.html`'s "Analytics" section documents this.

---

## SEO & GEO

- **`robots.txt`** — allows all crawlers, including AI ones (GPTBot,
  ClaudeBot, Google-Extended, etc.) — a deliberate choice, since the goal is
  visibility in both traditional search and AI-generated answers (GEO). Points
  to `sitemap.xml`.
- **`sitemap.xml`** — lists `index.html` and `privacy.html` (not `404.html`,
  which is explicitly `<meta name="robots" content="noindex">` instead — an
  error page shouldn't compete in search results). `lastmod` dates are set by
  hand when the page's content meaningfully changes, not automated.
- **`llms.txt`** — an emerging (unofficial, not yet standardized) convention:
  a plain-Markdown summary of the org for AI systems to consume directly,
  similar in spirit to `robots.txt`/`sitemap.xml`.
- **Open Graph / Twitter Card tags + canonical links** — on `index.html` and
  `privacy.html`, using `assets/img/hero.jpg` (1600×900) as the share image.
- **schema.org structured data (JSON-LD)** — an `Organization` block is
  static, directly in `index.html`'s `<head>` (name, logo, social links via
  `sameAs`). An `Event` block is generated dynamically by
  `renderEventsSchema()` in `site.js`, injected into `<head>` alongside
  whatever `renderEvents()` actually renders — so crawlers see the same
  events a visitor does, not the full unfiltered feed, and it can never drift
  out of sync with the visible page.

`scripts/check_site.py` validates all of the above (canonical links, required
Open Graph properties, the Organization JSON-LD's required fields, `404.html`
being noindex, and `robots.txt`/`sitemap.xml` existing and being well-formed)
on every push/PR — see "Checks (CI)" above.

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

**Order of operations:** export Wix contacts → import to Sender.net (when ready)
→ verify new site → repoint DNS → cancel Wix.

---

## Still to do

- [ ] Verify the Sender.net form actually renders on the live utahagile.org
      domain (see "Known gap" above — untestable on localhost)
- [ ] Verify a real event renders correctly (schedule one on Meetup)
