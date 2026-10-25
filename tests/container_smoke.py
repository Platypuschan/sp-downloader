"""Offline smoke test inside the actual published image, using real FFmpeg media."""
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, '/app')
import downloader as d

output, work = d.prepare_paths(Path(os.environ['DOWNLOAD_DIR']), Path(os.environ['WORK_DIR']))
filename = 'South Park - S01E01 [smoke].mkv'
for lang in ('de', 'en'):
    record = {'id': 'smoke', 'season': 1, 'language': lang}
    stage = d.episode_dir(work / 'episodes', record)
    stage.mkdir(parents=True)
    subprocess.run([
        'ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i', 'color=s=160x90:d=1',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1',
        '-c:v', 'mpeg4', '-c:a', 'aac', '-shortest', str(stage / filename)], check=True)
    dest = d.episode_dir(output, record)
    assert not dest.exists(), 'Unfertige Folge im Downloadordner'
    d.mark_complete(stage, record)
    d.publish(stage, dest, record)
    assert d.is_complete(dest, record)
    assert not stage.exists()

assert d.merge_dual(output, work) == 0
dual = d.episode_dir(output, {'id': 'smoke', 'season': 1, 'language': 'dual'})
info = d.check_media(dual / filename, min_audio=2)
audio = [s for s in info['streams'] if s['codec_type'] == 'audio']
assert [s.get('tags', {}).get('language') for s in audio] == ['deu', 'eng']
assert not list(output.rglob('*.part'))
assert not list(output.rglob('*.partial.mkv'))
assert len(list(output.rglob('completed.json'))) == 3
print('Container-Smoke-Test erfolgreich: atomare DE/EN-Veröffentlichung und Zweiton-MKV.')
