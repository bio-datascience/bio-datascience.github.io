#!/usr/bin/env python3
"""Refresh publications from Google Scholar on demand; never commit or publish.

Usage: python3 scripts/update_publications.py [--check] [--html-dir PATH]
Only the Python standard library is required. --html-dir supports offline review
of saved scholar-profile.html and scholar-profile-older.html pages.
"""
import argparse
import hashlib
from datetime import datetime, timezone
from difflib import SequenceMatcher
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / 'docs/references'


def normalized(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode()
    return re.sub('[^a-z0-9]', '', value.lower())


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def text(fragment):
    parser = PlainText()
    parser.feed(fragment)
    return ' '.join(''.join(parser.parts).split())


def parse_page(page):
    rows = re.findall(r'<tr\b[^>]*class=["\']gsc_a_tr["\'][^>]*>(.*?)</tr>', page, re.S)
    if not rows:
        raise ValueError('No Scholar article rows found. Access may be blocked or the page format changed; no files were updated.')
    records = []
    for row in rows:
        title = re.search(r'<a\b(?=[^>]*class=["\']gsc_a_at["\'])(?=[^>]*href=["\']([^"\']+)["\'])[^>]*>(.*?)</a>', row, re.S)
        year_cell = re.search(r'<td\b[^>]*class=["\']gsc_a_y["\'][^>]*>(.*?)</td>', row, re.S)
        if not title or not year_cell:
            raise ValueError('Incomplete Scholar row; refusing a partial refresh.')
        year_text = text(year_cell[1])
        year = int(year_text) if re.fullmatch(r'\d{4}', year_text) else None
        gray = re.findall(r'<div\b[^>]*class=["\']gs_gray["\'][^>]*>(.*?)</div>', row, re.S)
        url = urljoin('https://scholar.google.com', unescape(title[1]))
        citation_id = parse_qs(urlparse(url).query).get('citation_for_view', [None])[0]
        if not citation_id:
            raise ValueError('Missing Scholar citation identifier; refusing a partial refresh.')
        records.append({'title': text(title[2]), 'authors': text(gray[0]) if gray else '',
                        'venue': text(gray[1]) if len(gray) > 1 else '', 'year': year,
                        'scholar': url, 'scholar_id': citation_id})
    return records


def fetch_page(profile, start):
    url = 'https://scholar.google.com/citations?' + urlencode({
        'user': profile, 'sortby': 'pubdate', 'pagesize': 100, 'cstart': start, 'hl': 'en'})
    request = Request(url, headers={'User-Agent': 'BioDS publication updater (manual run)'})
    with urlopen(request, timeout=30) as response:
        return response.read().decode(response.headers.get_content_charset() or 'utf-8')


def reconcile(current, incoming, settings):
    aliases = {normalized(a): normalized(b) for a, b in settings['title_aliases'].items()}
    def canonical(title):
        key = normalized(title)
        return aliases.get(key, key)
    excluded = {canonical(t) for t in settings['excluded_titles']}
    output = [dict(p) for p in current if canonical(p['title']) not in excluded]
    index = {canonical(p['title']): i for i, p in enumerate(output)}
    ids = {p['scholar_id']: i for i, p in enumerate(output) if p.get('scholar_id')}
    seen = set()
    counts = {'added': 0, 'matched': 0, 'duplicates': 0, 'excluded': 0}
    for record in incoming:
        key = canonical(record['title'])
        if key in excluded:
            counts['excluded'] += 1
            continue
        if key in seen:
            counts['duplicates'] += 1
            continue
        seen.add(key)
        idx = ids.get(record['scholar_id'], index.get(key))
        if idx is None:
            # Existing publisher citations can differ slightly in punctuation or subtitle.
            matches = [(SequenceMatcher(None, key, k).ratio(), i) for k, i in index.items()]
            best = max(matches, default=(0, None))
            if best[0] >= .94:
                idx = best[1]
        if idx is not None:
            p = output[idx]
            p['scholar'] = record['scholar']
            p['scholar_id'] = record['scholar_id']
            if not p.get('authors'):
                p['authors'] = record['authors']
            # Preserve verified publisher metadata and full author lists from the export.
            if not p.get('year') and record['year']:
                p['year'] = record['year']
            counts['matched'] += 1
        else:
            p = dict(record)
            p['source'] = 'Google Scholar profile (on-demand refresh)'
            p['venue'] = record['venue'] or (str(record['year']) if record['year'] else 'Year not supplied')
            output.append(p)
            idx = len(output) - 1
            counts['added'] += 1
        index[key] = idx
        ids[record['scholar_id']] = idx
    output.sort(key=lambda p: (-(p.get('year') or 0), p['title'].casefold()))
    return output, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Report proposed refresh without changing files')
    parser.add_argument('--html-dir', type=Path, help='Read saved Scholar HTML instead of fetching the profile')
    args = parser.parse_args()
    settings = json.loads((REFERENCES / 'publication-settings.json').read_text())
    current = json.loads((REFERENCES / 'publication-records.json').read_text())
    incoming = []
    pages = []
    if args.html_dir:
        pages = sorted(args.html_dir.glob('scholar-profile*.html'))
        if not pages:
            raise ValueError('No saved Scholar pages found.')
        for path in pages:
            data = path.read_bytes()
            try:
                page = data.decode('utf-8')
            except UnicodeDecodeError:
                page = data.decode('latin-1')
            incoming.extend(parse_page(page))
    else:
        for start in range(0, 10000, 100):
            rows = parse_page(fetch_page(settings['profile'], start))
            incoming.extend(rows)
            if len(rows) < 100:
                break
        else:
            raise ValueError('Pagination safety limit reached; no files updated.')
    # Detect truncated results, CAPTCHA pages and repeated pagination before writing.
    unique_ids = {p['scholar_id'] for p in incoming}
    if len(unique_ids) != len(incoming):
        raise ValueError('Repeated citation identifiers across pages; no files updated.')
    if len(incoming) < settings.get('minimum_profile_records', 100):
        raise ValueError('Unexpectedly short profile; no files updated. Review access and source first.')
    if any(not p['scholar_id'].startswith(settings['profile'] + ':') for p in incoming):
        raise ValueError('Unexpected Scholar profile identity; no files updated.')
    updated, counts = reconcile(current, incoming, settings)
    source_path = ROOT / 'app.js'
    source = source_path.read_text()
    payload = json.dumps(updated, ensure_ascii=False)
    revised, replacements = re.subn(r'const publicationRecords=.*?;\n',
        lambda _: 'const publicationRecords=' + payload + ';\n', source, count=1)
    if replacements != 1:
        raise ValueError('Cannot locate website publication data; no files updated.')
    summary = {'profile_records': len(incoming), 'displayed_records': len(updated), **counts}
    print(json.dumps(summary, indent=2))
    if args.check:
        print('Preview only; no files changed.')
        return
    # All fetching, parsing and validation finishes before modifying website files.
    (REFERENCES / 'publication-records.json').write_text(json.dumps(updated, ensure_ascii=False, indent=2) + '\n')
    source_path.write_text(revised)
    index_path = ROOT / 'index.html'
    version = hashlib.sha256(revised.encode()).hexdigest()[:12]
    index_path.write_text(re.sub(r'app\.js(?:\?v=[a-z0-9]+)?"', 'app.js?v=' + version + '"', index_path.read_text()))
    (REFERENCES / 'publication-last-refresh.json').write_text(json.dumps({
        'checked_at': datetime.now(timezone.utc).isoformat(), **summary}, indent=2) + '\n')
    print('Updated local publication data. Run site checks and review before committing or publishing.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Publication refresh failed: {error}', file=sys.stderr)
        sys.exit(1)
