"""Tk integration checks using a temporary workspace and mocked Gemini only."""
import os
import sys
import tempfile
import time
import tkinter.font as tkfont
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from gui_app import App
from pipeline import Pipeline
from test_audio2md import OLD, PATCH, RAW


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.input = self.root / 'data/input'
        self.output = self.root / 'data/output'
        self.input.mkdir(parents=True)
        self.output.mkdir(parents=True)
        (self.input / 'video.mp4').touch()
        (self.input / 'audio.mp3').touch()
        (self.output / 'old_raw.md').write_text(RAW, encoding='utf-8')
        (self.output / 'old_refine.md').write_text(OLD, encoding='utf-8')
        self.app = App(self.root)
        self.app.withdraw()
        self.errors = []
        self.app.report_callback_exception = lambda *args: self.errors.append(args)
        self.app.update()

    def tearDown(self):
        if self.app.worker and self.app.worker.is_alive():
            self.app.cancel.set()
            self.app.worker.join(timeout=3)
        for callback in self.app.tk.call('after', 'info'):
            self.app.after_cancel(callback)
        self.app.destroy()
        self.temp.cleanup()

    def test_mode_filters_and_clear_selection(self):
        self.assertEqual([Path(x).name for x in self.app.sources.values()], ['video.mp4'])
        self.app.select_all()
        self.assertEqual(len(self.app.selected), 1)
        self.app.mode.set('Audio')
        self.app.change_mode()
        self.assertEqual([Path(x).name for x in self.app.sources.values()], ['audio.mp3'])
        self.assertFalse(self.app.selected)

    def test_update_checkboxes_and_existing_links(self):
        self.app.task.set('Cập nhật kết quả cũ')
        self.app.change_mode()
        self.app.select_all()
        self.assertEqual(len(self.app.sources), 1)
        raw, refined = self.app.existing_paths(next(iter(self.app.sources.values())))
        self.assertTrue(raw.exists() and refined.exists())
        self.assertEqual(str(self.app.start_button['state']), 'normal')
        self.app.refine_update.set(False)
        self.app.refresh_start()
        self.assertEqual(str(self.app.start_button['state']), 'disabled')
        self.assertEqual(tkfont.nametofont('TkDefaultFont').actual()['size'], 10)

    def test_link_add_and_duplicate(self):
        self.app.mode.set('Link')
        self.app.change_mode()
        for _ in range(2):
            self.app.source.set('https://example.org/new')
            self.app.add_urls()
        self.assertEqual(len(self.app.sources), 1)

    def test_worker_end_to_end_no_network(self):
        self.app.task.set('Cập nhật kết quả cũ')
        self.app.change_mode()
        self.app.select_all()
        fake_pool = NS(usage=[], close=lambda: None, tong_ket=lambda: None)
        def factory(root, **kw):
            return Pipeline(root, pool_factory=lambda **opts: fake_pool, **kw)
        with patch('gui_app.Pipeline', side_effect=factory), patch('refine._call_json', return_value=PATCH):
            self.app.start()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                self.app.update()
                if self.app.results and self.app.worker and not self.app.worker.is_alive():
                    break
                time.sleep(0.01)
            self.app.finished()
        self.assertFalse(self.errors)
        self.assertEqual(next(iter(self.app.results.values())).status, 'success')
        self.assertIn('Góc nhìn chuyên sâu', (self.output / 'old_refine.md').read_text(encoding='utf-8'))
        self.assertEqual((self.output / 'old_raw.md').read_text(encoding='utf-8'), RAW)


if __name__ == '__main__':
    unittest.main()
