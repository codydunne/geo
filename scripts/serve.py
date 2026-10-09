#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Local server that mirrors production routing: web/ is mounted at /geo/,
/geo/_/* are static assets, and every other /geo/* path serves index.html
(production does this with a Cloudflare rewrite)."""

from __future__ import annotations

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

WEB = Path(__file__).resolve().parent.parent / 'web'


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        if urlsplit(self.path).path in ('/', '/geo'):
            self.send_response(302)
            self.send_header('Location', '/geo/')
            self.end_headers()
            return
        super().do_GET()

    def translate_path(self, path: str) -> str:
        if urlsplit(path).path.startswith('/geo/_/'):
            return super().translate_path(path.removeprefix('/geo'))
        return str(WEB / 'index.html')


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(
        ('127.0.0.1', port), partial(Handler, directory=str(WEB))
    )
    print(f'http://127.0.0.1:{port}/geo/', file=sys.stderr)
    server.serve_forever()


if __name__ == '__main__':
    main()
