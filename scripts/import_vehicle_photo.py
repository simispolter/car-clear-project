"""Import a manually reviewed Commons photo; never guess a model from a search hit.

Run --help for the required review and model-generation parameters.
"""
import argparse
import hashlib
import html
import json
import pathlib
import re
import sqlite3
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
FREE_LICENSES = {'CC0', 'Public domain', 'CC BY 2.0', 'CC BY 2.5', 'CC BY 3.0', 'CC BY 4.0',
                 'CC BY-SA 2.0', 'CC BY-SA 2.5', 'CC BY-SA 3.0', 'CC BY-SA 4.0'}


def plain(value):
    return html.unescape(re.sub(r'<[^>]*>', '', value)).strip()


def license_record(info):
    meta = info.get('extmetadata', {})
    license_name = plain(meta.get('LicenseShortName', {}).get('value', ''))
    author = plain(meta.get('Artist', {}).get('value', ''))
    license_url = meta.get('LicenseUrl', {}).get('value', '')
    if license_url.startswith('//'):
        license_url = 'https:' + license_url
    if license_name not in FREE_LICENSES or not author or not license_url.startswith('https://'):
        raise ValueError('Unsupported/missing photo license, license URL or attribution. Nothing was imported.')
    return dict(license=license_name, author=author, license_url=license_url)


def fetch(url, user_agent, limit):
    if urllib.parse.urlparse(url).scheme != 'https' or urllib.parse.urlparse(url).hostname not in ['commons.wikimedia.org', 'upload.wikimedia.org']:
        raise ValueError('Unexpected photo destination')
    request = urllib.request.Request(url, headers={'User-Agent': user_agent})
    with urllib.request.urlopen(request, timeout=30) as response:
        if urllib.parse.urlparse(response.geturl()).scheme != 'https' or urllib.parse.urlparse(response.geturl()).hostname not in ['commons.wikimedia.org', 'upload.wikimedia.org']:
            raise ValueError('Unexpected redirect destination')
        content = response.read(limit + 1)
        if len(content) > limit:
            raise ValueError('Response exceeds size limit')
        return content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--make', required=True, help='Exact Hebrew make in the local catalog')
    parser.add_argument('--model', required=True, help='Exact model name in the local catalog')
    parser.add_argument('--year-from', required=True, type=int)
    parser.add_argument('--year-to', required=True, type=int)
    parser.add_argument('--commons-file', required=True, help='Reviewed Commons File: title')
    parser.add_argument('--reviewed-by', required=True, help='Person who verified model, generation and body')
    parser.add_argument('--user-agent', required=True, help='Project name plus real contact per Wikimedia policy')
    args = parser.parse_args()
    if not 1990 <= args.year_from <= args.year_to <= 2035 or not args.reviewed_by.strip():
        parser.error('Valid generation years and a reviewer are required')
    with sqlite3.connect('file:' + str(ROOT / 'data/catalog.sqlite') + '?mode=ro', uri=True) as db:
        count = db.execute('SELECT COUNT(*) FROM cars WHERE make=? AND model=? AND year BETWEEN ? AND ? AND active_count>10',
                           (args.make, args.model, args.year_from, args.year_to)).fetchone()[0]
    if not count:
        parser.error('No eligible local catalog version matches this exact model/year interval')
    registry = ROOT / 'data/vehicle-photos.json'
    records = json.loads(registry.read_text()) if registry.exists() else []
    if any(p['make'] == args.make and p['model'] == args.model
           and p['year_from'] <= args.year_to and p['year_to'] >= args.year_from for p in records):
        raise ValueError('A photo already covers part of this interval; review its metadata before replacing it')
    title = args.commons_file if args.commons_file.startswith('File:') else 'File:' + args.commons_file
    query = urllib.parse.urlencode(dict(action='query', format='json', titles=title, prop='imageinfo',
                                       iiprop='url|extmetadata|mime', iiurlwidth=1200))
    response = json.loads(fetch('https://commons.wikimedia.org/w/api.php?' + query, args.user_agent, 1000000))
    pages = response.get('query', {}).get('pages', {})
    info = next((p['imageinfo'][0] for p in pages.values() if p.get('imageinfo')), None)
    if not info:
        raise ValueError('The selected Commons file has no image metadata')
    attribution = license_record(info)
    extension = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'}.get(info.get('mime'))
    if not extension:
        raise ValueError('Only JPEG, PNG and WebP photos are supported')
    data = fetch(info.get('thumburl', info['url']), args.user_agent, 10000000)
    # Basic media signature validation; do not persist HTML/error responses as photographs.
    valid = ((extension == 'jpg' and data.startswith(b'\xff\xd8\xff'))
             or (extension == 'png' and data.startswith(b'\x89PNG\r\n\x1a\n'))
             or (extension == 'webp' and data[:4] == b'RIFF' and data[8:12] == b'WEBP'))
    if not valid:
        raise ValueError('Downloaded bytes do not match the declared image type')
    digest = hashlib.sha256(data).hexdigest()
    filename = 'vehicles/' + digest[:20] + '.' + extension
    destination = ROOT / 'app/static' / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
        raise ValueError('An existing local photo conflicts with this content hash')
    destination.write_bytes(data)
    entry = dict(make=args.make, model=args.model, year_from=args.year_from, year_to=args.year_to,
                 approved=True, file=filename, source_url='https://commons.wikimedia.org/wiki/' + urllib.parse.quote(title),
                 image_sha256=digest, reviewed_by=args.reviewed_by.strip(), changes='Scaled thumbnail from Commons; no other edits.',
                 scope='Model-generation illustration; exact local trim is not implied.', **attribution)
    records.append(entry)
    temporary = registry.with_suffix('.json.building')
    temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(registry)
    print('Imported photo for', args.make, args.model, args.year_from, '–', args.year_to, 'under', attribution['license'])
    print('Restart the application to refresh its photo registry.')


if __name__ == '__main__':
    main()
