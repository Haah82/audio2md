import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import save_mp4


class Downloader:
    seen_options = []

    def __init__(self, options):
        self.options = options
        self.seen_options.append(options)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def download(self, urls):
        self.urls = urls
        return 0


class SaveMp4Tests(unittest.TestCase):
    def test_custom_name_is_windows_safe_and_removes_extension(self):
        self.assertEqual(save_mp4.safe_custom_name(' lesson: one.mp4 '), 'lesson_ one')
        with self.assertRaises(ValueError):
            save_mp4.safe_custom_name(' .mp4 ')

    def test_options_limit_height_and_produce_mp4(self):
        opts = save_mp4.options(Path('output'), '720', 'lesson')
        self.assertEqual(opts['format'], save_mp4.pipeline.mp4_format('720'))
        self.assertIn('height<=720', opts['format'])
        self.assertIn('width<=720', opts['format'])
        self.assertEqual(opts['merge_output_format'], 'mp4')
        self.assertTrue(opts['outtmpl'].endswith('lesson.%(ext)s'))
        self.assertTrue(opts['nooverwrites'])
        self.assertTrue(opts['windowsfilenames'])
        self.assertNotIn('trim_file_name', opts)

    def test_default_template_bounds_long_reel_titles_before_download(self):
        opts = save_mp4.options(Path('output'), '1080')
        self.assertIn('%(title).120B', opts['outtmpl'])

    def test_facebook_download_uses_one_default_client(self):
        Downloader.seen_options = []
        with tempfile.TemporaryDirectory() as folder, patch('save_mp4.yt_dlp.YoutubeDL', Downloader):
            self.assertTrue(save_mp4.download_one('https://www.facebook.com/reel/123', Path(folder), '1080', emit=lambda _: None))
        self.assertEqual(len(Downloader.seen_options), 1)
        self.assertNotIn('extractor_args', Downloader.seen_options[0])

    def test_batch_exposes_the_two_folder_and_name_modes(self):
        batch = (Path(__file__).resolve().parents[1] / 'save-mp4.bat').read_text(encoding='utf-8')
        self.assertIn('[1] Mac dinh:', batch)
        self.assertIn('[2] Chon thu muc khac...', batch)
        self.assertIn('--custom-names', batch)


if __name__ == '__main__':
    unittest.main()
