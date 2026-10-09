My goal is to create a simple, static, and mobile-friendly website like mapfwd.com, geohack, and OpenSwitchMapsWeb that will sit at https://dunne.dev/geo.

Constraints:
* Use the CSS in @references/ to start with.
* Accept URL parameters, e.g., as OpenSwitchMapsWeb. Especially lat,lon, zoom, and default map to show. E.g.,
  * https://dunne.dev/geo/42.364678,-71.131311
  * https://dunne.dev/geo/42.364678,-71.131311&z=15 for OSM zoom level 15
  * https://dunne.dev/geo/42.3646,-71.1313&m=osmcycle for OSM Cycle
  * https://dunne.dev/geo/42.3646,-71.1313&m=rwgps for ridewithgps
  * https://dunne.dev/geo/https://www.google.com/maps/place/42.364678,-71.131311
  * https://dunne.dev/geo/https://www.google.com/maps/search/?api=1&query=42.364678,-71.131311
  * https://dunne.dev/geo/https://www.google.com/maps/@?api=1&map_action=map&center=42.364678,-71.131311
* Parameters should be terse for short urls.
* Have a responsive design that works well on both desktop and mobile devices.
* Simple, easy to use layout.
* Provide the superset of maps covered by GeoHack, OpenSwitchMapsWeb, and mapfwd.com
* The browser location should be stripped down to be canonical. E.g., https://dunne.dev/geo/https://www.google.com/maps/place/42.364678,-71.131311 should become https://dunne.dev/geo/42.364678,-71.131311
* A standalone uv script should collect the map formats from GeoHack, OpenSwitchMapsWeb, and mapfwd.com and put them in our format.
* Map link formats should be as terse as possible. E.g., remove all redundant boilerplate code, store in JSON instead of in code if viable.

# Decisions (2026-10-09)

## Hosting and routing

dunne.dev is the `codydunne/codydunne.github.io` user site (CNAME `dunne.dev`), proxied through Cloudflare (Cloudflare NS; responses carry `server: cloudflare` and `x-github-request-id`).
This repo publishes as a GitHub Pages project site, which serves it at `dunne.dev/geo/`.

* **Path form is canonical and must return HTTP 200.** A Cloudflare Transform Rule (URL Rewrite) internally rewrites `/geo/*` to `/geo/` so `index.html` serves every path. The browser keeps the original URL for the JS to parse. The rule is created by hand in the Cloudflare dashboard and documented in the README.
* **Fallback:** `404.html` is identical to `index.html`, so the site still works (with status 404) if the rule is removed.
* **Assets** live under a single prefix, `/geo/_/`, which the rewrite rule excludes. Inputs such as `/geo/https://www.google.com/…` contain dots, so extension-based exclusion is unreliable.
* **Equivalent forms** `dunne.dev/geo/?<input>` and `dunne.dev/geo/#<input>` are accepted and rewritten to the path form via `history.replaceState`.

## Canonical URL

* Form: `/geo/<lat>,<lon>[&z=<zoom>][&m=<map id>][&a=<address>]`.
* Precision: keep the digits as entered, but truncate beyond 6 decimal places (about 0.1 m).
* Drop default values, such as `z=15`.

## Parameters

| Param | Meaning | Default |
|---|---|---|
| `<lat>,<lon>` | Point, as the first path segment or query token | — |
| `z` | OSM-scale zoom; converted per provider (scale, altitude, bbox) | 15, or the source URL's zoom if it has one |
| `m` | Map ID to feature | none |
| `a` | Free-text address or place label | none |

* **`m=`** highlights the chosen map, pinned at the top with an Open button. The page never auto-redirects, and the full list stays visible.
* **`a=`** is the only trigger for address geocoding.
  * Geocoding uses Nominatim and runs once, only when `a` is present and coordinates are absent. The result is canonicalized with `a` preserved, e.g. `/geo/?a=My Place Name, City` becomes `/geo/42.364678,-71.131311&a=My%20Place%20Name,%20City`.
  * When coordinates are present, `a` is trusted as given: there is no second lookup, and `a` is used only as the pin label.

## Accepted inputs

* Plain `lat,lon`, and the Google Maps URL forms listed above.
* Any map URL that OpenSwitchMaps can parse, reusing its MIT-licensed URL patterns.
* DMS and other text forms (e.g. `42°21′52.8″N 71°7′52.7″W`, `42.36 N 71.13 W`) and `geo:` URIs (`geo:42.36,-71.13?z=15`).
* Out of scope: short links such as `maps.app.goo.gl`. They cannot be resolved client-side because of CORS and would need a proxy.

## UI

* A small Leaflet map with OSM tiles shows the point (and the `a` label). Dragging the pin or zooming updates the canonical URL. The OSM tile usage policy applies.
* Features:
  * A search box that filters the map list by name or category.
  * A Copy-link button, plus the Web Share API on mobile.
  * A My-location button that uses browser geolocation.
* Favorites are not in scope.
* Regional maps are listed only when the point falls inside their region, so each regional map needs a country code or bbox in the data.

## Styling

* Base: `references/style-k7.css` (a dark theme), plus a light theme via `prefers-color-scheme`.
* Fonts: copy the Atkinson Hyperlegible files (SIL OFL) into this repo so the site is self-contained on localhost and github.io. Source: `codydunne.github.io/public/r/k7/fonts/`.

## Map data and collector script

* Output: a committed JSON file, `web/_/maps.json`.
* The collector runs manually with `uv run`, and you review the diff before committing. No scheduled automation.
* Sources:
  * **GeoHack:** scraped.
  * **OpenSwitchMaps / OpenSwitchMapsWeb:** `maps.js` scraped. Both repos are MIT-licensed; keep attribution.
  * **mapfwd.com:** not scraped. It is a closed-source Next.js app with no license and no data file. Compare its service list by hand once, and add any missing services to the overrides.
* **Overrides:** a hand-maintained JSON file merged on top of the scraped data. It holds:
  * Curated short map IDs (`osm`, `osmcycle`, `rwgps`, …). The script auto-slugs anything without one, and published IDs never change.
  * The mapfwd extras.
  * Hand-added services: **RideWithGPS** and **AllTrails**. AllTrails needs a bbox computed from lat/lon/zoom.

## Closed items

* **RideWithGPS:** I verified the coordinate deep-link template by hand (see `docs/2026-10-09_map-link-tools-comparison.md` §5).

## Open items

* **Cloudflare:**
  * Confirm that Cloudflare URL normalization does not collapse `//` in `/geo/https://…`. If it does, the parser must also accept `https:/`.
  * Write the exact Transform Rule expression and add it to the README.
* **Nominatim:** comply with its usage policy (≤1 request/s, identifying referrer). Cache results so a canonicalized URL never triggers another lookup.
* **Region data:** choose a source for regional bboxes, either GeoHack section metadata or a small country-bbox table.
