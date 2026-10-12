# geo

A small static page at [dunne.dev/geo](https://dunne.dev/geo/) that opens a location in any of about 420 map services.
It takes coordinates, a map URL, or an address, rewrites the address bar to a short canonical link, and lists links into every map that applies at that point.
The map list is the union of [GeoHack](https://geohack.toolforge.org/), [OpenSwitchMaps](https://github.com/tankaru/OpenSwitchMapsWeb), and [mapfwd](https://mapfwd.com/), plus RideWithGPS and AllTrails.

## TODO

add descriptive text for each

## URLs

```text
/geo/<lat>,<lon>[&z=<zoom>][&m=<map id>][&a=<label>]
```

| Param | Meaning | Default |
|---|---|---|
| `<lat>,<lon>` | Decimal degrees; digits kept as entered, truncated past 6 decimals | — |
| `z` | OSM-scale zoom, converted per provider | 15 |
| `m` | Map ID to feature at the top (never auto-redirects) | none |
| `a` | Pin label; on its own (`/geo/?a=…`) it is geocoded once via Nominatim, falling back to Photon | none |

A bare `/geo/` shows Cambridge, MA at zoom 10 (greater Boston) with no pin; click the map to drop one, or use the input box or My location.
Anything after `/geo/` is parsed, then replaced by the canonical form:

- `42.364678,-71.131311`, `42°21′52.8″N 71°7′52.7″W`, `42.36 N 71.13 W`, `geo:42.36,-71.13?z=15`
- Google Maps `place/`, `search/?api=1&query=`, `@?api=1&map_action=map&center=`, and `@lat,lon,Nz` URLs
- GeoHack `geohack.php?params=` URLs, RideWithGPS, OpenStreetMap `#map=`, and about 90 other services' URLs (the `p` patterns in `maps.json`)
- `/geo/?<input>` and `/geo/#<input>` work too

Map IDs are listed in [`web/_/maps.json`](web/_/maps.json); curated short ones include `osm`, `google`, `apple`, `osmcycle`, `rwgps`, and `alltrails`.
Short links such as `maps.app.goo.gl` are not supported: resolving them needs a server-side proxy.

## Run locally

```sh
uv run scripts/serve.py        # http://127.0.0.1:8000/geo/
```

The server mounts `web/` at `/geo/` and serves `index.html` for every non-asset path, as production does.
A plain static server or `file://` will not work, because every path must serve the same page.

## Tests

```sh
corepack pnpm install          # once: TypeScript for the JSDoc type check
node --test                    # parser, canonicalizer, maps.json invariants
corepack pnpm typecheck        # tsc --noEmit over web/_/*.js and tests/
uv run tests/smoke.py          # headless browser; see its docstring for one-time setup
```

## Updating the map list

```sh
uv run scripts/collect_maps.py
git diff web/_/maps.json       # review before committing
```

The collector fetches GeoHack's [`Template:GeoTemplate`](https://en.wikipedia.org/wiki/Template:GeoTemplate) wikitext and OpenSwitchMaps' `maps.js` (both repos, pinned commits), and Natural Earth country outlines for regional bboxes.
It parses the JavaScript with regexes and never runs it.
It then applies [`scripts/maps-overrides.json`](scripts/maps-overrides.json): curated IDs, category names, region aliases, and hand-added services.
Published IDs never change: the collector reuses IDs from the previous `maps.json`, keeps entries that vanish upstream until an override marks them `"drop": true`, and refuses to write if a published ID would disappear.
It prints what it could not translate (computed URLs, unsupported GeoHack placeholders, parse patterns that fail to round-trip).

## Deployment

`.github/workflows/pages.yml` publishes `web/` to GitHub Pages on every push to `main` that touches it, copying `index.html` to `404.html` on the way.
One-time setting: **Settings → Pages → Source: GitHub Actions**.

dunne.dev is proxied by Cloudflare.
A Transform Rule makes every `/geo/…` path return HTTP 200 with `index.html`.
Without the rule, GitHub's `404.html` fallback still serves the page, but with status 404.

**Rules → Overview → Create Rule → URL Rewrite Rule**:

- Enter a rule name, e.g.: "transform for /geo/ so it doesn't hit 404s"
- Under "If incoming requests match…", choose "Custom filter expression"
- Select "Edit expression" and paste the whole expression there, not into the builder's Value box or the "Wildcard pattern" Request URL box (both read it as a URL pattern and warn that DNS is not proxying it):
  `starts_with(http.request.uri.path, "/geo/") and not starts_with(http.request.uri.path, "/geo/_/") and http.request.uri.path ne "/geo/"`
- Under "Path": Rewrite to → Static → `/geo/`
- Under "Query": Preserve

After deploying, check that Cloudflare does not collapse the `//` in embedded URLs:

```sh
curl -sI 'https://dunne.dev/geo/https://www.google.com/maps/place/42.364678,-71.131311' | head -1
```

The parser accepts `https:/` as well, so a collapsed slash degrades gracefully.

## Credits and licenses

Code: MIT ([`LICENSE`](LICENSE)).
Map link formats come from GeoHack's Template:GeoTemplate (Wikipedia contributors, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)) and OpenSwitchMaps / OpenSwitchMapsWeb by tankaru (MIT); `web/_/maps.json` records its sources per entry.
Regional bboxes are derived from [Natural Earth](https://www.naturalearthdata.com/) (public domain).
Bundled: [Leaflet](https://leafletjs.com/) 1.9.4 (BSD-2-Clause, `web/_/leaflet/LICENSE`) and Atkinson Hyperlegible by the Braille Institute (SIL OFL 1.1, `web/_/fonts/OFL.txt`).
The page uses [OpenStreetMap](https://www.openstreetmap.org/copyright) tiles, [Nominatim](https://nominatim.org/), and [Photon](https://photon.komoot.io/) under their usage policies.
