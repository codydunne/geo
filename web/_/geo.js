// Pure location logic shared by the page and `node --test`: no DOM access here.

/**
 * @typedef {{lat?: string, lon?: string, z?: number, m?: string, a?: string, tile?: string}} State
 *   lat/lon stay strings so the digits a user typed survive canonicalization.
 *   tile: comma-separated tile layer ids (a basemap and any overlays).
 * @typedef {{id: string, n: string, c: string, u: string, p?: string[], r?: (string | number[])[], s?: string[], f?: boolean, star?: boolean, disabled?: boolean}} MapDef
 *   f: the service allows being shown in an iframe (probed by the collector).
 * @typedef {{id: string, n: string, c: "Basemaps" | "Overlays", u: string, o: Record<string, unknown>, r?: (string | number[])[], s?: string[], star?: boolean, disabled?: boolean}} TileDef
 *   u: a Leaflet tile URL template; o: its TileLayer options.
 * @typedef {{v: number, geocoders?: string[], maps: MapDef[], tiles: TileDef[], regions: Record<string, number[][]>}} MapData
 */

export const BASE = "/geo/";
export const DEFAULT_Z = 15;
const NUM = String.raw`[-+]?\d+(?:\.\d+)?`;

// Built in rather than in maps.json so the documented input forms never depend on
// generated data. Named groups: lat, lon, and one of z (zoom), m (metres of view).
const BUILTIN = [
  // Google Maps: /@lat,lon,15z | /@lat,lon,1234m | place/lat,lon | ?query= | ?center= | ?ll= | ?q=
  String.raw`google\.[^/]+/maps/.*@(?<lat>${NUM}),(?<lon>${NUM})(?:,(?:(?<z>[\d.]+)z|(?<m>[\d.]+)m))?`,
  String.raw`google\.[^/]+/maps/place/(?<lat>${NUM}),\s*(?<lon>${NUM})`,
  String.raw`google\.[^/]+/maps.*[?&](?:query|center|ll|q|destination)=(?<lat>${NUM}),\s*(?<lon>${NUM})(?:.*[?&]zoom=(?<z>\d+))?`,
].map((p) => new RegExp(p));

// Generic fallbacks used by many providers. Tried after the per-service patterns in
// maps.json: a service may put lon first in the same shape (OpenSnowMap's #map=z/lon/lat).
const GENERIC = [
  String.raw`[?&#/]map=(?<z>[\d.]+)/(?<lat>${NUM})/(?<lon>${NUM})`,
  String.raw`[?&]center=(?<lat>${NUM}),\s*(?<lon>${NUM})(?:.*[?&]zoom=(?<z>[\d.]+))?`,
].map((p) => new RegExp(p));

/** @param {string} s */
function decode(s) {
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
}

/** Format a computed coordinate: 6 decimals, trailing zeros dropped. @param {number} x */
export function fmt(x) {
  return x.toFixed(6).replace(/\.?0+$/, "").replace(/^-0$/, "0");
}

/**
 * Keep the digits as entered but cut (not round) past 6 decimals.
 * @param {string} s
 */
export function trunc6(s) {
  const m = s.trim().match(/^([-+]?)0*(\d+)(?:\.(\d*))?$/);
  if (!m) return fmt(Number(s));
  const frac = (m[3] ?? "").slice(0, 6);
  const out = (m[1] === "-" ? "-" : "") + m[2] + (frac ? "." + frac : "");
  return /^-0(\.0*)?$/.test(out) ? out.slice(1) : out;
}

/**
 * Zoom from a regex match's named groups.
 * @param {Record<string, string | undefined>} g
 * @returns {number | undefined}
 */
function zoomOf(g) {
  if (g.z) return Math.round(Number(g.z));
  // Google's metres-of-view form; constants from OpenSwitchMaps' Google parser (MIT).
  if (g.m) return Math.round(-1.4446 * Math.log(Number(g.m)) + 26.858);
  return undefined;
}

/** GeoHack scale -> OSM zoom, per mediawiki.org/wiki/GeoHack. @param {number} scale */
export const scaleToZoom = (scale) => 18 - Math.round(Math.log2(scale / 1693));

/**
 * Degrees from D[,M[,S]] parts plus a hemisphere letter.
 * @param {(string | undefined)[]} parts
 * @param {string | undefined} hemi
 */
function dms(parts, hemi) {
  const [d, m, s] = parts.map((x) => Number(x ?? 0));
  const v = d + m / 60 + s / 3600;
  return /[SW]/i.test(hemi ?? "") ? -v : v;
}

/** @param {string} head @returns {State | null} */
function parseGeoHack(head) {
  const pm = head.match(/geohack\.php\?(?:.*&)?params=([^&#]+)/);
  if (!pm) return null;
  const params = decode(pm[1]);
  /** @type {State} */
  let st;
  let rest = params;
  const dd = params.match(new RegExp(`^(${NUM});(${NUM})(.*)$`));
  if (dd) {
    st = { lat: dd[1], lon: dd[2] };
    rest = dd[3];
  } else {
    const f = params.split("_");
    const ns = f.findIndex((x) => /^[NS]$/i.test(x));
    const ew = f.findIndex((x, i) => i > ns && /^[EW]$/i.test(x));
    if (ns < 1 || ns > 3 || ew - ns < 2 || ew - ns > 4) return null;
    const lat = f.slice(0, ns);
    const lon = f.slice(ns + 1, ew);
    // Single decimal fields keep their digits; D_M_S fields are computed.
    st =
      lat.length === 1 && lon.length === 1
        ? { lat: (/S/i.test(f[ns]) ? "-" : "") + lat[0], lon: (/W/i.test(f[ew]) ? "-" : "") + lon[0] }
        : { lat: fmt(dms(lat, f[ns])), lon: fmt(dms(lon, f[ew])) };
    rest = f.slice(ew + 1).join("_");
  }
  const scale = rest.match(/scale:(\d+)/);
  const dim = rest.match(/dim:([\d.]+)(km|m)?/);
  if (scale) st.z = scaleToZoom(Number(scale[1]));
  // GeoHack treats dim (view width) as scale = dim * 10.
  else if (dim) st.z = scaleToZoom(Number(dim[1]) * (dim[2] === "km" ? 1000 : 1) * 10);
  return st;
}

const DMS_SIDE = (/** @type {string} */ hemis) =>
  String.raw`([${hemis}])?\s*(\d+(?:\.\d+)?)\s*(?:[°º:d]\s*|\s+)?(?:(\d+(?:\.\d+)?)\s*(?:['′’:m]\s*|\s+)?)?(?:(\d+(?:\.\d+)?)\s*(?:["″”s]|''|′′)?)?\s*([${hemis}])?`;
const DMS_RE = new RegExp(`^${DMS_SIDE("NSns")}\\s*[,;/]?\\s*${DMS_SIDE("EWew")}$`);

/** "42°21′52.8″N 71°7′52.7″W", "42.36 N 71.13 W", "N42 21.88 W71 7.88". @param {string} head */
function parseText(head) {
  const t = head.trim();
  // A hemisphere letter or degree sign is required, else plain "lat lon" handles it.
  if (!/[NSEWnsew°º]/.test(t)) return null;
  const m = t.match(DMS_RE);
  if (!m) return null;
  const [, h1, d1, m1, s1, h1b, h2, d2, m2, s2, h2b] = m;
  if ((h1 && h1b) || (h2 && h2b)) return null;
  const nsH = h1 ?? h1b;
  const ewH = h2 ?? h2b;
  if (!nsH && !ewH && !/[°º]/.test(t)) return null;
  const single = (/** @type {string|undefined} */ mm, /** @type {string|undefined} */ ss) => !mm && !ss;
  return {
    lat: single(m1, s1) ? (/[Ss]/.test(nsH ?? "") ? "-" : "") + d1 : fmt(dms([d1, m1, s1], nsH)),
    lon: single(m2, s2) ? (/[Ww]/.test(ewH ?? "") ? "-" : "") + d2 : fmt(dms([d2, m2, s2], ewH)),
  };
}

/**
 * Parse anything we accept into a state; null if nothing matched.
 * `raw` is still percent-encoded: our own trailing params are peeled first so an
 * embedded URL's `&` cannot be confused with them.
 * @param {string} raw
 * @param {MapData} [data]
 * @returns {State | null}
 */
export function parse(raw, data) {
  /** @type {State} */
  const own = {};
  let head = raw;
  // `tile`, not `t`: many map links end in their own `&t=` (Apple, Google).
  for (let m; (m = head.match(/(?:^|&)(z|m|a|tile)=([^&]*)$/)); head = head.slice(0, m.index)) {
    const k = /** @type {"z"|"m"|"a"|"tile"} */ (m[1]);
    const v = decode(m[2].replace(/\+/g, " ")).trim();
    if (k === "z") {
      if (/^\d+(\.\d+)?$/.test(v)) own.z = Math.round(Number(v));
    } else if (v && own[k] === undefined) own[k] = v;
  }
  head = decode(head).trim().replace(/^(https?):\/(?!\/)/i, "$1://");

  /** @type {State | null} */
  let st = null;
  let m;
  if (!head) st = {};
  else if ((m = head.match(new RegExp(`^(${NUM})\\s*[,;\\s]\\s*(${NUM})$`)))) st = { lat: m[1], lon: m[2] };
  else if ((m = head.match(new RegExp(`^geo:(${NUM}),(${NUM})(?:,${NUM})?(?:;[^?]*)?(?:\\?(.*))?$`, "i")))) {
    st = { lat: m[1], lon: m[2] };
    const z = new URLSearchParams(m[3] ?? "").get("z");
    if (z && /^\d+(\.\d+)?$/.test(z)) st.z = Math.round(Number(z));
  } else st = parseGeoHack(head) ?? parseText(head) ?? parsePatterns(head, data);
  if (!st) return null;

  return normalize({ ...st, ...own });
}

/** @param {string} head @param {MapData} [data] @returns {State | null} */
function parsePatterns(head, data) {
  const extra = (data?.maps ?? []).flatMap((d) => (d.p ?? []).map((p) => new RegExp(p)));
  for (const re of [...BUILTIN, ...extra, ...GENERIC]) {
    const g = head.match(re)?.groups;
    if (g?.lat && g?.lon) return { lat: g.lat, lon: g.lon, z: zoomOf(g) };
  }
  return null;
}

/**
 * Wrap lon, reject impossible lat, clamp zoom, apply 6-decimal truncation.
 * @param {State} st
 * @returns {State | null}
 */
export function normalize(st) {
  const out = { ...st };
  if (out.z !== undefined) out.z = Math.min(21, Math.max(0, out.z));
  if (out.lat === undefined || out.lon === undefined) return out.lat === out.lon ? out : null;
  const lat = Number(out.lat);
  let lon = Number(out.lon);
  // A bad latitude means a misparse, so it is an error rather than a clamp.
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90) return null;
  out.lat = trunc6(out.lat);
  if (Math.abs(lon) > 180) {
    lon = ((((lon + 180) % 360) + 360) % 360) - 180;
    out.lon = fmt(lon);
  } else out.lon = trunc6(out.lon);
  return out;
}

/** encodeURIComponent, but keep `,` readable as the requirements show. @param {string} s */
const enc = (s) => encodeURIComponent(s).replace(/%2C/gi, ",");

/**
 * Canonical path. Default zoom and empty params are dropped.
 * @param {State} st
 */
export function canonical(st) {
  let s = st.lat !== undefined ? `${st.lat},${st.lon}` : "";
  if (st.z !== undefined && st.z !== DEFAULT_Z) s += `&z=${st.z}`;
  if (st.m) s += `&m=${enc(st.m)}`;
  if (st.tile) s += `&tile=${enc(st.tile)}`;
  if (st.a) s += `&a=${enc(st.a)}`;
  return BASE + (s.startsWith("&") ? "?" + s.slice(1) : s);
}

/**
 * The raw input from a location: path suffix plus query plus hash, so an embedded
 * URL keeps its own query and fragment. Falls back to the ?/# forms.
 * @param {{pathname: string, search: string, hash: string}} loc
 */
export function inputOf(loc) {
  const suffix = loc.pathname.startsWith(BASE) ? loc.pathname.slice(BASE.length) : "";
  if (suffix && suffix !== "index.html") return suffix + loc.search + loc.hash;
  return loc.search.slice(1) || loc.hash.slice(1);
}

const MERC_MAX = 85.0511287798;

/**
 * Web Mercator bbox [w, s, e, n] of a w×h px view at integer zoom z.
 * @param {number} lat @param {number} lon @param {number} z
 */
export function bbox(lat, lon, z, w = 1024, h = 768) {
  const size = 256 * 2 ** z;
  const phi = (Math.max(-MERC_MAX, Math.min(MERC_MAX, lat)) * Math.PI) / 180;
  const x = ((lon + 180) / 360) * size;
  const y = ((1 - Math.log(Math.tan(phi) + 1 / Math.cos(phi)) / Math.PI) / 2) * size;
  const lonOf = (/** @type {number} */ px) => (px / size) * 360 - 180;
  const latOf = (/** @type {number} */ py) => (Math.atan(Math.sinh(Math.PI * (1 - (2 * py) / size))) * 180) / Math.PI;
  return [lonOf(x - w / 2), latOf(Math.min(size, y + h / 2)), lonOf(x + w / 2), latOf(Math.max(0, y - h / 2))];
}

export const PLACEHOLDERS = ["lat", "lon", "z", "scale", "mqzoom", "w", "s", "e", "n", "a"];

/**
 * Fill a map's link template.
 * @param {string} u
 * @param {State} st
 */
export function fill(u, st) {
  const z = st.z ?? DEFAULT_Z;
  const scale = Math.round(1693 * 2 ** (18 - z));
  const [w, s, e, n] = bbox(Number(st.lat), Number(st.lon), z).map(fmt);
  /** @type {Record<string, string>} */
  const v = {
    lat: st.lat ?? "",
    lon: st.lon ?? "",
    z: String(z),
    scale: String(scale),
    // GeoHack's legacy {zoom}: int(18 - ln(scale)) in [0, 9]; natural log checked
    // against geohack.toolforge.org on 2026-10-09 (default scale 300000 -> 5).
    mqzoom: String(Math.min(9, Math.max(0, Math.trunc(18 - Math.log(scale))))),
    w, s, e, n,
    a: st.a ? encodeURIComponent(st.a) : "",
  };
  return u.replace(/\{(\w+)\}/g, (all, k) => v[k] ?? all);
}

/**
 * Whether a map applies at this point: global maps always, regional ones only inside
 * one of their country bboxes or inline [w,s,e,n] boxes.
 * @param {MapDef | TileDef} d @param {State} st @param {MapData["regions"]} regions
 */
export function inRegion(d, st, regions) {
  if (!d.r) return true;
  const lat = Number(st.lat);
  const lon = Number(st.lon);
  const boxes = d.r.flatMap((r) => (typeof r === "string" ? (regions[r] ?? []) : [r]));
  // No resolvable box means the region is unknown, not empty: show the map.
  return boxes.length === 0 || boxes.some(([w, s, e, n]) => lat >= s && lat <= n && lon >= w && lon <= e);
}
