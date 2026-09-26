"""Unit tests for the current command-line Audio2MD implementation.

The earlier suite targeted a removed Tk/pipeline application. These tests cover
the active modules used by ``audio2md.bat`` without network or Gemini.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import chon_video_kenh as chooser
import main_audio2md as app


class UrlAndConfigTests(unittest.TestCase):
    def test_canonical_youtube_variants_match(self):
        expected = 'youtube:abc123'
        for url in ('https://youtu.be/abc123?si=tracking', 'https://www.youtube.com/watch?v=abc123&utm_source=x', 'https://m.youtube.com/shorts/abc123'):
            self.assertEqual(app.canonical_url(url), expected)

    def test_canonical_facebook_removes_trackers(self):
        self.assertEqual(app.canonical_url('https://www.facebook.com/reel/123?fbclid=abc&utm_source=x'), 'https://facebook.com/reel/123')

    def test_save_flags_are_opt_in(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(app.env_yes('SAVE_MP4', 'save-mp4'))
        with patch.dict(os.environ, {'SAVE_MP4': 'yes'}, clear=True):
            self.assertTrue(app.env_yes('SAVE_MP4', 'save-mp4'))
        with patch.dict(os.environ, {'SAVE_MP4': 'Y'}, clear=True):
            self.assertFalse(app.env_yes('SAVE_MP4', 'save-mp4'))

    def test_facebook_uses_one_client_youtube_has_fallbacks(self):
        self.assertEqual(app.danh_sach_client('https://www.facebook.com/reel/123'), ('default',))
        self.assertEqual(app.danh_sach_client('https://youtu.be/abc'), app.YOUTUBE_CLIENT_FALLBACKS)

    def test_youtube_client_options_only_apply_to_youtube_clients(self):
        self.assertNotIn('extractor_args', app.opts_theo_client({}, 'default'))
        self.assertEqual(app.opts_theo_client({}, 'android')['extractor_args'], {'youtube': {'player_client': ['android']}})

    def test_mp4_selector_allows_portrait_at_the_selected_quality(self):
        selector = app.mp4_format('1080')
        self.assertIn('height<=1080', selector)
        self.assertIn('width<=1080', selector)

    def test_menu_four_mp4_title_template_is_limited_before_download(self):
        self.assertEqual(app.mp4_output_template(), '%(title).150B.%(ext)s')


class InputAndMarkdownTests(unittest.TestCase):
    def test_subtitle_cleaner_removes_timing_and_repeated_overlap(self):
        with tempfile.TemporaryDirectory() as folder:
            subtitle = Path(folder) / 'sample.vtt'
            subtitle.write_text('WEBVTT\n\n00:00.000 --> 00:02.000\nHello.\n\n00:01.000 --> 00:03.000\nHello.\nWorld!\n', encoding='utf-8')
            self.assertEqual(app.clean_subtitle(subtitle), 'Hello.\n\nWorld!')

    def test_update_table_updates_existing_and_adds_new_row(self):
        with tempfile.TemporaryDirectory() as folder:
            input_dir = Path(folder) / 'data' / 'input'
            input_dir.mkdir(parents=True)
            table = input_dir / 'build-audio2md.md'
            table.write_text('| STT | Link | Tên file - tiêu đề | Thời gian | Raw | Refine | Status |\n|---|---|---|---|---|---|---|\n| 1 | https://youtu.be/known | Old | old | | | Pending |\n', encoding='utf-8')
            with patch.object(app, 'INPUT_DIR', str(input_dir)):
                app.update_md_table('https://www.youtube.com/watch?v=known', 'Known|title', 'known_raw', 'known_refine')
                app.update_md_table('https://www.facebook.com/reel/new', 'New title', 'new_raw', None)
            result = table.read_text(encoding='utf-8')
            self.assertIn('Known-title', result)
            self.assertIn('[[known_refine]]', result)
            self.assertIn('| 2 | https://www.facebook.com/reel/new | New title |', result)
            self.assertIn('[[new_raw]]', result)
            self.assertIn('Raw only', result)


class MenuFourTests(unittest.TestCase):
    def test_multiple_links_preserve_order_and_deduplicate(self):
        urls = chooser.tach_link('https://www.facebook.com/reel/1?fbclid=a, https://www.facebook.com/reel/1; https://www.facebook.com/share/r/2/')
        self.assertEqual(urls, ['https://www.facebook.com/reel/1?fbclid=a', 'https://www.facebook.com/share/r/2/'])

    def test_facebook_is_not_channel_and_youtube_channel_is(self):
        self.assertFalse(chooser.la_link_kenh('https://www.facebook.com/share/v/1abc/'))
        self.assertTrue(chooser.la_link_kenh('https://www.youtube.com/@example/videos'))
        self.assertFalse(chooser.la_link_kenh('https://www.youtube.com/watch?v=abc&list=xyz'))

    def test_selection_supports_single_list_and_range(self):
        self.assertEqual(chooser.phan_tich_lua_chon('1, 3-5; 8', 8), [1, 3, 4, 5, 8])
        self.assertIsNone(chooser.phan_tich_lua_chon('abc', 8))


if __name__ == '__main__':
    unittest.main()
