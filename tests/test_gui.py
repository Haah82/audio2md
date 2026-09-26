"""Regression checks for the active Menu 4 launcher wiring.

Audio2MD no longer ships a Tk GUI; its supported interface is ``audio2md.bat``.
Keeping the filename preserves normal unittest discovery while testing that UI.
"""
import unittest
from pathlib import Path


class MenuLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.batch = (Path(__file__).resolve().parents[1] / 'audio2md.bat').read_text(encoding='utf-8')

    def test_menu_four_routes_new_links_through_the_chooser(self):
        self.assertIn(':ADD_NEW_LINK', self.batch)
        self.assertIn('python src\\chon_video_kenh.py', self.batch)
        self.assertIn('"%TEMP_LIST%"', self.batch)

    def test_menu_advertises_multiple_link_separators(self):
        self.assertIn('nhieu link cach nhau bang , hoac ;', self.batch)


if __name__ == '__main__':
    unittest.main()
