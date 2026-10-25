import tempfile
import errno
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import downloader as d


def media(duration='100', audio=1):
    return {'format': {'duration': duration},
            'streams': [{'codec_type': 'video'}] + [{'codec_type': 'audio'}] * audio}


class DownloaderTests(unittest.TestCase):
    def test_pagination_filters_clips_and_other_language(self):
        def card(ident, path):
            return {'id': ident, 'entityType': 'episode', 'url': path}
        api = '/api/context/season/episode/2/10'
        root = {'items': [card('one', '/folgen/one/first'),
                          card('wrong', '/en/episodes/wrong/english'),
                          {'id': 'clip', 'entityType': 'video', 'url': '/videoclip/x/y'}],
                'next': {'url': api}}
        second = {'items': [card('two', '/folgen/two/second')], 'next': {'url': api}}
        with patch.object(d, 'fetch', side_effect=[root, second]) as fetch:
            result = d.discover('de', {1})
        self.assertEqual([v['id'] for v in result], ['one', 'two'])
        self.assertEqual(fetch.call_count, 2)

    def test_missing_season_and_empty_catalog_fail(self):
        with patch.object(d, 'fetch', return_value={}):
            with self.assertRaises(ValueError):
                d.discover('de', {99})
            with self.assertRaises(ValueError):
                d.discover('en', {1})

    def test_season_input_and_catalog_host(self):
        self.assertEqual(d.season_set('1,3-5'), {1, 3, 4, 5})
        for value in ['0', '4-2', '1-2-3', 'abc']:
            with self.assertRaises(Exception):
                d.season_set(value)
        with self.assertRaises(ValueError):
            d.local_url('https://example.com/api/context/x/episode/2/10')

    def test_merge_uses_id_despite_different_episode_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for lang, number in [('de', 2), ('en', 3)]:
                folder = root / lang / 'Staffel 01'
                folder.mkdir(parents=True)
                (folder / f'South Park - S01E{number:02} [uuid].mkv').touch()
            def mux(args, **kwargs):
                self.assertFalse((root / 'dual').exists())
                Path(args[-1]).write_bytes(b'complete')
            with patch.object(d, 'probe', return_value=media(audio=2)), \
                    patch.object(d.subprocess, 'run', side_effect=mux) as run:
                self.assertEqual(d.merge_dual(root, root / 'work'), 0)
                self.assertTrue(any('S01E03' in arg for arg in run.call_args.args[0]))
            self.assertTrue((root / 'dual/Staffel 01/uuid/South Park - S01E02 [uuid].mkv').exists())

    def test_merge_refuses_different_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for lang in ['de', 'en']:
                folder = root / lang / 'Staffel 01'
                folder.mkdir(parents=True)
                (folder / 'South Park - S01E01 [uuid].mkv').touch()
            with patch.object(d, 'probe', side_effect=[
                    media('100'), media('105')]), \
                    patch.object(d.subprocess, 'run') as run:
                self.assertEqual(d.merge_dual(root, root / 'work'), 1)
                run.assert_not_called()


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output, self.work = d.prepare_paths(self.root / 'finished', self.root / 'work')
        self.record = {'id': 'uuid', 'language': 'de', 'season': 1, 'url': 'https://example.invalid/episode'}
        self.factory = MagicMock()
        self.ydl = self.factory.return_value.__enter__.return_value
        self.ydl.download.return_value = 0
        patcher = patch.dict(sys.modules, {'yt_dlp': SimpleNamespace(YoutubeDL=self.factory)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def stage(self):
        return d.episode_dir(self.work / 'episodes', self.record)

    def successful_download(self, urls):
        self.assertEqual(list(self.output.rglob('*')), [])
        stage = self.stage()
        (stage / 'episode.mkv').write_bytes(b'finished media')
        (stage / 'episode.en.vtt').write_text('WEBVTT')
        (stage / 'episode.info.json').write_text('{}')
        return 0

    def test_episode_and_sidecars_appear_together_after_processing(self):
        self.ydl.download.side_effect = self.successful_download
        with patch.object(d, 'probe', return_value=media()):
            d.download(self.record, self.output, self.work)
        dest = d.episode_dir(self.output, self.record)
        self.assertEqual({p.name for p in dest.iterdir()},
                         {'episode.mkv', 'episode.en.vtt', 'episode.info.json', 'completed.json'})
        self.assertFalse(self.stage().exists())
        self.assertTrue(d.is_complete(dest, self.record))
        self.factory.reset_mock()
        d.download(self.record, self.output, self.work)
        self.factory.assert_not_called()

    def test_failed_download_stays_outside_destination(self):
        def interrupted(urls):
            (self.stage() / 'episode.mp4.part').write_bytes(b'partial')
            raise RuntimeError('interrupted')
        self.ydl.download.side_effect = interrupted
        with self.assertRaises(RuntimeError):
            d.download(self.record, self.output, self.work)
        self.assertEqual(list(self.output.rglob('*')), [])
        self.assertTrue((self.stage() / 'episode.mp4.part').exists())

    def test_failed_postprocessing_never_publishes(self):
        self.ydl.download.side_effect = self.successful_download
        with patch.object(d, 'probe', return_value=media(audio=0)):
            with self.assertRaises(ValueError):
                d.download(self.record, self.output, self.work)
        self.assertEqual(list(self.output.rglob('*')), [])
        self.assertFalse((self.stage() / 'completed.json').exists())

    def test_unfinished_fragment_rejects_publication(self):
        stage = self.stage()
        stage.mkdir(parents=True)
        (stage / 'episode.mkv').write_bytes(b'media')
        (stage / 'episode.mp4.part-Frag1').write_bytes(b'incomplete')
        with self.assertRaises(ValueError):
            d.mark_complete(stage, self.record)

    def test_publish_failure_can_retry_without_redownloading(self):
        self.ydl.download.side_effect = self.successful_download
        with patch.object(d, 'probe', return_value=media()), \
                patch.object(Path, 'rename', side_effect=OSError(errno.EXDEV, 'different filesystem')):
            with self.assertRaises(OSError):
                d.download(self.record, self.output, self.work)
        self.assertTrue(d.is_complete(self.stage(), self.record))
        self.assertEqual(list(self.output.rglob('*.mkv')), [])
        self.factory.reset_mock()
        d.download(self.record, self.output, self.work)
        self.factory.assert_not_called()
        self.assertTrue(d.is_complete(d.episode_dir(self.output, self.record), self.record))

    def test_environment_configures_output_and_state_is_outside_it(self):
        with patch.dict(os.environ, {'DOWNLOAD_DIR': str(self.output), 'WORK_DIR': str(self.work)}), \
                patch.object(sys, 'argv', ['downloader.py', 'catalog']), \
                patch.object(d, 'discover', return_value=[self.record]):
            self.assertEqual(d.main(), 0)
        self.assertTrue((self.work / 'catalog.json').exists())
        self.assertEqual(list(self.output.rglob('*')), [])

    def test_conflicting_and_cross_filesystem_directories_rejected(self):
        for output, work in [(self.output, self.output),
                             (self.output, self.output / 'work'),
                             (self.work / 'output', self.work)]:
            with self.assertRaises(ValueError):
                d.prepare_paths(output, work)
        real_stat = Path.stat
        def different_device(path, *args, **kwargs):
            result = real_stat(path, *args, **kwargs)
            if path == self.work:
                fields = list(result)
                fields[2] += 1  # st_dev
                return os.stat_result(fields)
            return result
        with patch.object(Path, 'stat', different_device):
            with self.assertRaisesRegex(ValueError, 'Dateisystem'):
                d.prepare_paths(self.output, self.work)

    def test_path_traversal_id_rejected(self):
        with self.assertRaises(ValueError):
            d.episode_dir(self.output, {**self.record, 'id': '../outside'})

    def test_concurrent_output_or_work_writer_is_rejected(self):
        locks = [self.output.parent / f'.{self.output.name}.lock', self.work / '.lock']
        for path in locks:
            with self.subTest(lock=path), path.open('w') as held, \
                    patch.dict(os.environ, {'DOWNLOAD_DIR': str(self.output), 'WORK_DIR': str(self.work)}), \
                    patch.object(sys, 'argv', ['downloader.py', 'catalog']), \
                    patch.object(d, 'discover') as discover:
                d.fcntl.flock(held, d.fcntl.LOCK_EX | d.fcntl.LOCK_NB)
                with self.assertRaises(SystemExit) as exc:
                    d.main()
                self.assertEqual(exc.exception.code, 2)
                discover.assert_not_called()

    def test_failed_merge_never_publishes_partial_mkv(self):
        for lang in ('de', 'en'):
            folder = d.episode_dir(self.output, {**self.record, 'language': lang})
            folder.mkdir(parents=True)
            (folder / 'South Park - S01E01 [uuid].mkv').write_bytes(b'source')
        def failed_mux(args, **kwargs):
            Path(args[-1]).write_bytes(b'incomplete merge')
            raise RuntimeError('FFmpeg failed')
        with patch.object(d, 'probe', return_value=media()), \
                patch.object(d.subprocess, 'run', side_effect=failed_mux):
            self.assertEqual(d.merge_dual(self.output, self.work), 1)
        self.assertFalse((self.output / 'dual').exists())
        self.assertTrue(list((self.work / 'merges').rglob('*.mkv')))
        errors = json.loads((self.work / 'merge-errors.json').read_text())
        self.assertIn('FFmpeg failed', errors[0]['error'])


if __name__ == '__main__':
    unittest.main()
