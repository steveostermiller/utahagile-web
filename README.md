# Utah Agile website

Static replacement for the Wix site (utahagile.org). No paid hosting, no manual
event entry, no backend to maintain.

- **Pages** — a single page, `index.html` (everything is an anchor section:
  Events, About, Team, Get Involved, Sponsorship), plus a standalone
  `privacy.html`. Plain static HTML/CSS, no build step.
- **Events** — pulled automatically from the Meetup iCal feed by
  `scripts/build_events.py`, on a schedule via GitHub Actions. No admin area.
- **Newsletter** — not yet live. The Subscribe button/section is commented out
  in `index.html` until a MailerLite embed is added (see below).

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
