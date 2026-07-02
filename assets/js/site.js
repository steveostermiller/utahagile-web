/* Utah Agile — shared site behavior.
   Injects the header + footer on every page (so you edit them in ONE place),
   handles the mobile menu, and renders events from data/events.json. */

const NAV = [
  { label: "Events",       href: "events.html" },
  { label: "About",        href: "about.html" },
  { label: "Speakers",     href: "speakers.html" },
  { label: "Sponsorship",  href: "sponsorship.html" },
  { label: "Jobs",         href: "jobs.html" },
  { label: "Volunteer",    href: "volunteer.html" },
];

const SOCIAL = {
  meetup:   "https://www.meetup.com/utahagile",
  linkedin: "https://www.linkedin.com/company/utah-agile",
  youtube:  "https://www.youtube.com/@utahagile",
  twitter:  "https://twitter.com/utahagile",
  facebook: "https://www.facebook.com/utahagile",
  slack:    "#", // TODO: Slack invite link
};

function renderHeader() {
  const el = document.getElementById("site-header");
  if (!el) return;
  el.innerHTML = `
    <div class="container nav">
      <a class="nav__brand" href="index.html" aria-label="Utah Agile home">
        <img src="assets/img/logo.png" alt="Utah Agile"
             onerror="this.replaceWith(document.createTextNode('Utah Agile'))">
      </a>
      <button class="nav__toggle" aria-label="Menu" aria-expanded="false">&#9776;</button>
      <nav class="nav__links">
        ${NAV.map(n => `<a href="${n.href}">${n.label}</a>`).join("")}
        <a class="btn btn--primary" href="index.html#subscribe">Subscribe</a>
      </nav>
    </div>`;
  const toggle = el.querySelector(".nav__toggle");
  const links = el.querySelector(".nav__links");
  toggle.addEventListener("click", () => {
    const open = links.classList.toggle("open");
    toggle.setAttribute("aria-expanded", String(open));
  });
}

function renderFooter() {
  const el = document.getElementById("site-footer");
  if (!el) return;
  const year = new Date().getFullYear();
  el.innerHTML = `
    <div class="container site-footer__grid">
      <div>
        <strong>Utah Agile</strong><br>
        A 501(c)6 nonprofit uniting Utah's agile community.<br>
        <a href="mailto:info@agileutah.org">info@agileutah.org</a>
        <div class="social">
          <a href="${SOCIAL.meetup}">Meetup</a>
          <a href="${SOCIAL.linkedin}">LinkedIn</a>
          <a href="${SOCIAL.youtube}">YouTube</a>
          <a href="${SOCIAL.twitter}">Twitter</a>
          <a href="${SOCIAL.facebook}">Facebook</a>
        </div>
      </div>
      <div>
        &copy; ${year} Utah Agile<br>
        <a href="privacy.html">Privacy &amp; GDPR</a>
      </div>
    </div>`;
}

/* ---------- Events (from data/events.json, generated from Meetup) ---------- */
function formatEvent(ev) {
  const start = new Date(ev.start);
  const month = start.toLocaleString("en-US", { month: "short" });
  const day = start.getDate();
  const when = start.toLocaleString("en-US", {
    weekday: "long", month: "long", day: "numeric",
    hour: "numeric", minute: "2-digit", timeZoneName: "short",
  });
  const loc = ev.location ? ` &middot; ${ev.location}` : "";
  return `
    <article class="event">
      <div class="event__date">
        <div class="m">${month}</div>
        <div class="d">${day}</div>
      </div>
      <div class="event__body">
        <h3><a href="${ev.url}">${ev.title}</a></h3>
        <p class="event__meta">${when}${loc}</p>
        <a class="btn btn--primary" href="${ev.url}">RSVP on Meetup</a>
      </div>
    </article>`;
}

async function renderEvents() {
  const containers = document.querySelectorAll("[data-events]");
  if (!containers.length) return;
  let events = [];
  try {
    const res = await fetch("data/events.json", { cache: "no-store" });
    events = await res.json();
  } catch (e) {
    console.error("Could not load events.json", e);
  }
  const now = Date.now();
  const upcoming = events
    .filter(e => new Date(e.end || e.start).getTime() >= now)
    .sort((a, b) => new Date(a.start) - new Date(b.start));

  containers.forEach(c => {
    const limit = parseInt(c.dataset.events, 10) || upcoming.length;
    const list = upcoming.slice(0, limit);
    c.innerHTML = list.length
      ? list.map(formatEvent).join("")
      : `<p class="events-empty">No upcoming events scheduled right now &mdash;
         check our <a href="${SOCIAL.meetup}">Meetup page</a> or subscribe below.</p>`;
  });
}

document.addEventListener("DOMContentLoaded", () => {
  renderHeader();
  renderFooter();
  renderEvents();
});
