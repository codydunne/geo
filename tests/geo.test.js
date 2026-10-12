import assert from "node:assert/strict";
import { test } from "node:test";
import { PLACEHOLDERS, bbox, canonical, fill, inRegion, inputOf, parse } from "../web/_/geo.js";

/** @param {string} raw */
const canon = (raw) => {
  const st = parse(raw);
  return st && canonical(st);
};

test("requirements.md and example-links-to-existing.md inputs", () => {
  /** @type {[string, string][]} */
  const cases = [
    ["42.364678,-71.131311", "/geo/42.364678,-71.131311"],
    ["42.364678,-71.131311&z=15", "/geo/42.364678,-71.131311"],
    ["42.364678,-71.131311&z=12", "/geo/42.364678,-71.131311&z=12"],
    ["42.3646,-71.1313&m=osmcycle", "/geo/42.3646,-71.1313&m=osmcycle"],
    ["42.3646,-71.1313&m=rwgps", "/geo/42.3646,-71.1313&m=rwgps"],
    ["https://www.google.com/maps/place/42.364678,-71.131311", "/geo/42.364678,-71.131311"],
    ["https://www.google.com/maps/search/?api=1&query=42.364678,-71.131311", "/geo/42.364678,-71.131311"],
    ["https://www.google.com/maps/@?api=1&map_action=map&center=42.364678,-71.131311", "/geo/42.364678,-71.131311"],
    ["https://www.google.com/maps/search/?api=1&query=42.364678%2C-71.131311", "/geo/42.364678,-71.131311"],
    ["https://ridewithgps.com/routes/new?center=42.364743%2C-71.131245&zoom=16", "/geo/42.364743,-71.131245&z=16"],
    ["https://geohack.toolforge.org/geohack.php?params=42.364678%3B-71.131311", "/geo/42.364678,-71.131311"],
    ["https://geohack.toolforge.org/geohack.php?params=42_21_52_N_71_7_52_W", "/geo/42.364444,-71.131111"],
    ["https://geohack.toolforge.org/geohack.php?params=42.364678_N_71.131311_W", "/geo/42.364678,-71.131311"],
    ["https://geohack.toolforge.org/geohack.php?params=42.364678;-71.131311_dim:100", "/geo/42.364678,-71.131311&z=19"],
    ["a=My%20Place%20Name,%20City", "/geo/?a=My%20Place%20Name,%20City"],
    ["42.364678,-71.131311&a=My%20Place%20Name,%20City", "/geo/42.364678,-71.131311&a=My%20Place%20Name,%20City"],
  ];
  for (const [raw, want] of cases) assert.equal(canon(raw), want, raw);
});

test("text and geo: forms", () => {
  assert.equal(canon("42°21′52.8″N 71°7′52.7″W"), "/geo/42.364667,-71.131306");
  assert.equal(canon("42%C2%B021%E2%80%B252.8%E2%80%B3N%2071%C2%B07%E2%80%B252.7%E2%80%B3W"), "/geo/42.364667,-71.131306");
  assert.equal(canon(`42°21'52.8"N, 71°7'52.7"W`), "/geo/42.364667,-71.131306");
  assert.equal(canon("42.36 N 71.13 W"), "/geo/42.36,-71.13");
  assert.equal(canon("N42.36 W71.13"), "/geo/42.36,-71.13");
  assert.equal(canon("33.9 S 18.4 E"), "/geo/-33.9,18.4");
  assert.equal(canon("geo:42.36,-71.13?z=15"), "/geo/42.36,-71.13");
  assert.equal(canon("geo:42.36,-71.13;u=35?z=12"), "/geo/42.36,-71.13&z=12");
  assert.equal(canon("42.36 -71.13"), "/geo/42.36,-71.13");
});

test("other map URLs", () => {
  assert.equal(canon("https://www.openstreetmap.org/#map=12/42.36/-71.13"), "/geo/42.36,-71.13&z=12");
  assert.equal(canon("https://www.google.com/maps/@42.36,-71.13,13z"), "/geo/42.36,-71.13&z=13");
  assert.equal(canon("https:/www.google.com/maps/@42.36,-71.13,13.5z"), "/geo/42.36,-71.13&z=14");
});

test("precision, wrapping, and rejection", () => {
  assert.equal(canon("42.1234567891,-71.1"), "/geo/42.123456,-71.1");
  assert.equal(canon("-0.0000001,7"), "/geo/0.000000,7");
  assert.equal(canon("42.3600,-71.1300"), "/geo/42.3600,-71.1300");
  assert.equal(canon("10,190"), "/geo/10,-170");
  assert.equal(canon("91,0"), null);
  assert.equal(canon("hello world"), null);
  assert.equal(canon("42,-71&z=99"), "/geo/42,-71&z=21");
});

test("inputOf: path, query, and hash forms", () => {
  const loc = (/** @type {string} */ pathname, search = "", hash = "") => ({ pathname, search, hash });
  assert.equal(inputOf(loc("/geo/42,-71&z=3")), "42,-71&z=3");
  assert.equal(
    inputOf(loc("/geo/https://www.google.com/maps/search/", "?api=1&query=42,-71")),
    "https://www.google.com/maps/search/?api=1&query=42,-71",
  );
  assert.equal(inputOf(loc("/geo/https://www.openstreetmap.org/", "", "#map=3/1/2")), "https://www.openstreetmap.org/#map=3/1/2");
  assert.equal(inputOf(loc("/geo/", "?42,-71")), "42,-71");
  assert.equal(inputOf(loc("/geo/", "", "#42,-71")), "42,-71");
  assert.equal(inputOf(loc("/geo/index.html", "?42,-71")), "42,-71");
});

test("bbox is finite at the poles and centred elsewhere", () => {
  for (const lat of [90, -90]) assert.ok(bbox(lat, 0, 5).every(Number.isFinite));
  const [w, s, e, n] = bbox(42.36, -71.13, 15);
  assert.ok(w < -71.13 && e > -71.13 && s < 42.36 && n > 42.36);
});

test("fill and inRegion", () => {
  const st = { lat: "42.36", lon: "-71.13", z: 12, a: "A & B" };
  assert.equal(fill("x/{z}/{lat}/{lon}?q={a}&s={scale}", st), "x/12/42.36/-71.13?q=A%20%26%20B&s=108352");
  assert.equal(fill("{mqzoom}", { lat: "0", lon: "0", z: 11 }), "5"); // scale 216704 ~ GeoHack default
  assert.equal(fill("{mqzoom}", { lat: "0", lon: "0", z: 15 }), "8");
  assert.ok(inRegion({ id: "x", n: "x", c: "x", u: "", r: ["US"] }, st, { US: [[-125, 24, -66, 50]] }));
  assert.ok(!inRegion({ id: "x", n: "x", c: "x", u: "", r: ["GB"] }, st, { GB: [[-8, 49, 2, 61]] }));
  assert.ok(inRegion({ id: "x", n: "x", c: "x", u: "", r: [[-72, 42, -71, 43]] }, st, {}));
});

test("maps.json invariants", async () => {
  const { readFile } = await import("node:fs/promises");
  /** @type {import("../web/_/geo.js").MapData} */
  const data = JSON.parse(await readFile(new URL("../web/_/maps.json", import.meta.url), "utf8"));
  const ids = data.maps.map((m) => m.id);
  assert.equal(new Set(ids).size, ids.length, "unique ids");
  for (const id of ["osm", "google", "osmcycle", "rwgps", "alltrails"]) assert.ok(ids.includes(id), id);
  const st = { lat: "42.364678", lon: "-71.131311", z: 13 };
  for (const m of data.maps) {
    const bad = [...m.u.matchAll(/\{(\w*)\}/g)].map((x) => x[1]).filter((k) => !PLACEHOLDERS.includes(k));
    assert.deepEqual(bad, [], `${m.id} placeholders`);
    assert.match(fill(m.u, st), /^https?:\/\/[^{}]+$/, `${m.id} fill`);
    assert.ok(!m.f || (m.u.startsWith("https://") && !m.disabled), `${m.id} framable`);
    for (const r of m.r ?? []) assert.ok(typeof r !== "string" || data.regions[r], `${m.id} region ${r}`);
    for (const p of m.p ?? []) {
      const g = fill(m.u, st).match(new RegExp(p))?.groups;
      assert.ok(g, `${m.id} pattern matches its own link`);
      assert.equal(Number(g.lat), Number(st.lat), `${m.id} lat`);
      assert.equal(Number(g.lon), Number(st.lon), `${m.id} lon`);
    }
  }
  // Country-specific services stay out of a Boston list.
  const boston = { lat: "42.36", lon: "-71.13" };
  const leaked = data.maps
    .filter((m) => inRegion(m, boston, data.regions))
    .map((m) => m.n)
    .filter((n) => /\((JP|FR|DE|RU|UK)\)|地理院|^osm\.(fr|kr|bzh)$|^OSM\.(de|jp|ru|cl|in|ch)$|^OSMChina$/i.test(n));
  assert.deepEqual(leaked, []);
  assert.ok(data.maps.filter((m) => inRegion(m, { lat: "35.68", lon: "139.76" }, data.regions)).some((m) => m.n === "地理院地図"));
  // A link from a collected service parses through the data patterns.
  assert.equal(canonical(/** @type {any} */ (parse("https://www.komoot.com/plan/@42.36,-71.13,12z", data))), "/geo/42.36,-71.13&z=12");
});
