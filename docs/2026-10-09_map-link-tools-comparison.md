# Universal map-link tools: mapfwd, GeoHack, and OpenSwitchMapsWeb

Cody Dunne · 2026-10-09 · compiled with Claude

## Summary

No hosted tool found supports both RideWithGPS and AllTrails out of the box.
The best no-maintenance option for outdoor and cycling use is [OpenSwitchMapsWeb](https://tankaru.github.io/OpenSwitchMapsWeb/) plus its 10 user-defined custom slots, filled with the US services GeoHack has and OpenSwitchMaps lacks (CalTopo, Natural Atlas, USGS TopoView, NWS) and an RWGPS template once verified.
AllTrails cannot be added through custom slots because its explore URL needs a bounding box, not a center point.

## 1. Scope

The goal was a shareable, cross-provider location link in the spirit of [mapfwd.com](https://mapfwd.com), covering cycling and hiking services, with no self-hosted code to maintain.

## 2. Tool landscape

| Category | Examples | Fits the goal? |
|---|---|---|
| Sender-side web link generators | mapfwd, GeoHack, OpenSwitchMapsWeb | Yes |
| Receiver-side apps (re-open a link you were sent) | Geo Share (Android/F-Droid), Maze, Map Switch (iOS) | No; per device |
| Safari redirect extensions | Map Redirect, MapLink Router, MapSwitch, Rerouter (archived 2024-11-27) | No; per browser |
| Developer libraries | `create-map-link` (npm), `react-native-map-link` | No; requires building |
| Standards | `geo:` URI | Unreliable on iOS Safari |

[mapfwd](https://alternativeto.net/software/map-fwd/about) converts any coordinate, address, or map URL into one smart link that lists services or auto-redirects to the native maps app. It also accepts a `mapfwd.com/<map URL>` prefix and has Discord, Slack, Telegram, and IRC bots.
Its service list is fixed and does not include trail or cycling apps.

## 3. GeoHack vs. OpenSwitchMapsWeb

GeoHack was inspected live for 42.3736, −71.1097 on 2026-10-09.
OpenSwitchMaps coverage is taken from the extension repository's [`maps.js`](https://github.com/tankaru/OpenSwitchMaps/blob/master/src/maps.js).
The web version keeps its own `maps.js`, which was not diffed, so expect minor differences.

### 3.1 Structural differences

| | GeoHack | OpenSwitchMapsWeb |
|---|---|---|
| Input | Coordinates only | Any supported map URL; round-trips to many |
| Custom links | No; Wikipedia template, community consensus | 10 slots, per browser |
| Regional depth | ~50 country/region sections, including US | Mainly JP; a few EU, RU, CN |
| Zoom | Approximate, via scale | Integer zoom |
| Maintenance | Wikimedia community | Single maintainer; extension currently not updatable, web version live |

### 3.2 Provider coverage

**Both.**
Google Maps (map, satellite, Street View), Bing, OpenStreetMap, Apple Maps, HERE WeGo, Waze, Yandex, Mapy, TomTom, Wikimapia, OpenTopoMap, Google Earth, Esri Wayback, Zoom Earth, NASA FIRMS, Sentinel/Copernicus imagery, OpenHistoricalMap, OpenStreetBrowser, Mapillary, Strava heatmap, PeakFinder, Windy, Flickr, Old Maps Online, Open Infrastructure Map, OpenRailwayMap, OpenSeaMap, WaterwayMap, MarineTraffic, Flightradar24, SkyVector, LightningMaps, and overlapping UK/France/Japan official maps (Ordnance Survey, NLS, IGN, GSI).

**GeoHack only.**
- *US outdoor:* CalTopo, Natural Atlas, USGS National Map, USGS TopoView (historic topos), GPS Visualizer (USGS topo, USDA aerial), ACME Mapper (topo, NEXRAD, DOQ), Historic Aerials, NWS point forecast, TopoQuest.
- *General:* MapQuest, GeoNames, NASA WorldWind, Blue Marble, Geocaching.
- *Wikipedia:* nearby articles, WikiShootMe, Commons map.
- *Regional:* the large country-specific catalog.

GeoHack's OSM row also links a `project=osm` variant with more OSM maps; it was not inspected.

**OpenSwitchMaps only.**
- *Cycling and routing:* Komoot planner, CyclOSM, OpenCycleMap, BRouter-Web, Waymarked Trails, Trail Router, On The Go Map, Locus, OsmAnd, OpenSnowMap.
- *OSM tooling:* Geofabrik/BBBike Map Compare, Overpass Turbo, Osmose and other QA tools, iD/JOSM/RapiD editors.
- *Other:* ShadeMap/Shadowmap, Macrostrat geology, Ventusky, Weather Underground, earth.nullschool, what3words, Panoramax, KartaView.

**Neither.**
RideWithGPS, AllTrails, Gaia GPS, onX, Garmin Connect.

## 4. OpenSwitchMapsWeb custom slots

Behavior verified from [`main.js`](https://github.com/tankaru/OpenSwitchMapsWeb/blob/master/main.js):

- Ten slots, `Custom01`–`Custom10`, appear under a "Custom maps" category.
- Placeholders are `{latitude}`, `{longitude}`, and `{zoom}`.
  Each is substituted once via `String.replace`, so only the first occurrence of each placeholder is filled.
  No arithmetic is possible.
- Zoom is rounded to an integer, and values are inserted unencoded.
- Slots are saved to `localStorage` key `OpenSwitchMapsCustomMaps`.
  They are per browser and per device, with no sync and no export.
  Back up via DevTools: `localStorage.getItem('OpenSwitchMapsCustomMaps')`.
- Custom entries are jump-to only and cannot parse a URL as input.

### 4.1 Setup

1. Open the page with any supported map URL after `#`.
2. Enable **Show descriptions**; the input boxes live in the description column.
3. Enter a label and template in a Custom row, then click **↺** to save.

### 4.2 Proposed templates

The first four are derived from GeoHack's live links.

| Label | Template | Status |
|---|---|---|
| CalTopo | `https://caltopo.com/map.html#ll={latitude},{longitude}&z={zoom}&b=t` | From GeoHack |
| Natural Atlas | `https://naturalatlas.com/map/@{latitude},{longitude},{zoom}z` | From GeoHack |
| USGS TopoView | `https://ngmdb.usgs.gov/topoview/viewer/#{zoom}/{latitude}/{longitude}` | From GeoHack |
| NWS forecast | `https://forecast.weather.gov/MapClick.php?lat={latitude}&lon={longitude}` | From GeoHack |
| RideWithGPS | `https://ridewithgps.com/routes/new?center={latitude}%2C{longitude}&zoom={zoom}` | **Unverified**; test once directly |

## 5. Open items

- **RideWithGPS.** No documented coordinate deep link was found, and a forum report says RWGPS did not support entering waypoints by coordinates (old, secondhand).
  Verify by panning the planner and watching the address bar, or by loading the template above with real values.
- **AllTrails.** The explore page takes `b_tl_lat`, `b_tl_lng`, `b_br_lat`, `b_br_lng`, which custom slots cannot compute.
  Request it upstream in an [OpenSwitchMapsWeb issue](https://github.com/tankaru/OpenSwitchMapsWeb/issues): the codebase already has a `latLonZoomToBbox` helper used for Yelp and Old Maps Online.
- **mapfwd.** It may be worth asking via its [contact page](https://mapfwd.com/contact) whether it will add trail and cycling services, since its shareable-link model is closest to the goal.

## Sources

- [mapfwd on AlternativeTo](https://alternativeto.net/software/map-fwd/about)
- [GeoHack, live page for 42.3736, −71.1097](https://geohack.toolforge.org/geohack.php?params=42.3736_N_71.1097_W)
- [OpenSwitchMapsWeb repository](https://github.com/tankaru/OpenSwitchMapsWeb) and [`main.js`](https://github.com/tankaru/OpenSwitchMapsWeb/blob/master/main.js)
- [OpenSwitchMaps `maps.js`](https://github.com/tankaru/OpenSwitchMaps/blob/master/src/maps.js)
- [OSM Smart Menu (OSM wiki)](https://wiki.openstreetmap.org/wiki/OSM_Smart_Menu)
- [AllTrails explore URL format (browse.sh)](https://browse.sh/skills/alltrails.com/search-trails-dsqvnx)
- [RWGPS coordinate waypoints thread (Bushwalk)](https://maps.bushwalk.com/forum/viewtopic.php?p=299385)
- [Geo Share](https://alternativeto.net/software/geo-share/about), [Maze](https://apps.apple.com/py/app/maze-maps-switcher/id6504451783), [Map Switch](https://apps.apple.com/us/app/map-switch-convert-map-links/id6748560411), [Map Redirect](https://apps.apple.com/us/app/map-redirect-for-map-links/id1590589672), [MapLink Router](https://apps.apple.com/app/id6757279013), [Rerouter](https://github.com/git-shawn/Rerouter)
- [create-map-link](https://github.com/jasongerbes/create-map-link), [react-native-map-link](https://github.com/tweag/react-native-map-link)
- [`geo:` URI on iOS (DEV)](https://dev.to/professortom/why-your-browser-wont-open-maps-with-a-geo-uri-and-a-workaround-ief)
