"""Form tkinter luu video thanh MP4 hoac MP3 (YouTube, Facebook, Instagram, LinkedIn...).

Khong goi Gemini, khong tao Raw/Refine, khong sua build-audio2md.md.
"""
import os
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import save_mp4  # noqa: E402

TEMP_LIST = Path(tempfile.gettempdir()) / 'audio2md-save-media-links.txt'


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Save MP4 / MP3')
        self.geometry('700x640')
        self.fmt = tk.StringVar(value='mp4')
        self.folder = tk.StringVar(value=str(ROOT / 'data' / 'mp4'))
        self.quality = tk.StringVar(value='1080')
        self.custom = tk.BooleanVar(value=False)
        self.running = False
        self.build()
        self.fmt.trace_add('write', self.on_format)

    def build(self):
        pad = {'padx': 12, 'pady': 4}
        ttk.Label(self, text='Link (YouTube / Facebook / Instagram / LinkedIn...), '
                  'cach nhau bang dau phay, cham phay hoac xuong dong:').pack(anchor='w', **pad)
        self.links = scrolledtext.ScrolledText(self, height=6, wrap='word')
        self.links.pack(fill='x', **pad)

        row = ttk.Frame(self); row.pack(fill='x', **pad)
        ttk.Label(row, text='Dinh dang:').pack(side='left')
        ttk.Radiobutton(row, text='MP4 (video)', variable=self.fmt, value='mp4').pack(side='left', padx=8)
        ttk.Radiobutton(row, text='MP3 (am thanh)', variable=self.fmt, value='mp3').pack(side='left')

        row = ttk.Frame(self); row.pack(fill='x', **pad)
        ttk.Label(row, text='Thu muc luu:').pack(side='left')
        ttk.Entry(row, textvariable=self.folder).pack(side='left', fill='x', expand=True, padx=8)
        ttk.Button(row, text='Browse...', command=self.browse).pack(side='left')

        row = ttk.Frame(self); row.pack(fill='x', **pad)
        ttk.Label(row, text='Chat luong MP4 toi da:').pack(side='left')
        self.quality_box = ttk.Combobox(row, textvariable=self.quality, values=('1080', '720'),
                                        state='readonly', width=6)
        self.quality_box.pack(side='left', padx=8)
        ttk.Label(row, text='p').pack(side='left')

        ttk.Checkbutton(self, text='Nhap ten rieng cho tung file (mac dinh: ten theo tieu de)',
                        variable=self.custom).pack(anchor='w', **pad)

        row = ttk.Frame(self); row.pack(fill='x', **pad)
        self.start_btn = ttk.Button(row, text='Bat dau', command=self.start)
        self.start_btn.pack(side='left')
        ttk.Button(row, text='Thoat', command=self.destroy).pack(side='left', padx=8)

        self.log_box = scrolledtext.ScrolledText(self, height=16, state='disabled')
        self.log_box.pack(fill='both', expand=True, **pad)

    # --- giao dien -------------------------------------------------------
    def on_format(self, *_):
        mp3 = self.fmt.get() == 'mp3'
        self.quality_box.configure(state='disabled' if mp3 else 'readonly')
        current = Path(self.folder.get())
        # Chi tu doi khi dang o thu muc mac dinh, khong ghi de thu muc nguoi dung chon.
        if current in (ROOT / 'data' / 'mp4', ROOT / 'data' / 'mp3'):
            self.folder.set(str(ROOT / 'data' / self.fmt.get()))

    def browse(self):
        chosen = filedialog.askdirectory(title='Chon thu muc luu', initialdir=self.folder.get())
        if chosen:
            self.folder.set(str(Path(chosen)))

    def log(self, text):
        self.after(0, self._log, text)

    def _log(self, text):
        self.log_box.configure(state='normal')
        self.log_box.insert('end', text + '\n')
        self.log_box.see('end')
        self.log_box.configure(state='disabled')

    def ask_name(self, url):
        """Hoi ten file tu luong nen: chuyen sang luong giao dien va cho ket qua."""
        result, done = [], threading.Event()

        def show():
            result.append(simpledialog.askstring(
                'Ten file', f'Ten file (de trong = ten mac dinh):\n{url}', parent=self) or '')
            done.set()
        self.after(0, show)
        done.wait()
        return result[0]

    # --- chay ------------------------------------------------------------
    def start(self):
        if self.running:
            return
        text = self.links.get('1.0', 'end').strip()
        if not text:
            messagebox.showwarning('Thieu link', 'Hay nhap it nhat mot link.')
            return
        self.running = True
        self.start_btn.configure(state='disabled')
        threading.Thread(target=self.work, args=(text.replace('\n', ';'),), daemon=True).start()

    def work(self, raw):
        try:
            self.process(raw)
        except Exception as error:
            self.log(f'[ERROR] {error}')
        finally:
            self.running = False
            self.after(0, lambda: self.start_btn.configure(state='normal'))

    def process(self, raw):
        fmt, quality = self.fmt.get(), self.quality.get()
        output_dir = Path(self.folder.get()).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        self.log('[INFO] Dang kiem tra link (link kenh YouTube se mo menu chon o cua so cmd)...')
        TEMP_LIST.unlink(missing_ok=True)
        code = subprocess.call([sys.executable, str(HERE / 'chon_video_kenh.py'), raw, str(TEMP_LIST)])
        if code != 0:
            self.log('[X] Khong tao duoc danh sach link (hoac da quay lai).')
            return
        urls = save_mp4.read_urls(TEMP_LIST)
        self.log(f'[INFO] Luu {len(urls)} link {fmt.upper()} vao: {output_dir}')

        used, success = set(), 0
        for index, url in enumerate(urls, start=1):
            self.log(f'\n=== [{index}/{len(urls)}] {url} ===')
            name = None
            if self.custom.get():
                name = save_mp4.custom_name(url, used, output_dir, fmt, ask=self.ask_name)
            success += save_mp4.download_one(url, output_dir, quality, name, emit=self.log, fmt=fmt)
        self.log(f'\n[SUMMARY] Thanh cong: {success}/{len(urls)} | Thu muc: {output_dir}')


if __name__ == '__main__':
    App().mainloop()
