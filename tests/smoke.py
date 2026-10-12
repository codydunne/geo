#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright==1.55.0"]
# ///
"""Browser smoke test against scripts/serve.py.

Nominatim is mocked and OSM tiles are blocked, so the test never touches those
services. One-time setup: `uvx --from playwright==1.55.0 playwright install
chromium-headless-shell` (on hosts Playwright does not list yet, prefix with
PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, Route, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PORT = 8765
BASE = f'http://127.0.0.1:{PORT}'


def wait_for_server() -> None:
    for _ in range(50):
        try:
            urllib.request.urlopen(f'{BASE}/geo/_/maps.json', timeout=1)
            return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError('server did not start')


def visit(page: Page, path: str) -> None:
    page.goto(BASE + path)
    page.wait_for_function(
        'document.querySelector("#list a") || !document.querySelector("#msg").hidden'
    )


def main() -> None:
    server = subprocess.Popen(
        [sys.executable, str(ROOT / 'scripts' / 'serve.py'), str(PORT)],
        stderr=subprocess.DEVNULL,
    )
    nominatim_calls: list[str] = []

    def nominatim(route: Route) -> None:
        nominatim_calls.append(route.request.url)
        # Misspelled names miss in Nominatim; the page must fall back to Photon.
        miss = 'Joes' in route.request.url
        route.fulfill(
            content_type='application/json',
            body=json.dumps(
                [] if miss else [{'lat': '42.3736158', 'lon': '-71.1097335'}]
            ),
        )

    def photon(route: Route) -> None:
        route.fulfill(
            content_type='application/json',
            body=json.dumps(
                {'features': [{'geometry': {'coordinates': [-71.114146, 42.3581395]}}]}
            ),
        )

    try:
        wait_for_server()
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for viewport, scheme in (
                ({'width': 1280, 'height': 900}, 'light'),
                ({'width': 390, 'height': 844}, 'dark'),
            ):
                context = browser.new_context(
                    viewport=viewport,
                    color_scheme=scheme,
                    geolocation={'latitude': 48.8566, 'longitude': 2.3522},
                    permissions=['geolocation', 'clipboard-read', 'clipboard-write'],
                )
                page = context.new_page()
                errors: list[str] = []
                page.on('pageerror', lambda e, errors=errors: errors.append(str(e)))
                page.route('https://tile.openstreetmap.org/**', lambda r: r.abort())
                page.route('https://nominatim.openstreetmap.org/**', nominatim)
                page.route('https://photon.komoot.io/**', photon)

                # Embedded Google URL with its own query string -> canonical path.
                visit(
                    page,
                    '/geo/https://www.google.com/maps/search/?api=1&query=42.364678,-71.131311',
                )
                assert (
                    page.evaluate('location.pathname + location.search')
                    == '/geo/42.364678,-71.131311'
                ), page.url
                n = page.locator('#list a').count()
                assert n > 100, n
                href = page.locator(
                    '#list a', has_text='OpenStreetMap'
                ).first.get_attribute('href')
                assert href and '42.364678' in href, href

                # Featured map, zoom kept, no redirect.
                visit(page, '/geo/42.3646,-71.1313&z=12&m=rwgps')
                assert page.locator('#featured').is_visible()
                open_href = page.locator('#featured a').get_attribute('href')
                assert (
                    open_href
                    == 'https://ridewithgps.com/routes/new?center=42.3646%2C-71.1313&zoom=12'
                ), open_href
                assert page.url.endswith('/geo/42.3646,-71.1313&z=12&m=rwgps'), page.url

                # A framable map opens in place of the pin map; the URL does not change.
                page.route(
                    'https://opentopomap.org/**',
                    lambda r: r.fulfill(content_type='text/html', body='stub'),
                )
                visit(page, '/geo/42.3646,-71.1313&m=opentopomap')
                page.click('#featured a')
                frame = page.locator('#pane iframe')
                src = frame.get_attribute('src')
                assert src and '42.3646' in src, src
                assert 'allow-top-navigation' not in (
                    frame.get_attribute('sandbox') or 'allow-top-navigation'
                )
                assert page.locator('#pane-open').get_attribute('href') == src
                assert page.locator('#map').is_hidden()
                assert page.locator('#pane').is_visible()
                assert page.url.endswith('/geo/42.3646,-71.1313&m=opentopomap')
                # It follows the location.
                page.fill('#q', '42.37,-71.11')
                page.press('#q', 'Enter')
                page.wait_for_function(
                    'document.querySelector("#pane iframe")?.src.includes("42.37")'
                )
                assert page.locator('#pane iframe').count() == 1
                # Side by side, only the list scrolls: the page is one window tall.
                assert viewport['width'] < 768 or page.evaluate(
                    'document.documentElement.scrollHeight <= innerHeight'
                )
                # Expand covers the window; the same button puts it back.
                narrow = page.locator('#pane').bounding_box()['width']
                page.click('#pane-wide')
                assert (
                    page.locator('#pane').bounding_box()['width']
                    == page.viewport_size['width']
                )
                page.click('#pane-wide')
                assert page.locator('#pane').bounding_box()['width'] == narrow
                page.click('#pane-close')
                assert page.locator('#pane').is_hidden()
                assert page.locator('#pane iframe').count() == 0
                assert page.locator('#map').is_visible()
                # A service that refuses framing stays a plain link.
                page.route(
                    'https://www.google.com/**',
                    lambda r: r.fulfill(content_type='text/html', body='stub'),
                )
                visit(page, '/geo/42.3646,-71.1313&m=google')
                page.click('#featured a')
                page.wait_for_url('https://www.google.com/**')

                # Query and hash forms canonicalize to the path form.
                visit(page, '/geo/?42.36,-71.13')
                assert page.evaluate('location.pathname') == '/geo/42.36,-71.13'
                visit(page, '/geo/#42.36,-71.13&z=9')
                assert (
                    page.evaluate('location.pathname + location.search + location.hash')
                    == '/geo/42.36,-71.13&z=9'
                )

                # Regional maps: US services in Cambridge, not in London.
                visit(page, '/geo/42.36,-71.13&m=osmcycle&a=Cambridge')
                assert (
                    page.locator('#list summary', has_text='United States').count() == 1
                )
                page.screenshot(
                    path=str(ROOT / 'tests' / f'.smoke-{viewport["width"]}.png'),
                    full_page=True,
                )
                visit(page, '/geo/51.5,-0.12')
                assert (
                    page.locator('#list summary', has_text='United States').count() == 0
                )
                page.check('#show-regions')
                assert (
                    page.locator('#list summary', has_text='United States').count() == 1
                )
                page.uncheck('#show-regions')

                # Disabled maps: hidden unless asked for, then red links.
                assert page.locator('#list a.disabled').count() == 0
                page.check('#show-disabled')
                dead = page.locator('#list a.disabled', has_text='Qwant Maps')
                assert dead.count() == 1
                assert 'qwant.com' in (dead.get_attribute('href') or '')
                page.uncheck('#show-disabled')

                # Filter.
                page.fill('#filter', 'cyclosm')
                visible = page.locator('#list li:not([hidden])').count()
                assert 1 <= visible < 5, visible
                assert page.locator('#list .count', has_text='shown').count() >= 1
                page.click('#filter-clear')
                assert page.input_value('#filter') == ''
                assert page.locator('#filter-clear').is_hidden()

                # Address -> one geocode -> canonical URL keeps `a`; reload does not geocode again.
                before = len(nominatim_calls)
                visit(page, '/geo/?a=Harvard%20Square,%20Cambridge')
                page.wait_for_function('location.pathname !== "/geo/"')
                want = '/geo/42.373615,-71.109733&a=Harvard%20Square,%20Cambridge'
                assert page.evaluate('location.pathname + location.search') == want, (
                    page.url
                )
                page.reload()
                page.wait_for_selector('#list a')
                assert len(nominatim_calls) == before + 1, nominatim_calls

                # Nominatim miss -> Photon fallback.
                visit(page, '/geo/?a=Trader%20Joes,%20Cambridge')
                page.wait_for_function('location.pathname !== "/geo/"')
                assert page.evaluate('location.pathname').startswith(
                    '/geo/42.358139,-71.114146'
                ), page.url

                # Typed input: coordinates in the box.
                page.fill('#q', '42°21′52.8″N 71°7′52.7″W')
                page.press('#q', 'Enter')
                page.wait_for_function('location.pathname.startsWith("/geo/42.364667")')

                # Zoom control updates the URL.
                visit(page, '/geo/42.36,-71.13')

                # Clearing the location box resets the location but keeps the map view,
                # so the next map click drops a pin in the same area.
                assert page.input_value('#q') == '42.36,-71.13'
                page.click('#q-clear')
                assert page.input_value('#q') == ''
                assert page.locator('#q-clear').is_hidden()
                assert page.evaluate('location.pathname') == '/geo/'
                assert page.locator('.leaflet-marker-icon').count() == 0
                assert page.locator('#list a').count() == 0
                page.click('#map', position={'x': 150, 'y': 150})
                page.wait_for_function('location.pathname.startsWith("/geo/42.3")')
                visit(page, '/geo/42.36,-71.13')
                page.click('.leaflet-control-zoom-in')
                page.wait_for_function('location.pathname === "/geo/42.36,-71.13&z=16"')

                # Dragging the pin moves the point, the URL, and every link.
                osm = page.locator('#list a', has_text='OpenStreetMap').first
                before_href = osm.get_attribute('href')
                box = page.locator('.leaflet-marker-icon').bounding_box()
                assert box
                x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
                page.mouse.move(x, y)
                page.mouse.down()
                page.mouse.move(x + 60, y + 30, steps=8)
                page.mouse.up()
                page.wait_for_function(
                    '!location.pathname.startsWith("/geo/42.36,-71.13")'
                )
                assert page.evaluate('location.pathname').endswith('&z=16'), page.url
                assert osm.get_attribute('href') != before_href

                # My location uses browser geolocation; keeps the zoom.
                page.click('#locate')
                page.wait_for_function(
                    'location.pathname === "/geo/48.8566,2.3522&z=16"'
                )

                # Copy link puts the canonical URL on the clipboard.
                page.click('#copy')
                page.wait_for_selector('#msg.ok')
                assert page.evaluate('navigator.clipboard.readText()') == page.url

                # A label is text, never HTML.
                visit(
                    page,
                    '/geo/42.36,-71.13&a=%3Cimg%20src%3Dx%20onerror%3D%22window.pwned%3D1%22%3E',
                )
                page.wait_for_selector('.leaflet-popup-content')
                assert page.evaluate('window.pwned') is None
                assert page.locator('.leaflet-popup-content img').count() == 0

                # Bare /geo/ shows Cambridge with no pin; a click drops the first pin there.
                page.goto(BASE + '/geo/')
                page.wait_for_function(
                    'document.querySelector("#where").textContent.startsWith("Click")'
                )
                assert page.locator('.leaflet-marker-icon').count() == 0
                assert page.locator('#list a').count() == 0
                page.click('#map', position={'x': 40, 'y': 120})
                page.wait_for_selector('#list a')
                path = page.evaluate('location.pathname')
                lat, lon = (
                    float(v)
                    for v in path.removeprefix('/geo/').split('&')[0].split(',')
                )
                assert (
                    path.endswith('&z=10') and 42.0 < lat < 42.8 and -71.6 < lon < -70.6
                ), path
                assert page.locator('.leaflet-marker-icon').count() == 1

                # Unreadable input shows an error, not a crash.
                visit(page, '/geo/not-a-place')
                assert page.locator('#msg').is_visible()

                # No horizontal scroll on phones.
                overflow = page.evaluate(
                    'document.documentElement.scrollWidth - window.innerWidth'
                )
                assert overflow <= 0, f'horizontal overflow {overflow}px at {viewport}'

                assert not errors, errors
                context.close()
            browser.close()
        print('smoke: ok')
    finally:
        server.terminate()


if __name__ == '__main__':
    main()
