# Utah Agile website

Static replacement for the Wix site (utahagile.org). No paid hosting, no manual
event entry, no backend to maintain.

- **Pages** — plain static HTML/CSS. Edit the `.html` files directly.
- **Events** — pulled automatically from the Meetup iCal feed by
  `scripts/build_events.py`, on a schedule via GitHub Actions. No admin area.
- **Newsletter** — an embedded MailerLite form (no server needed).

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

## Finish the newsletter (MailerLite)

1. Create a free MailerLite account.
2. **Import subscribers**: use the CSV you exported from Wix
   (*Marketing & SEO → Contacts → Export*). MailerLite → Subscribers → Import.
3. Build an **Embedded form** in MailerLite, copy its HTML snippet.
4. Paste it into `index.html`, replacing the `#mailerlite-form` placeholder block
   (search for `MAILERLITE EMBED GOES HERE`).

---

## Deploy (free hosting)

**GitHub Pages (recommended — everything stays in one place):**
Repo → **Settings → Pages → Build and deployment → Source: "Deploy from a branch"**
→ Branch **`main`**, folder **`/ (root)`** → **Save**. Publishes at
`https://steveostermiller.github.io/utahagile-web/` in ~1 minute, and auto-redeploys
on every push (including the hourly events commit). Paths are relative, so it works at
this subpath and at the root custom domain later. A `.nojekyll` file disables Jekyll.

**Alternative — Cloudflare Pages:** Workers & Pages → Create → **Pages → Connect to Git**
(not "Worker"), framework preset "None", build command empty, output directory `/`.

### Point the domain (Squarespace registrar)

Once the site is live on Pages, in Squarespace **Domains → DNS settings**, replace
the current Wix records with the host's records (Cloudflare/GitHub provide the exact
A / CNAME values). Do this only after the new site looks right — it's the cutover.

**Order of operations:** export Wix contacts → import to MailerLite → verify new site
→ repoint DNS → cancel Wix.

---

## Still to do

- [ ] Add MailerLite embed (above)
- [ ] Match exact brand colors + drop in the logo (`assets/css/style.css`, `assets/img/`)
- [ ] Pull remaining Explore pages (SEUs, Network, Certification, etc.)
- [ ] Confirm/replace social + Slack links in `assets/js/site.js`
- [ ] Verify a real event renders correctly (schedule one on Meetup)
