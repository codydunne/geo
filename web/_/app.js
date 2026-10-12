// Page wiring: everything location-related is in geo.js so it can be tested.
import { DEFAULT_Z, canonical, fill, fmt, inRegion, inputOf, parse, trunc6 } from "./geo.js";

/** @typedef {import("./geo.js").State} State */
/** @typedef {import("./geo.js").MapData} MapData */

/** Leaflet's UMD global; untyped on purpose (no @types dependency). @type {any} */
const L = /** @type {any} */ (globalThis).L;
const $ = (/** @type {string} */ id) => /** @type {HTMLElement} */ (document.getElementById(id));
const msg = $("msg");
const list = $("list");
const featured = $("featured");
const filter = /** @type {HTMLInputElement} */ ($("filter"));
const q = /** @type {HTMLInputElement} */ ($("q"));
const showDisabled = /** @type {HTMLInputElement} */ ($("show-disabled"));
const showRegions = /** @type {HTMLInputElement} */ ($("show-regions"));

/** @type {MapData} */
const data = await (await fetch("_/maps.json")).json();
/** @type {State} */
let st = {};
/** @type {any} */
let map;
/** @type {any} */
let pin;

/** @param {string} text @param {"error" | "ok"} [kind] */
function say(text, kind = "error") {
  msg.textContent = text;
  msg.className = `message ${kind}`;
  msg.hidden = !text;
}

/** localStorage can throw (privacy modes, blocked storage); it is only a cache. */
const cache = {
  /** @param {string} k */
  get(k) {
    try {
      return JSON.parse(localStorage.getItem(k) ?? "null");
    } catch {
      return null;
    }
  },
  /** @param {string} k @param {unknown} v */
  set(k, v) {
    try {
      localStorage.setItem(k, JSON.stringify(v));
    } catch {
      /* cache only */
    }
  },
};

/**
 * One lookup per address, ever, per browser: the result is cached and the canonical
 * URL then carries coordinates, so reloads never ask again (usage policy).
 * Geocoders are tried in order; Nominatim matches names exactly ("Trader Joes" misses
 * "Trader Joe's"), so the fuzzy Photon runs only when it finds nothing or fails.
 * @param {string} a
 * @returns {Promise<{lat: string, lon: string} | null>}
 */
async function geocode(a) {
  const key = `geo:a:${a}`;
  const hit = cache.get(key);
  if (hit) return hit;
  let err;
  for (const tpl of data.geocoders ?? []) {
    try {
      const res = await fetch(tpl.replace("{a}", encodeURIComponent(a)), {
        headers: { Accept: "application/json" },
      });
      if (!res.ok) throw new Error(`geocoder HTTP ${res.status}`);
      const j = await res.json();
      // Nominatim: [{lat, lon}] as decimal strings; Photon: GeoJSON [lon, lat] numbers.
      const c = j.features?.[0]?.geometry.coordinates;
      const r = c ? { lat: c[1], lon: c[0] } : j[0];
      if (!r) continue;
      // Same truncation rule as typed input.
      const out = { lat: trunc6(String(r.lat)), lon: trunc6(String(r.lon)) };
      cache.set(key, out);
      return out;
    } catch (e) {
      err = e;
    }
  }
  if (err) throw err;
  return null;
}

function updateUrl() {
  const url = canonical(st);
  if (url !== location.pathname + location.search + location.hash) history.replaceState(null, "", url);
}

/**
 * A disabled map (dead service, kept so its published id still resolves) stays a link
 * so it can still be tried, but is marked as broken.
 * @param {import("./geo.js").MapDef} d @param {string} text @param {string} [cls]
 */
function link(d, text, cls = "") {
  const el = document.createElement("a");
  el.className = d.disabled ? `${cls} disabled`.trim() : cls;
  el.textContent = d.disabled ? `${text} (disabled)` : text;
  el.href = fill(d.u, st);
  el.rel = "noopener";
  if (d.disabled) el.title = "This service appears to no longer work";
  return el;
}

function renderFeatured() {
  const d = st.m ? data.maps.find((x) => x.id === st.m) : undefined;
  featured.hidden = !d || st.lat === undefined;
  if (st.m && !d) say(`Unknown map "${st.m}"; showing all maps.`);
  if (!d || featured.hidden) return;
  featured.replaceChildren();
  const name = document.createElement("strong");
  name.textContent = d.n;
  featured.append(name, link(d, "Open", d.disabled ? "" : "button"));
}

function renderList() {
  list.replaceChildren();
  if (st.lat === undefined) return;
  /** @type {Map<string, HTMLElement>} */
  const groups = new Map();
  for (const d of data.maps) {
    if (d.disabled && !showDisabled.checked) continue;
    if (!showRegions.checked && !inRegion(d, st, data.regions)) continue;
    let ul = groups.get(d.c);
    if (!ul) {
      const det = document.createElement("details");
      det.className = "group";
      det.open = true;
      det.dataset.c = d.c.toLowerCase();
      const sum = document.createElement("summary");
      sum.textContent = d.c + " ";
      const count = document.createElement("span");
      count.className = "count";
      sum.append(count);
      ul = document.createElement("ul");
      det.append(sum, ul);
      list.append(det);
      groups.set(d.c, ul);
    }
    const li = document.createElement("li");
    li.dataset.n = d.n.toLowerCase();
    li.append(link(d, d.n, d.n.includes("★") ? "" : "dim"));
    ul.append(li);
  }
  applyFilter();
}

function applyFilter() {
  const f = filter.value.trim().toLowerCase();
  $("filter-clear").hidden = !filter.value;
  for (const det of /** @type {NodeListOf<HTMLDetailsElement>} */ (list.querySelectorAll("details"))) {
    const catHit = (det.dataset.c ?? "").includes(f);
    let shown = 0;
    for (const li of /** @type {NodeListOf<HTMLLIElement>} */ (det.querySelectorAll("li"))) {
      li.hidden = !!f && !catHit && !(li.dataset.n ?? "").includes(f);
      if (!li.hidden) shown++;
    }
    det.hidden = shown === 0;
    const total = det.querySelectorAll("li").length;
    /** @type {HTMLElement} */ (det.querySelector(".count")).textContent = f ? `(${shown}/${total} shown)` : `(${total})`;
  }
}

function renderMap() {
  if (st.lat === undefined || st.lon === undefined) {
    // Location cleared: drop the pin but leave the view where it is.
    pin?.remove();
    pin = undefined;
    return;
  }
  const ll = [Number(st.lat), Number(st.lon)];
  const z = Math.min(st.z ?? DEFAULT_Z, 19);
  if (!pin) {
    pin = L.marker(ll, { draggable: true, autoPan: true, keyboard: true, title: "Drag to move" }).addTo(map);
    pin.on("dragend", () => {
      const p = pin.getLatLng();
      st = { ...st, lat: fmt(p.lat), lon: fmt(L.Util.wrapNum(p.lng, [-180, 180], true)) };
      update(false);
    });
  } else pin.setLatLng(ll);
  // The label comes from the URL: always text, never HTML (Leaflet uses innerHTML for strings).
  if (st.a) pin.bindPopup(document.createTextNode(st.a)).openPopup();
  else pin.unbindPopup();
  map.setView(ll, z);
}

/** @param {boolean} [moveMap] */
function update(moveMap = true) {
  updateUrl();
  $("where").textContent =
    st.lat !== undefined ? `${st.a ? st.a + " · " : ""}${st.lat}, ${st.lon}` : "Click the map to drop a pin, or enter a location above.";
  // The current location is the field's value, not its placeholder, so it can be edited; don't clobber typing.
  if (document.activeElement !== q) q.value = st.lat !== undefined ? `${st.lat},${st.lon}` : "";
  $("q-clear").hidden = !q.value;
  if (moveMap) renderMap();
  renderFeatured();
  renderList();
}

/** Bumped per load, so a slow lookup cannot overwrite a newer location. */
let generation = 0;

/** @param {State} next */
async function load(next) {
  const gen = ++generation;
  say("");
  st = next;
  if (st.lat === undefined && st.a) {
    say(`Looking up "${st.a}"…`, "ok");
    try {
      const hit = await geocode(st.a);
      if (gen !== generation) return;
      if (!hit) return say(`No match for "${st.a}".`);
      st = { ...st, ...hit };
      say("");
    } catch (e) {
      if (gen !== generation) return;
      return say(`Address lookup failed (${e instanceof Error ? e.message : e}).`);
    }
  }
  update();
}

// --- wiring ---

// With no location yet, show Cambridge, MA at greater-Boston zoom; a click drops the first pin.
map = L.map("map", { worldCopyJump: true }).setView([42.3736, -71.1097], 10);
map.on("click", (/** @type {any} */ e) => {
  if (st.lat !== undefined) return; // after the first pin, move it by dragging
  load({ lat: fmt(e.latlng.lat), lon: fmt(L.Util.wrapNum(e.latlng.lng, [-180, 180], true)), z: map.getZoom(), m: st.m });
});
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);
map.on("zoomend", () => {
  if (st.lat === undefined || map.getZoom() === Math.min(st.z ?? DEFAULT_Z, 19)) return;
  st = { ...st, z: map.getZoom() };
  update(false);
});

$("go").addEventListener("submit", (e) => {
  e.preventDefault();
  const v = q.value.trim();
  if (!v) return;
  // Anything we cannot read as a location is an address: `a=` is the only geocoding trigger.
  const next = parse(v, data) ?? parse(`a=${encodeURIComponent(v)}`, data);
  if (next) load({ ...next, m: next.m ?? st.m });
  q.blur(); // lets update() show the resolved coordinates
});

// Resets the location (keeping any chosen map); the view stays put, so a click drops a new pin there.
q.addEventListener("input", () => ($("q-clear").hidden = !q.value));
$("q-clear").addEventListener("click", () => {
  q.value = "";
  load({ m: st.m });
  q.focus();
});

filter.addEventListener("input", applyFilter);
showDisabled.addEventListener("change", renderList);
showRegions.addEventListener("change", renderList);
$("filter-clear").addEventListener("click", () => {
  filter.value = "";
  applyFilter();
  filter.focus();
});

$("copy").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(location.href);
    say("Link copied.", "ok");
  } catch {
    say("Copy failed; copy the address bar instead.");
  }
});

if (navigator.share) {
  const share = $("share");
  share.hidden = false;
  share.addEventListener("click", () => navigator.share({ title: document.title, url: location.href }).catch(() => {}));
}

$("locate").addEventListener("click", () => {
  if (!navigator.geolocation) return say("This browser has no geolocation.");
  say("Finding your location…", "ok");
  const gen = generation;
  navigator.geolocation.getCurrentPosition(
    (p) => {
      if (gen === generation) load({ lat: fmt(p.coords.latitude), lon: fmt(p.coords.longitude), z: st.z, m: st.m });
    },
    (err) => {
      if (gen === generation) say(`Location unavailable (${err.message}).`);
    },
    { enableHighAccuracy: true, timeout: 15000 },
  );
});

const raw = inputOf(location);
const initial = raw ? parse(raw, data) : {};
if (initial) load(initial);
else say(`Could not read a location from "${raw}".`);
