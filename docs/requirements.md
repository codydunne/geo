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