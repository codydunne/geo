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
        route.fulfill(
            content_type='application/json',
            body=json.dumps([{'lat': '42.3736158', 'lon': '-71.1097335'}]),
        )

    try:
        wait_for_server()
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for viewport, scheme in (
                ({'width': 1280, 'height': 900}, 'light'),
                ({'width': 390, 'height': 844}, 'dark'),
            ):
                page = browser.new_page(viewport=viewport, color_scheme=scheme)
                errors: list[str] = []
                page.on('pageerror', lambda e, errors=errors: errors.append(str(e)))
                page.route('https://tile.openstreetmap.org/**', lambda r: r.abort())
                page.route('https://nominatim.openstreetmap.org/**', nominatim)

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

                # Filter.
                page.fill('#filter', 'cyclosm')
                visible = page.locator('#list li:not([hidden])').count()
                assert 1 <= visible < 5, visible

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

                # Typed input: coordinates in the box.
                page.fill('#q', '42°21′52.8″N 71°7′52.7″W')
                page.press('#q', 'Enter')
                page.wait_for_function('location.pathname.startsWith("/geo/42.364667")')

                # Unreadable input shows an error, not a crash.
                visit(page, '/geo/not-a-place')
                assert page.locator('#msg').is_visible()

                # No horizontal scroll on phones.
                overflow = page.evaluate(
                    'document.documentElement.scrollWidth - window.innerWidth'
                )
                assert overflow <= 0, f'horizontal overflow {overflow}px at {viewport}'

                assert not errors, errors
                page.close()
            browser.close()
        print('smoke: ok')
    finally:
        server.terminate()


if __name__ == '__main__':
    main()
