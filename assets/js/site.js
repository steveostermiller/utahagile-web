/* Utah Agile — shared site behavior.
   Renders events from data/events.json wherever a [data-events] element
   exists. Header/footer are static markup directly in each page now that
   the site is a single page (index.html) plus privacy.html. */

const MEETUP_URL = "https://www.meetup.com/utahagile/";

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
         check our <a href="${MEETUP_URL}">Meetup page</a> or subscribe below.</p>`;
  });
}

document.addEventListener("DOMContentLoaded", renderEvents);
