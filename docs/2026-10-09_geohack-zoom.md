# GeoHack default zoom depends on coordinate format, not precision

Cody Dunne — 2026-10-09

## Question

Why does

`https://geohack.toolforge.org/geohack.php?params=42.364678%3B-71.131311`

open the map links zoomed out (OSM zoom 11), while

`https://geohack.toolforge.org/geohack.php?params=42_21_52_N_71_7_52_W`

opens them zoomed in (OSM zoom 15)?

## Answer

GeoHack picks a default map scale from the number of coordinate fields given (degrees, degrees+minutes, or degrees+minutes+seconds). It ignores how many decimal places those fields have. Any degrees-only input, however precise, falls through to the documented default of 1:300,000 (OSM zoom 11). Including seconds gives a default of roughly 1:10,000 (zoom 15).

The decimal form in the first URL is degrees-only, so it gets the coarse default even though six decimal places (≈0.1 m) is far more precise than whole arc-seconds (≈31 m).

## Method

The pages were loaded in a browser on 2026-10-09. For each variant of `params=`, the `zoom=` value was read from the OpenStreetMap link that GeoHack generates. The Google Maps (`z=`) and Bing (`lvl=`) links carried the same values. Same-origin `fetch` was used against `https://geohack.toolforge.org/geohack.php`.

| `params=` | Format | OSM zoom | Implied scale |
|---|---|---|---|
| `42.364678;-71.131311` | D;D | 11 | 1:300,000 (default) |
| `42.364678_N_71.131311_W` | D_N_D_W | 11 | 1:300,000 |
| `42.36_N_71.13_W` | D_N_D_W | 11 | 1:300,000 |
| `42_21_N_71_7_W` | D_M | 12 | ≈1:100,000 |
| `42_21.88_N_71_7.88_W` | D_M (decimal min) | 12 | ≈1:100,000 |
| `42_21_52_N_71_7_52_W` | D_M_S | 15 | ≈1:10,000 |
| `42_21_52.84_N_71_7_52.72_W` | D_M_S (decimal sec) | 15 | ≈1:10,000 |
| `42.364678;-71.131311_dim:100` | D;D + `dim` | 18 | 1:1,000 (capped at zoom 18) |

The implied scales are back-computed from GeoHack's documented conversion, `osmzoom = 18 − round(log2(scale / 1693))`, and clamped to [2, 18]. See the [GeoHack documentation](https://www.mediawiki.org/wiki/GeoHack).

Observations:

- The semicolon syntax is not the cause. Decimal degrees in `_N_…_W` form behave identically.
- Decimal places within a field have no effect. `42.36` and `42.364678` both give 11, and `52` and `52.84` seconds both give 15.
- Only the field count matters: 1 field gives 11, 2 fields give 12, and 3 fields give 15.

## Uncertainty

The [GeoHack documentation](https://www.mediawiki.org/wiki/GeoHack) and the [WikiProject coordinates `scale:` page](https://en.wikiversity.org/wiki/Wikiversity:WikiProject_Geographical_coordinates/scale:) describe only the 1:300,000 default when no `dim:`, `type:`, or `scale:` is given. The step-up for minutes and seconds is undocumented. It is inferred here from observed behavior; the server source was not inspected because the [Bitbucket repository](https://bitbucket.org/magnusmanske/geohack) blocks automated access. The exact internal scale values for the D_M and D_M_S cases are therefore approximate, back-computed from the zoom levels. A future GeoHack change could alter this.

## Fix

Keep the precise decimal coordinates and state the intended view explicitly. The preferred option is `dim:`, the object's size in metres, because it does not depend on display resolution. `scale:` (1:N) also works.

- Close-up of a building: `params=42.364678;-71.131311_dim:100` gives zoom 18.
- Same view as the DMS link: `params=42.364678;-71.131311_dim:1000` gives zoom 15.
- Alternatively, set a `type:`. For example, `type:landmark` gives 1:10,000, which is zoom 15.

## Side note: the DMS link is a different point

`42_21_52_N_71_7_52_W` truncates the seconds of the original point (`42°21′52.84″ N, 71°7′52.72″ W`).

- Latitude: 0.84″ × 30.87 m/″ ≈ 26 m.
- Longitude: 0.72″ × 30.87 m/″ × cos 42.36° ≈ 16 m.
- Combined offset: √(26² + 16²) ≈ 31 m, roughly south-east of the intended location.

This corrects the earlier estimate of ≈25 m, which counted only the latitude component.

Use the decimal form with `dim:` to get both the precision and the zoom.
