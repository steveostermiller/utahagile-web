/* Utah Agile — shared site behavior.
   Renders events from data/events.json wherever a [data-events] element
   exists, and past-meetup videos from data/videos.json wherever a
   [data-videos] element exists. Also injects a schema.org Event JSON-LD
   block matching whatever events actually render (see renderEventsSchema),
   for SEO/GEO — the static Organization JSON-LD lives directly in
   index.html's <head> instead, since it doesn't change at runtime. Header/
   footer are static markup directly in each page now that the site is a
   single page (index.html) plus privacy.html. */

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
  const thumb = ev.thumbnail
    ? `<img class="event__thumb" src="${ev.thumbnail}" alt="" loading="lazy">` : "";
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
      ${thumb}
    </article>`;
}

function eventToSchema(ev) {
  return {
    "@context": "https://schema.org",
    "@type": "Event",
    name: ev.title,
    startDate: ev.start,
    endDate: ev.end,
    eventAttendanceMode: "https://schema.org/OfflineEventAttendanceMode",
    eventStatus: "https://schema.org/EventScheduled",
    location: ev.location ? { "@type": "Place", name: ev.location } : undefined,
    image: ev.thumbnail,
    url: ev.url,
    organizer: { "@type": "Organization", name: "Utah Agile", url: "https://utahagile.org/" },
  };
}

// Reflects whatever the [data-events] container actually renders, so search/AI
// crawlers see the same events a visitor does — not the full unfiltered feed.
function renderEventsSchema(list) {
  let tag = document.getElementById("events-jsonld");
  if (!tag) {
    tag = document.createElement("script");
    tag.type = "application/ld+json";
    tag.id = "events-jsonld";
    document.head.appendChild(tag);
  }
  tag.textContent = JSON.stringify(list.map(eventToSchema));
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
    renderEventsSchema(list);
  });
}

function formatVideo(v) {
  return `
    <button type="button" class="video-thumb" data-embed="${v.embed}" aria-label="Play: ${v.title}">
      <span class="video-thumb__img"><img src="${v.thumbnail}" alt=""><span class="video-thumb__play" aria-hidden="true">&#9658;</span></span>
      <span class="video-thumb__title">${v.title}</span>
    </button>`;
}

async function renderVideos() {
  const containers = document.querySelectorAll("[data-videos]");
  if (!containers.length) return;
  let videos = [];
  try {
    const res = await fetch("data/videos.json", { cache: "no-store" });
    videos = await res.json();
  } catch (e) {
    console.error("Could not load videos.json", e);
  }
  containers.forEach(c => {
    const limit = parseInt(c.dataset.videos, 10) || videos.length;
    c.innerHTML = videos.slice(0, limit).map(formatVideo).join("");
  });
}

document.addEventListener("DOMContentLoaded", renderEvents);
document.addEventListener("DOMContentLoaded", renderVideos);
