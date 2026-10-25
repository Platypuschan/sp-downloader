"""Discover the provider's episode catalog and download its available streams."""
import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

BASE = 'https://www.southpark.de'


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def fetch(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=45) as r:
                text = r.read().decode('utf-8')
                if 'json' in r.headers.get('Content-Type', ''):
                    return json.loads(text)
            match = re.search(r'window\.__DATA__\s*=\s*', text)
            if not match:
                raise ValueError('Anbieter-Seitenstruktur unbekannt: window.__DATA__ fehlt')
            return json.JSONDecoder().raw_decode(text[match.end():])[0]
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def local_url(path):
    url = urljoin(BASE, path)
    if urlsplit(url).netloc != urlsplit(BASE).netloc:
        raise ValueError(f'Unerwarteter Kataloghost: {url}')
    return url


def discover(lang, seasons=None):
    prefix = '/en' if lang == 'en' else ''
    home = local_url(prefix + '/seasons/south-park')
    root = fetch(home)
    pages = {1: home}
    for node in walk(root):
        if isinstance(node, dict) and node.get('seasonNumber') and node.get('url'):
            path = node['url']
            if '/seasons/' in path:
                pages[int(node['seasonNumber'])] = local_url(path)
    if seasons and not seasons <= pages.keys():
        raise ValueError(f'{lang}: Staffeln fehlen im Katalog: {sorted(seasons - pages.keys())}')
    records = {}
    for season, page in sorted(pages.items()):
        if seasons and season not in seasons:
            continue
        queue, visited = [page], set()
        while queue:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            data = root if url == home else fetch(url)
            for node in walk(data):
                if not isinstance(node, dict):
                    continue
                path = node.get('url')
                if not isinstance(path, str):
                    continue
                if re.search(r'/api/context/[^/]+/episode/\d+/\d+', path):
                    next_url = local_url(path)
                    if next_url not in visited:
                        queue.append(next_url)
                if not re.match(r'^/(?:en/)?(?:folgen|episodes)/', path):
                    continue
                if (path.startswith('/en/')) != (lang == 'en'):
                    continue
                # Only episode cards, never navigation links or clips.
                if node.get('entityType', node.get('itemType')) != 'episode':
                    continue
                ident = node.get('id') or node.get('meta', {}).get('itemMgid', '').rsplit(':', 1)[-1]
                if not ident:
                    raise ValueError(f'Folgen-ID fehlt: {path}')
                records[ident] = {'id': ident, 'language': lang, 'season': season,
                                  'url': local_url(path)}
        count = sum(r['season'] == season for r in records.values())
        if not count:
            print(f'WARNUNG: {lang}: Staffel {season} enthält keine gelisteten Folgen.', file=sys.stderr)
        print(f'{lang}: Staffel {season}: {count} Folgen', file=sys.stderr)
    if not records:
        raise ValueError(f'{lang}: keine Folgen gefunden; Anbieterstruktur prüfen')
    return list(records.values())


def season_set(value):
    result = set()
    try:
        for part in value.split(','):
            ends = [int(n) for n in part.split('-')]
            if len(ends) not in (1, 2) or min(ends) < 1 or ends[-1] < ends[0]:
                raise ValueError()
            result.update(range(ends[0], ends[-1] + 1))
    except ValueError:
        raise argparse.ArgumentTypeError('Staffeln als 1,3,5-8 angeben')
    return result


def atomic_json(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def prepare_paths(output, work):
    output, work = output.resolve(), work.resolve()
    if output == work or output in work.parents or work in output.parents:
        raise ValueError('DOWNLOAD_DIR und WORK_DIR müssen getrennt und außerhalb voneinander liegen')
    output.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    if output.stat().st_dev != work.stat().st_dev:
        raise ValueError('DOWNLOAD_DIR und WORK_DIR müssen für atomare Veröffentlichung auf demselben Dateisystem liegen')
    return output, work


def episode_dir(root, record):
    # IDs come from the provider, but must never become arbitrary filesystem paths.
    if not re.fullmatch(r'[A-Za-z0-9_-]+', record['id']):
        raise ValueError('Ungültige Folgen-ID')
    if record['language'] not in ('de', 'en', 'dual') or int(record['season']) < 1:
        raise ValueError('Ungültige Sprache/Staffel')
    return root / record['language'] / f'Staffel {record["season"]:02}' / record['id']


def check_media(path, min_audio=1):
    info = probe(path)
    streams = info.get('streams', [])
    if not any(s['codec_type'] == 'video' for s in streams):
        raise ValueError(f'Videospur fehlt: {path}')
    if sum(s['codec_type'] == 'audio' for s in streams) < min_audio:
        raise ValueError(f'Tonspur fehlt: {path}')
    if float(info.get('format', {}).get('duration', 0)) <= 0:
        raise ValueError(f'Ungültige Laufzeit: {path}')
    return info


def mark_complete(stage, record, min_audio=1):
    candidates = list(stage.glob('*.mkv'))
    if len(candidates) != 1 or candidates[0].name.endswith('.partial.mkv'):
        raise ValueError(f'Keine eindeutige fertige MKV in {stage}')
    if any(p.name.endswith(('.part', '.ytdl', '.tmp')) or '.part-Frag' in p.name
           for p in stage.iterdir()):
        raise ValueError(f'Unvollständige Downloadreste in {stage}')
    check_media(candidates[0], min_audio)
    atomic_json(stage / 'completed.json', {**record, 'filename': candidates[0].name})


def is_complete(folder, record):
    marker = folder / 'completed.json'
    if not marker.is_file():
        return False
    data = json.loads(marker.read_text())
    filename = data.get('filename', '')
    return (data.get('id') == record['id'] and data.get('language') == record['language']
            and Path(filename).name == filename and filename.endswith('.mkv')
            and (folder / filename).is_file() and (folder / filename).stat().st_size > 0)


def publish(stage, dest, record):
    if not is_complete(stage, record):
        raise ValueError(f'Folge ist nicht fertig verarbeitet: {stage}')
    if dest.exists():
        raise FileExistsError(f'Ziel existiert bereits: {dest}')
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Deliberately no shutil.move: EXDEV must fail rather than expose a partial copy.
    stage.rename(dest)
    print(f'Fertig veröffentlicht: {dest}')


def download(record, output, work, max_height=None):
    from yt_dlp import YoutubeDL
    dest = episode_dir(output, record)
    if is_complete(dest, record):
        print(f'Bereits fertig: {dest}')
        return
    if dest.exists():
        raise FileExistsError(f'Ziel ohne gültigen Abschlussnachweis: {dest}')
    folder = episode_dir(work / 'episodes', record)
    folder.mkdir(parents=True, exist_ok=True)
    if is_complete(folder, record):
        publish(folder, dest, record)
        return
    video = f'bv[height<={max_height}]' if max_height else 'bv'
    combined = f'b[height<={max_height}]' if max_height else 'b'
    language = record['language']
    opts = {
        'outtmpl': str(folder / 'South Park - S%(season_number)02dE%(episode_number)02d [%(id)s].%(ext)s'),
        'format': f'{video}+ba[language^={language}]/{combined}[language^={language}]',
        'merge_output_format': 'mkv',
        'writesubtitles': True, 'subtitleslangs': ['de.*', 'en.*'],
        'writeinfojson': True, 'clean_infojson': True,
        'retries': 5, 'fragment_retries': 5, 'skip_unavailable_fragments': False,
        'concurrent_fragment_downloads': 4,
        'geo_bypass': False, 'cachedir': False, 'socket_timeout': 45,
        'noprogress': True,
        'postprocessors': [{'key': 'FFmpegVideoRemuxer', 'preferedformat': 'mkv'},
                           {'key': 'FFmpegEmbedSubtitle', 'already_have_subtitle': True}],
    }
    with YoutubeDL(opts) as ydl:
        if ydl.download([record['url']]):
            raise RuntimeError('yt-dlp meldet einen fehlgeschlagenen Download')
    mark_complete(folder, record)
    publish(folder, dest, record)


def probe(path):
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))


def merge_dual(output, work):
    """Match content UUID, never episode number (DE and EN airing orders differ)."""
    failures = []
    sources = sorted((output / 'de').rglob('*.mkv'))
    if not sources:
        raise ValueError('Keine deutschen MKV-Dateien zum Zusammenführen gefunden')
    for de in sources:
        ident = re.search(r'\[([^\]]+)\]\.mkv$', de.name)
        if not ident:
            continue
        matches = list((output / 'en').rglob('*.mkv'))
        matches = [p for p in matches if p.name.endswith(f'[{ident[1]}].mkv')]
        if len(matches) != 1:
            failures.append({'file': str(de), 'error': 'Englische Fassung fehlt oder ist mehrdeutig'})
            continue
        en = matches[0]
        try:
            season = next(int(p.name.split()[-1]) for p in de.parents
                          if re.fullmatch(r'Staffel \d+', p.name))
            record = {'id': ident[1], 'language': 'dual', 'season': season}
            dest = episode_dir(output, record)
            if is_complete(dest, record):
                continue
            if dest.exists():
                raise FileExistsError(f'Ziel ohne gültigen Abschlussnachweis: {dest}')
            stage = episode_dir(work / 'merges', record)
            stage.mkdir(parents=True, exist_ok=True)
            if is_complete(stage, record):
                publish(stage, dest, record)
                continue
            dp, ep = check_media(de), check_media(en)
            durations = [float(p['format']['duration']) for p in (dp, ep)]
            if abs(durations[0] - durations[1]) > 0.25:
                raise ValueError(f'Laufzeiten abweichend: {durations}; getrennte Fassungen bleiben erhalten')
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(de), '-i', str(en),
                            '-map', '0:v:0', '-map', '0:a:0', '-map', '1:a:0',
                            '-map', '0:s?', '-map', '1:s?', '-c', 'copy',
                            '-metadata:s:a:0', 'language=deu', '-metadata:s:a:0', 'title=Deutsch',
                            '-metadata:s:a:1', 'language=eng', '-metadata:s:a:1', 'title=English',
                            '-disposition:a:0', 'default', '-disposition:a:1', '0',
                            str(stage / de.name)], check=True)
            mark_complete(stage, record, min_audio=2)
            publish(stage, dest, record)
        except Exception as exc:
            failures.append({'file': str(de), 'error': str(exc)})
    atomic_json(work / 'merge-errors.json', failures)
    return len(failures)


def main():
    parser = argparse.ArgumentParser(description='South Park: verfügbare vollständige Folgen herunterladen')
    parser.add_argument('action', choices=['catalog', 'download', 'merge'], nargs='?', default='download')
    parser.add_argument('--seasons', type=season_set, help='z.B. 1,3-5; Standard: alle')
    parser.add_argument('--languages', choices=['de', 'en', 'de,en'], default='de,en')
    parser.add_argument('--output', type=Path, default=Path(os.environ.get('DOWNLOAD_DIR', '/data/downloads')),
                        help='Ziel für fertige Folgen (Environment: DOWNLOAD_DIR)')
    parser.add_argument('--work-dir', type=Path, default=Path(os.environ.get('WORK_DIR', '/data/work')),
                        help='Arbeitsordner für Downloads/Zustand (Environment: WORK_DIR)')
    parser.add_argument('--limit', type=int, help='maximale Folgenzahl je Sprache für Probeläufe')
    parser.add_argument('--max-height', type=int, help='maximale Videoauflösung, z.B. 720')
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error('--limit muss positiv sein')
    if args.max_height is not None and args.max_height < 1:
        parser.error('--max-height muss positiv sein')
    args.output, args.work_dir = prepare_paths(args.output, args.work_dir)
    # A sibling lock also prevents concurrent writers using different WORK_DIR values.
    with (args.output.parent / f'.{args.output.name}.lock').open('w') as output_lock, \
            (args.work_dir / '.lock').open('w') as work_lock:
        try:
            fcntl.flock(output_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(work_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(2, 'Ein anderer Lauf verwendet dieses Downloadverzeichnis.\n')
        if args.action == 'merge':
            return bool(merge_dual(args.output, args.work_dir))
        records = []
        for lang in args.languages.split(','):
            records.extend(discover(lang, args.seasons))
        atomic_json(args.work_dir / 'catalog.json', records)
        if args.action == 'catalog':
            print(f'{len(records)} Sprachfassungen in {args.work_dir / "catalog.json"}')
            return 0
        failures, counts = [], {}
        for record in records:
            lang = record['language']
            if args.limit and counts.get(lang, 0) >= args.limit:
                continue
            counts[lang] = counts.get(lang, 0) + 1
            try:
                download(record, args.output, args.work_dir, args.max_height)
            except Exception as exc:
                print(f'FEHLER: {record["url"]}: {exc}', file=sys.stderr)
                failures.append({**record, 'error': str(exc)})
            time.sleep(1)
        atomic_json(args.work_dir / 'errors.json', failures)
        print(f'Fertig: {sum(counts.values())} versucht (inkl. bereits fertiger Folgen), {len(failures)} Fehler.')
        return bool(failures)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        print(f'FEHLER: {exc}', file=sys.stderr)
        sys.exit(1)
