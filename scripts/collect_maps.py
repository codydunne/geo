#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Collect map link formats from GeoHack and OpenSwitchMaps into web/_/maps.json.

Run `uv run scripts/collect_maps.py`, review the diff, and commit by hand.
Third-party JS is parsed with regexes, never executed.
"""

from __future__ import annotations

import json
import math
import re
import sys
import unicodedata
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'web' / '_' / 'maps.json'
OVERRIDES = ROOT / 'scripts' / 'maps-overrides.json'

GEOTEMPLATE = (
    'https://en.wikipedia.org/w/index.php?title=Template:GeoTemplate&action=raw'
)
# Pinned so a re-run is reproducible; bump deliberately and review the diff.
OSM_SOURCES = {
    'osmw': 'https://raw.githubusercontent.com/tankaru/OpenSwitchMapsWeb/04467250a81c7d19a3513a4ff52dc5b51cf8e218/maps.js',
    'osm': 'https://raw.githubusercontent.com/tankaru/OpenSwitchMaps/49ea3ffb2d4681d95744582d4cc96b153ba96112/src/maps.js',
}
NATURAL_EARTH = 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/ca96624a56bd078437bca8184e78163e5039ad19/geojson/ne_50m_admin_0_countries.geojson'
SOURCES = {
    'gh': 'GeoHack, en.wikipedia.org Template:GeoTemplate (CC BY-SA 4.0)',
    'osmw': 'OpenSwitchMapsWeb maps.js @0446725 (MIT, (c) tankaru)',
    'osm': 'OpenSwitchMaps maps.js @49ea3ff (MIT, (c) tankaru)',
    'ne': 'Natural Earth 1:50m admin-0 (public domain), region bboxes',
    'x': 'Hand-maintained overrides',
}
PLACEHOLDERS = {'lat', 'lon', 'z', 'scale', 'mqzoom', 'w', 's', 'e', 'n', 'a'}
# {language} is the reader's wiki language; this site is English-only.
GH_VARS = {
    'language': 'en',
    'latdegdec': 'lat',
    'londegdec': 'lon',
    'osmzoom': 'z',
    'zoom': 'mqzoom',
    'scale': 'scale',
    'titlee': 'a',
    'title': 'a',
}

Map = dict[str, Any]
dropped: Counter[str] = Counter()


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'dunne.dev/geo collector (c.dunne@northeastern.edu)'},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode()


def clean(s: str) -> str:
    """Wikitext/HTML label -> plain text."""
    s = re.sub(r'\[\[File:[^\]]*\]\]|<sup>.*?</sup>', '', s)
    s = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]', r'\1', s)
    s = re.sub(r'\{\{lang\|[^|}]*\|([^|}]*)[^}]*\}\}', r'\1', s)
    s = re.sub(r'\{\{pipe\}\}', '/', s)
    s = re.sub(r'\{\{[^}]*\}\}', '', s)
    s = re.sub(r"<[^>]+>|'''?|&nbsp;", ' ', s)
    s = re.sub(r'\s+', ' ', s).strip(' ,')
    # Drop only an unbalanced wrapping paren, e.g. "(+Wikipedia" from "([url +Wikipedia])".
    if s.startswith('(') and s.count('(') > s.count(')'):
        s = s[1:]
    if s.endswith(')') and s.count(')') > s.count('('):
        s = s[:-1]
    return s.strip()


# --- GeoHack -----------------------------------------------------------------


def gh_template(url: str) -> str | None:
    if '{{' in url:
        dropped['gh: parser function'] += 1
        return None

    def sub(m: re.Match[str]) -> str:
        v = GH_VARS.get(m[1])
        return '{?' + m[1] + '}' if v is None else v if v == 'en' else '{' + v + '}'

    out = re.sub(r'\{(\w+)\}', sub, url)
    if bad := re.search(r'\{\?(\w+)', out):
        dropped['gh: unsupported placeholder ' + bad[1]] += 1
        return None
    if '{lat}' not in out or '{lon}' not in out:
        dropped['gh: no lat/lon'] += 1
        return None
    return 'https:' + out if out.startswith('//') else out


def geohack(text: str) -> list[Map]:
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    # Skip the header box and the "Popular" icons; they repeat the tables below.
    text = text[text.index('== Global') :]
    maps: list[Map] = []
    section, codes, row, first = '', [], '', True
    pending: list[str] = []
    row_start = False
    for line in text.splitlines():
        if m := re.search(r'id="GEOTEMPLATE-([A-Z]{2})"', line):
            pending.append(m[1])
        if m := re.match(r'^(=+)\s*(.*?)\s*\1\s*$', line):
            if len(m[1]) <= 2 or pending:
                section, codes, pending = m[2], pending, []
            row = ''  # a row name never carries across headings
            continue
        if line.startswith('|}'):
            row = ''
            continue
        if line.startswith('|-'):
            row_start = True
            continue
        # The row name is a `! scope="row"` header, or plain text (no links) opening a
        # row, either in the first cell or on the line after an empty `|`.
        if row_start and line.strip() == '|':
            continue
        m = re.match(r'^!\s*scope="row"[^|]*\|\s*(.*)$', line)
        if (
            not m
            and row_start
            and '//' not in line
            and not line.startswith(('{', '!', '*'))
        ):
            m = re.match(r'^\|?\s*(.+)$', line)
        row_start = False
        if m:
            row, first = clean(m[1]), True
            continue
        for um in re.finditer(r'\[((?:https?:)?//\S+)\s+([^\]]*)\]', line):
            u = gh_template(um[1])
            label = clean(um[2])
            if u is None:
                continue
            name = (
                row if (first and row) else f'{row} {label}'.strip() if row else label
            )
            first = False
            maps.append(
                {'n': name, 'c': section, 'u': u, 's': ['gh']}
                | ({'r': codes} if codes else {})
            )
    return maps


# --- OpenSwitchMaps -------------------------------------------------------------

JS_VAR = {'lat': '{lat}', 'lon': '{lon}', 'zoom': '{z}'}
# lat/lon/zoom, optionally wrapped in a rounding call that changes nothing for us.
JS_REF = r'(?:Math\.(?:round|floor)\(\s*(zoom)\s*\)|Number\(\s*(lat|lon)\s*\)\.toFixed\(\d+\)|\b(lat|lon|zoom|\w+)\b)'


def strip_if_extra(body: str) -> str | None:
    """Drop `if (extra ...) { ... }` blocks: with no `extra` (pins etc.) they never run."""
    while m := re.search(r'\bif\s*\(\s*extra\b', body):
        i = body.index('{', m.end())
        depth = 0
        for j in range(i, len(body)):
            depth += {'{': 1, '}': -1}.get(body[j], 0)
            if depth == 0:
                break
        if re.match(r'\s*else\b', body[j + 1 :]):
            return None
        body = body[: m.start()] + body[j + 1 :]
    return body


def js_template(body: str) -> str | None:
    """getUrl body -> template, evaluated with `extra` undefined; None if it computes anything."""
    body = '\n'.join(ln for ln in body.splitlines() if not ln.strip().startswith('//'))
    stripped = strip_if_extra(body)
    if stripped is None:
        return None
    body = stripped
    empty = set(re.findall(r"\b(?:let|const|var)\s+(\w+)\s*=\s*(?:\"\"|'')\s*;", body))
    body = re.sub(r"\b(?:let|const|var)\s+\w+\s*=\s*(?:\"\"|'')\s*;", '', body).strip()
    m = re.fullmatch(r'return\s+(.*?);?', body, re.DOTALL)
    if not m:
        return None
    expr = m[1].strip()

    def ref(name: str) -> str | None:
        if name in JS_VAR:
            return JS_VAR[name]
        return '' if name in empty else None

    out, pos = [], 0
    tok = re.compile(
        r"""\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)'|`([^`]*)`|"""
        + JS_REF
        + r'|(\+))\s*'
    )
    while pos < len(expr):
        t = tok.match(expr, pos)
        if not t or t.end() == pos:
            return None
        pos = t.end()
        if t[1] is not None or t[2] is not None:
            out.append((t[1] if t[1] is not None else t[2]).replace('\\', ''))
        elif t[3] is not None:
            parts = re.split(r'\$\{([^}]*)\}', t[3])
            for i, part in enumerate(parts):
                if i % 2 == 0:
                    out.append(part)
                    continue
                part = part.strip()
                if part.startswith('extra'):
                    continue
                r = re.fullmatch(JS_REF, part)
                v = ref(r[1] or r[2] or r[3]) if r else None
                if v is None:
                    return None
                out.append(v)
        elif t[7] is None:
            v = ref(t[4] or t[5] or t[6])
            if v is None:
                return None
            out.append(v)
    return ''.join(out)


def js_regex_literal(s: str, start: int) -> tuple[str, str] | None:
    """Body and flags of the /.../ literal starting at s[start] == '/'."""
    i, cls = start + 1, False
    while i < len(s):
        ch = s[i]
        if ch == '\\':
            i += 2
            continue
        if ch == '[':
            cls = True
        elif ch == ']':
            cls = False
        elif ch == '/' and not cls:
            flags = re.match(r'[a-z]*', s[i + 1 :])
            return s[start + 1 : i], flags[0] if flags else ''
        i += 1
    return None


def name_groups(body: str, names: list[str]) -> str | None:
    """Give the n-th capturing group the n-th name ('' leaves it unnamed)."""
    out, i, n, cls = [], 0, 0, False
    while i < len(body):
        ch = body[i]
        if ch == '\\':
            out.append(body[i : i + 2])
            i += 2
            continue
        if ch == '[':
            cls = True
        elif ch == ']':
            cls = False
        elif ch == '(' and not cls and not body.startswith('(?', i):
            if n >= len(names):
                return None
            out.append(f'(?<{names[n]}>' if names[n] else '(')
            n += 1
            i += 1
            continue
        out.append(ch)
        i += 1
    return ''.join(out) if n == len(names) else None


def js_pattern(fn: str) -> str | None:
    """Single url.match + destructure -> named-group pattern, else None."""
    if fn.count('.match(') != 1 or re.search(r'\belse\b', fn):
        return None
    m = re.search(r'\.match\(\s*/', fn)
    lit = js_regex_literal(fn, m.end() - 1) if m else None
    d = re.search(r'\[\s*,\s*([\w\s,]+)\]\s*=\s*match', fn)
    if not lit or lit[1] or not d:
        return None
    vars_ = [v.strip() for v in d[1].split(',')]
    group = {'lat': 'lat', 'lon': 'lon', 'zoom': 'z'}
    if not {'lat', 'lon'} <= set(vars_) or any(v not in group for v in vars_):
        return None
    return name_groups(lit[0], [group[v] for v in vars_])


LOCAL_CATEGORIES = {'LOCAL_CATEGORY', 'OSM_LOCAL_CATEGORY'}
NOT_CCTLD = {'io', 'me', 'co', 'tv', 'ai', 'app', 'xyz'}


def local_region(m: Map, by_name: dict[str, str]) -> str | None:
    """Country for an OpenSwitchMaps "local" entry: override, `(XX)` suffix,
    Japanese script, or ccTLD, in that order."""
    if code := by_name.get(m['n']):
        return code
    if s := re.search(r'\(([A-Z]{2})\)\s*$', m['n']):
        return {'UK': 'GB'}.get(s[1], s[1])
    if re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', m['n']):
        return 'JP'
    tld = host(m['u']).rsplit('.', 1)[-1]
    if len(tld) == 2 and tld not in NOT_CCTLD:
        return {'uk': 'GB'}.get(tld, tld.upper())
    return None


def osm(text: str, src: str) -> list[Map]:
    cats = dict(re.findall(r'const (\w+_CATEGORY) = "([^"]*)"', text))
    maps: list[Map] = []
    for chunk in re.split(r'\n\t\{\s*\n', text)[1:]:
        name = re.search(r'\bname:\s*"([^"]*)"', chunk)
        if not name:
            continue
        cat = re.search(r'\bcategory:\s*(\w+)', chunk)
        get = re.search(r'getUrl\([^)]*\)\s*\{(.*?)\n\t\t\},', chunk, re.DOTALL)
        u = js_template(get[1]) if get else None
        if not u or '{lat}' not in u or not u.startswith('http'):
            dropped[f'{src}: computed getUrl'] += 1
            print(f'  unhandled {src}: {name[1]}', file=sys.stderr)
            continue
        m: Map = {
            'n': name[1],
            'c': cats.get(cat[1] if cat else '', 'Other maps'),
            'u': u,
            '_local': bool(cat) and cat[1] in LOCAL_CATEGORIES,
            's': [src],
        }
        parse = re.search(r'getLatLonZoom\(url\)\s*\{(.*?)\n\t\t\},', chunk, re.DOTALL)
        if parse and (p := js_pattern(parse[1])):
            m['p'] = [p]
        maps.append(m)
    return maps


# --- Merge, overrides, IDs -------------------------------------------------------


def host(u: str) -> str:
    return re.sub(
        r'^www\.', '', urlsplit(u.replace('{', '').replace('}', '')).netloc.lower()
    )


def ukey(u: str) -> str:
    return re.sub(r'^https?://(www\.)?|/$', '', u.lower())


def nkey(m: Map) -> tuple[str, str]:
    return (m['n'].casefold(), host(m['u']))


def slug(name: str, u: str) -> str:
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
    return s or re.sub(r'[^a-z0-9]+', '-', host(u)).strip('-')


def merge(groups: list[list[Map]]) -> list[Map]:
    """First occurrence wins; later duplicates (same template or same name+host) add sources."""
    out: list[Map] = []
    seen: dict[Any, Map] = {}
    for group in groups:
        for m in group:
            hit = seen.get(ukey(m['u'])) or seen.get(nkey(m))
            if hit:
                hit['s'] = sorted(set(hit['s']) | set(m['s']))
                if 'p' in m and 'p' not in hit:
                    hit['p'] = m['p']
                continue
            out.append(m)
            seen[ukey(m['u'])] = seen[nkey(m)] = m
    return out


SAMPLE = {
    'lat': '42.364678',
    'lon': '-71.131311',
    'z': '13',
    'scale': '108352',
    'mqzoom': '6',
    'w': '-71.2',
    's': '42.3',
    'e': '-71.1',
    'n': '42.4',
    'a': '',
}


def check_patterns(maps: list[Map]) -> None:
    """Drop parse patterns that cannot read back their own map's link (upstream
    template/pattern mismatches, or a merge pairing one source's template with
    another's pattern). JS (?<name>) is Python (?P<name>); the node test re-checks in JS."""
    for m in maps:
        u = re.sub(r'\{(\w+)\}', lambda g: SAMPLE[g[1]], m['u'])
        ok = []
        for p in m.get('p', []):
            try:
                g = re.search(p.replace('(?<', '(?P<'), u)
            except re.error:
                g = None
            if g and float(g['lat']) == 42.364678 and float(g['lon']) == -71.131311:
                ok.append(p)
            else:
                dropped['pattern: no round trip'] += 1
                print(f'  dropped pattern for {m["n"]}', file=sys.stderr)
        if ok:
            m['p'] = ok
        else:
            m.pop('p', None)


def apply_overrides(maps: list[Map], ov: dict[str, Any]) -> tuple[list[Map], set[str]]:
    by_name = {m['n'].casefold(): m for m in maps}
    cat_alias: dict[str, str] = ov.get('categories', {})
    for m in maps:
        m['c'] = cat_alias.get(m['c'], m['c'])
    dropped_ids: set[str] = set()
    for o in ov['maps']:
        o = dict(o)
        target = by_name.get(o.pop('match', o.get('n', '')).casefold())
        if o.pop('drop', False):
            dropped_ids.add(o['id'])
            if target:
                maps.remove(target)
            continue
        if target:
            target.update(o)
        elif 'u' in o:
            maps.append(o | {'s': ['x']})
        else:
            print(f'  override {o["id"]}: no map matched', file=sys.stderr)
    return maps, dropped_ids


def assign_ids(maps: list[Map], prev: list[Map]) -> None:
    prev_by_u = {ukey(m['u']): m['id'] for m in prev}
    prev_by_n = {nkey(m): m['id'] for m in prev}
    taken = {m['id'] for m in maps if 'id' in m}
    for m in maps:
        if 'id' in m:
            continue
        pid = prev_by_u.get(ukey(m['u'])) or prev_by_n.get(nkey(m))
        if pid and pid not in taken:
            m['id'] = pid
        else:
            base = slug(m['n'], m['u'])
            m['id'] = next(
                c
                for i in range(1, 999)
                if (c := base if i == 1 else f'{base}-{i}') not in taken
            )
        taken.add(m['id'])


# --- Regions ---------------------------------------------------------------------


def boxes(geom: dict[str, Any]) -> list[list[float]]:
    """Per-polygon bboxes, merged when within 1 degree, so archipelagos collapse but
    overseas territories and antimeridian halves stay separate."""
    polys = (
        geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
    )
    bs = []
    for poly in polys:
        xs = [p[0] for p in poly[0]]
        ys = [p[1] for p in poly[0]]
        bs.append([min(xs), min(ys), max(xs), max(ys)])
    merged = True
    while merged:
        merged = False
        for i in range(len(bs)):
            for j in range(i + 1, len(bs)):
                a, b = bs[i], bs[j]
                if (
                    a[0] - 1 <= b[2]
                    and b[0] - 1 <= a[2]
                    and a[1] - 1 <= b[3]
                    and b[1] - 1 <= a[3]
                ):
                    bs[i] = [
                        min(a[0], b[0]),
                        min(a[1], b[1]),
                        max(a[2], b[2]),
                        max(a[3], b[3]),
                    ]
                    del bs[j]
                    merged = True
                    break
            if merged:
                break
    # Round outward so the box never shrinks.
    return sorted([[_fl(b[0]), _fl(b[1]), _ce(b[2]), _ce(b[3])] for b in bs])


def _fl(x: float) -> float:
    return math.floor(x * 100) / 100


def _ce(x: float) -> float:
    return math.ceil(x * 100) / 100


def regions(maps: list[Map], ov: dict[str, Any]) -> dict[str, list[list[float]]]:
    alias: dict[str, Any] = ov.get('regions', {})
    # Resolve aliases: a string renames the code, a list is an inline bbox list, null means global.
    for m in maps:
        if 'r' not in m:
            continue
        r: list[Any] = []
        for code in m['r']:
            a = alias.get(code, code)
            if a is None:
                r = []
                break
            r.extend(a if isinstance(a, list) else [a])
        if r:
            m['r'] = r
        else:
            del m['r']
    need = {c for m in maps for c in m.get('r', []) if isinstance(c, str)}
    ne = json.loads(fetch(NATURAL_EARTH))
    out: dict[str, list[list[float]]] = {}
    for f in ne['features']:
        code = f['properties']['ISO_A2_EH']
        if code in need:
            out.setdefault(code, []).extend(boxes(f['geometry']))
    for c in sorted(need - out.keys()):
        print(
            f'  no bbox for region {c}; its maps are shown everywhere', file=sys.stderr
        )
        for m in maps:
            if c in m.get('r', []):
                m['r'] = [r for r in m['r'] if r != c]
                if not m['r']:
                    del m['r']
    return dict(sorted(out.items()))


# --- Main ------------------------------------------------------------------------


def check(data: dict[str, Any], prev: list[Map], dropped_ids: set[str]) -> None:
    ids = [m['id'] for m in data['maps']]
    assert len(ids) == len(set(ids)), 'duplicate ids'
    assert all(re.fullmatch(r'[a-z0-9][a-z0-9-]*', i) for i in ids), 'bad id'
    missing = {m['id'] for m in prev} - set(ids) - dropped_ids
    assert not missing, f'published ids vanished: {missing}'
    for m in data['maps']:
        bad = set(re.findall(r'\{(\w*)\}', m['u'])) - PLACEHOLDERS
        assert not bad, f'{m["id"]}: unknown placeholders {bad}'
        assert m['u'].startswith(('https://', 'http://')), m['id']


def main() -> None:
    ov = json.loads(OVERRIDES.read_text())
    prev: list[Map] = json.loads(OUT.read_text())['maps'] if OUT.exists() else []

    print('fetching GeoHack, OpenSwitchMaps...', file=sys.stderr)
    groups = [osm(fetch(url), src) for src, url in OSM_SOURCES.items()]
    groups.append(geohack(fetch(GEOTEMPLATE)))
    maps = merge(groups)
    for m in maps:
        if m.pop('_local', False) and 'r' not in m:
            if code := local_region(m, ov.get('local', {})):
                m['r'] = [code]
            else:
                print(f'  local map without region: {m["n"]}', file=sys.stderr)
    maps, dropped_ids = apply_overrides(maps, ov)

    # IDs first, so an entry that kept its name+host but changed its template
    # inherits its published id instead of leaving a stale copy behind.
    assign_ids(maps, prev)
    # Keep previously published entries that vanished upstream until explicitly dropped.
    have = {ukey(m['u']) for m in maps} | {m['id'] for m in maps}
    kept = [
        m
        for m in prev
        if m['id'] not in dropped_ids
        and m['id'] not in have
        and ukey(m['u']) not in have
    ]
    for m in kept:
        print(f'  kept (gone upstream): {m["id"]}', file=sys.stderr)
    maps += kept

    check_patterns(maps)
    reg = regions(maps, ov)
    order = {c: i for i, c in enumerate(ov.get('order', []))}
    maps.sort(
        key=lambda m: (
            order.get(m['c'], len(order)),
            'r' in m,
            m['c'],
            m['n'].casefold(),
        )
    )
    keys = ['id', 'n', 'c', 'u', 'p', 'r', 's']
    data = {
        'v': 1,
        'src': SOURCES,
        'geocoder': ov['geocoder'],
        'maps': [{k: m[k] for k in keys if k in m} for m in maps],
        'regions': reg,
    }
    check(data, prev, dropped_ids)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n')

    new = {m['id'] for m in maps} - {m['id'] for m in prev}
    print(
        f'wrote {OUT.relative_to(ROOT)}: {len(maps)} maps, {len(reg)} regions',
        file=sys.stderr,
    )
    print(
        f'  per source: {dict(Counter(s for m in maps for s in m["s"]))}',
        file=sys.stderr,
    )
    print(
        f'  with parse patterns: {sum("p" in m for m in maps)}; new ids: {len(new)}',
        file=sys.stderr,
    )
    for reason, n in sorted(dropped.items()):
        print(f'  dropped {n:4d}  {reason}', file=sys.stderr)


if __name__ == '__main__':
    main()
