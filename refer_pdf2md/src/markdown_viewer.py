# -*- coding: utf-8 -*-
"""Cửa sổ Xem Markdown bằng Tkinter cơ bản, theo plan mục "Xem Markdown".

Mỗi lần mở tạo một tk.Toplevel riêng, resize và đóng độc lập với cửa sổ chính.
Chế độ Nguồn cho sửa trực tiếp; chế độ Xem trước chỉ đọc, dựng lại khi chuyển
chế độ hoặc nhấn F5. File nguồn là dữ liệu duy nhất được ghi, nên không cần
chuyển ngược rich text thành Markdown.

Preview không tải URL, không chạy JavaScript, không gọi API và không tự mở nội
dung nhúng. Mermaid, LaTeX, HTML nhúng và plugin Obsidian chỉ hiện dạng khối mã
kèm ghi chú chưa hỗ trợ.
"""
import hashlib
import os
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

SRC_DIR = Path(__file__).resolve().parent
ROOT = SRC_DIR.parent
HISTORY_DIR = ROOT / 'history'

sys.path.insert(0, str(SRC_DIR))
import history_log  # noqa: E402

GHI_CHU_CHUA_HO_TRO = 'Chưa hỗ trợ trong Xem trước'
NGON_NGU_CHUA_DUNG = {'mermaid', 'dataview', 'dataviewjs', 'js', 'javascript',
                      'html', 'latex', 'tex', 'query'}
ANH_TK_DOC_DUOC = {'.png', '.gif', '.ppm', '.pgm'}
GIOI_HAN_ANH = 4 * 1024 * 1024


def hoi_lua_chon(cha, tieu_de, thong_diep, cac_nut, mac_dinh):
    """Hộp thoại nhiều nút. cac_nut là danh sách (ma, nhan). Đóng = mac_dinh."""
    hop = tk.Toplevel(cha)
    hop.title(tieu_de)
    hop.transient(cha)
    hop.resizable(False, False)
    ket = {'gia_tri': mac_dinh}

    khung = ttk.Frame(hop, padding=18)
    khung.pack(fill='both', expand=True)
    ttk.Label(khung, text=thong_diep, wraplength=560, justify='left').pack(anchor='w')
    hang = ttk.Frame(khung)
    hang.pack(anchor='e', pady=(16, 0))

    def chon(gt):
        ket['gia_tri'] = gt
        hop.destroy()

    nut_mac_dinh = None
    for ma, nhan in cac_nut:
        nut = ttk.Button(hang, text=nhan, command=lambda g=ma: chon(g))
        nut.pack(side='left', padx=4)
        if ma == mac_dinh:
            nut_mac_dinh = nut
    hop.protocol('WM_DELETE_WINDOW', lambda: chon(mac_dinh))
    hop.bind('<Escape>', lambda e: chon(mac_dinh))
    if nut_mac_dinh is not None:
        nut_mac_dinh.focus_set()
    hop.update_idletasks()
    x = cha.winfo_rootx() + (cha.winfo_width() - hop.winfo_width()) // 2
    y = cha.winfo_rooty() + (cha.winfo_height() - hop.winfo_height()) // 3
    hop.geometry(f'+{max(x, 0)}+{max(y, 0)}')
    hop.grab_set()
    hop.wait_window()
    return ket['gia_tri']


class CuaSoMarkdown(tk.Toplevel):
    def __init__(self, cha, duong_dan=None, ho_chu='Segoe UI', co_chu=11):
        super().__init__(cha)
        self.cha_chinh = cha
        self.duong_dan = Path(duong_dan) if duong_dan else None
        self.ho_chu = ho_chu
        self.co_chu = co_chu
        self.dau_van = None
        self.che_do = 'nguon'
        self.anh_giu = []

        px = getattr(cha, 'px', lambda n: n)
        self.geometry(f'{px(900)}x{px(680)}')
        self.minsize(px(560), px(400))
        self._dung_giao_dien()
        if self.duong_dan:
            self._nap_tu_dia()
        else:
            self._cap_nhat_tieu_de()
        self.protocol('WM_DELETE_WINDOW', self._dong_cua_so)
        self.bind('<F5>', lambda e: self._ve_xem_truoc())
        self.bind('<Control-s>', lambda e: self._luu())

    # ------------------------------------------------------------ giao diện
    def _dung_giao_dien(self):
        thanh = ttk.Frame(self, padding=(10, 8, 10, 4))
        thanh.pack(fill='x')
        self.lbl_tep = ttk.Label(thanh, text='Tệp: (chưa có)')
        self.lbl_tep.pack(side='left')
        for nhan, lenh in (('Lưu thành', self._luu_thanh), ('Lưu', self._luu),
                           ('Mở', self._mo), ('Mới', self._moi)):
            ttk.Button(thanh, text=nhan, command=lenh).pack(side='right', padx=3)

        hang_che_do = ttk.Frame(self, padding=(10, 0))
        hang_che_do.pack(fill='x')
        self.bien_che_do = tk.StringVar(value='nguon')
        ttk.Radiobutton(hang_che_do, text='Nguồn', value='nguon',
                        variable=self.bien_che_do, command=self._doi_che_do).pack(side='left')
        ttk.Radiobutton(hang_che_do, text='Xem trước', value='xem_truoc',
                        variable=self.bien_che_do, command=self._doi_che_do).pack(side='left',
                                                                                 padx=(10, 0))

        self.khung_noi_dung = ttk.Frame(self, padding=(10, 6, 10, 0))
        self.khung_noi_dung.pack(fill='both', expand=True)

        self.txt_nguon = tk.Text(self.khung_noi_dung, wrap='word', undo=True,
                                 font=(self.ho_chu, self.co_chu), relief='solid',
                                 borderwidth=1, padx=8, pady=6)
        thanh_nguon = ttk.Scrollbar(self.khung_noi_dung, orient='vertical',
                                    command=self.txt_nguon.yview)
        self.txt_nguon.configure(yscrollcommand=thanh_nguon.set)
        self.thanh_nguon = thanh_nguon

        self.txt_xem = tk.Text(self.khung_noi_dung, wrap='word', state='disabled',
                               font=(self.ho_chu, self.co_chu), relief='solid',
                               borderwidth=1, padx=10, pady=8, cursor='arrow')
        thanh_xem = ttk.Scrollbar(self.khung_noi_dung, orient='vertical',
                                  command=self.txt_xem.yview)
        self.txt_xem.configure(yscrollcommand=thanh_xem.set)
        self.thanh_xem = thanh_xem

        self._dat_the()
        self.txt_nguon.pack(side='left', fill='both', expand=True)
        self.thanh_nguon.pack(side='left', fill='y')
        self.txt_nguon.bind('<<Modified>>', self._danh_dau_thay_doi)

        chan = ttk.Frame(self, padding=(10, 6, 10, 8))
        chan.pack(fill='x')
        self.lbl_trang_thai = ttk.Label(chan, text='Trạng thái: Sẵn sàng')
        self.lbl_trang_thai.pack(side='left')

    def _dat_the(self):
        t = self.txt_xem
        co = self.co_chu
        for muc, thua in ((1, 9), (2, 6), (3, 4), (4, 2), (5, 1), (6, 0)):
            t.tag_configure(f'h{muc}', font=(self.ho_chu, co + thua, 'bold'),
                            spacing1=10, spacing3=6)
        t.tag_configure('dam', font=(self.ho_chu, co, 'bold'))
        t.tag_configure('nghieng', font=(self.ho_chu, co, 'italic'))
        t.tag_configure('gach', overstrike=True)
        t.tag_configure('danh_dau', background='#fff3a3')
        t.tag_configure('ma', font=('Consolas', co), background='#f0f0f0')
        t.tag_configure('khoi_ma', font=('Consolas', co), background='#f5f5f5',
                        lmargin1=20, lmargin2=20, spacing1=2, spacing3=2)
        t.tag_configure('bang', font=('Consolas', co), lmargin1=16, lmargin2=16)
        t.tag_configure('trich', lmargin1=20, lmargin2=20, foreground='#555555')
        t.tag_configure('callout', lmargin1=20, lmargin2=20, background='#eef4fb')
        t.tag_configure('lien_ket', foreground='#0a58ca', underline=True)
        t.tag_configure('chua_ho_tro', foreground='#a05000', font=(self.ho_chu, co, 'italic'))
        t.tag_configure('danh_sach', lmargin1=20, lmargin2=36)
        t.tag_configure('duong_ke', foreground='#999999')

    # ------------------------------------------------------------ trạng thái
    def _cap_nhat_tieu_de(self):
        ten = str(self.duong_dan) if self.duong_dan else '(chưa lưu)'
        self.title(f'Xem Markdown - {ten}')
        self.lbl_tep.configure(text=f'Tệp: {ten}')

    def _dat_trang_thai(self, chu):
        self.lbl_trang_thai.configure(text=f'Trạng thái: {chu}')

    def _danh_dau_thay_doi(self, _e=None):
        if self.txt_nguon.edit_modified():
            self._dat_trang_thai('Đã thay đổi')

    @property
    def co_thay_doi(self):
        return bool(self.txt_nguon.edit_modified())

    def _dat_sach(self):
        self.txt_nguon.edit_modified(False)
        self._dat_trang_thai('Đã lưu' if self.duong_dan else 'Sẵn sàng')

    # ------------------------------------------------------------ đọc và ghi
    @staticmethod
    def _chup_dau_van(duong_dan):
        try:
            tt = os.stat(duong_dan)
            bam = hashlib.sha256(Path(duong_dan).read_bytes()).hexdigest()
            return (tt.st_mtime_ns, tt.st_size, bam)
        except OSError:
            return None

    def _nap_tu_dia(self):
        try:
            du_lieu = self.duong_dan.read_bytes()
        except OSError as loi:
            self._dat_trang_thai(f'Không thể đọc: {loi}')
            self.duong_dan = None
            self._cap_nhat_tieu_de()
            return
        noi_dung = None
        for bang_ma in ('utf-8-sig', 'utf-8'):
            try:
                noi_dung = du_lieu.decode(bang_ma)
                break
            except UnicodeDecodeError:
                continue
        if noi_dung is None:
            # Không thay ký tự âm thầm và không cho ghi đè file chưa đọc được.
            self.txt_nguon.configure(state='disabled')
            self._dat_trang_thai('Không thể đọc: file không phải UTF-8')
            self._cap_nhat_tieu_de()
            return
        self.txt_nguon.configure(state='normal')
        self.txt_nguon.delete('1.0', 'end')
        self.txt_nguon.insert('1.0', noi_dung)
        self.dau_van = self._chup_dau_van(self.duong_dan)
        self._cap_nhat_tieu_de()
        self._dat_sach()

    def _ghi_ra_dia(self, dich):
        noi_dung = self.txt_nguon.get('1.0', 'end-1c')
        dich = Path(dich)
        dich.parent.mkdir(parents=True, exist_ok=True)
        tam = dich.with_name(dich.name + '.tmp')
        with open(tam, 'w', encoding='utf-8', newline='\n') as f:
            f.write(noi_dung)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tam, dich)
        self.duong_dan = dich
        self.dau_van = self._chup_dau_van(dich)
        self._cap_nhat_tieu_de()
        self._dat_sach()
        self._ghi_history(dich)

    def _ghi_history(self, dich):
        try:
            history_log.ghi(HISTORY_DIR, {
                'chuc_nang': 'Xem Markdown',
                'tac_vu': 'Lưu file Markdown',
                'nguon': str(dich),
                'dich': str(dich),
                'lua_chon': 'Lưu',
                'trang_thai': 'Đã lưu',
                'loi': None,
            })
        except Exception as loi:  # noqa: BLE001
            # File đã lưu vẫn giữ; chỉ báo tách bạch phần lịch sử.
            self._dat_trang_thai(f'Đã lưu, nhưng không ghi được lịch sử ({loi})')

    def _luu(self):
        if self.duong_dan is None:
            return self._luu_thanh()
        if self.dau_van is not None:
            hien_tai = self._chup_dau_van(self.duong_dan)
            if hien_tai is not None and hien_tai != self.dau_van:
                chon = hoi_lua_chon(
                    self, 'File đã thay đổi ngoài ứng dụng',
                    f'{self.duong_dan}\n\nFile trên đĩa đã khác so với lúc mở.',
                    [('nap_lai', 'Nạp lại'), ('luu_thanh', 'Lưu thành'),
                     ('ghi_de', 'Ghi đè'), ('huy', 'Hủy')], 'huy')
                if chon == 'huy':
                    return None
                if chon == 'nap_lai':
                    return self._nap_tu_dia()
                if chon == 'luu_thanh':
                    return self._luu_thanh()
        try:
            self._ghi_ra_dia(self.duong_dan)
        except OSError as loi:
            self._dat_trang_thai(f'Lưu thất bại: {loi}')
        return None

    def _luu_thanh(self):
        dich = filedialog.asksaveasfilename(
            parent=self, title='Lưu thành', defaultextension='.md',
            filetypes=[('Markdown', '*.md'), ('Tất cả file', '*.*')],
            confirmoverwrite=False)
        if not dich:
            return None
        dich = Path(dich)
        if dich.suffix.lower() != '.md':
            dich = dich.with_name(dich.name + '.md')
        if dich.exists():
            chon = hoi_lua_chon(
                self, 'File kết quả đã tồn tại',
                f'Đích: {dich}\n\nThay thế: ghi đè file hiện có.\n'
                'Bỏ qua: giữ file hiện có, không ghi.',
                [('thay_the', 'Thay thế (Replace)'), ('bo_qua', 'Bỏ qua'),
                 ('huy', 'Hủy')], 'huy')
            if chon != 'thay_the':
                return None
        try:
            self._ghi_ra_dia(dich)
        except OSError as loi:
            self._dat_trang_thai(f'Lưu thất bại: {loi}')
        return None

    def _xu_ly_thay_doi_cho(self):
        """Trả về True nếu được phép đi tiếp."""
        if not self.co_thay_doi:
            return True
        chon = hoi_lua_chon(self, 'Chưa lưu thay đổi',
                            'Nội dung đang có thay đổi chưa lưu.',
                            [('luu', 'Lưu'), ('khong_luu', 'Không lưu'),
                             ('huy', 'Hủy')], 'huy')
        if chon == 'huy':
            return False
        if chon == 'luu':
            self._luu()
            return not self.co_thay_doi
        return True

    def _moi(self):
        if not self._xu_ly_thay_doi_cho():
            return
        CuaSoMarkdown(self.cha_chinh, None, self.ho_chu, self.co_chu)

    def _mo(self):
        if not self._xu_ly_thay_doi_cho():
            return
        chon = filedialog.askopenfilename(
            parent=self, title='Mở file Markdown',
            filetypes=[('Markdown', '*.md'), ('Tất cả file', '*.*')])
        if chon:
            self.txt_nguon.configure(state='normal')
            self.duong_dan = Path(chon)
            self._nap_tu_dia()
            if self.che_do == 'xem_truoc':
                self._ve_xem_truoc()

    def _dong_cua_so(self):
        if self._xu_ly_thay_doi_cho():
            self.destroy()

    # ------------------------------------------------------------ chế độ
    def _doi_che_do(self):
        moi = self.bien_che_do.get()
        if moi == self.che_do:
            return
        self.che_do = moi
        if moi == 'xem_truoc':
            self.txt_nguon.pack_forget()
            self.thanh_nguon.pack_forget()
            self.txt_xem.pack(side='left', fill='both', expand=True)
            self.thanh_xem.pack(side='left', fill='y')
            self._ve_xem_truoc()
        else:
            self.txt_xem.pack_forget()
            self.thanh_xem.pack_forget()
            self.txt_nguon.pack(side='left', fill='both', expand=True)
            self.thanh_nguon.pack(side='left', fill='y')

    # ------------------------------------------------------------ dựng preview
    def _ve_xem_truoc(self):
        if self.che_do != 'xem_truoc':
            return
        noi_dung = self.txt_nguon.get('1.0', 'end-1c')
        t = self.txt_xem
        t.configure(state='normal')
        t.delete('1.0', 'end')
        self.anh_giu = []
        try:
            self._dung_khoi(t, noi_dung)
        except Exception as loi:  # noqa: BLE001
            t.insert('end', f'Không dựng được Xem trước: {loi}\n', ('chua_ho_tro',))
        t.configure(state='disabled')

    def _dung_khoi(self, t, noi_dung):
        dong = noi_dung.split('\n')
        i = 0
        while i < len(dong):
            d = dong[i]

            # khối mã có rào
            khop_rao = re.match(r'^\s*```+\s*([A-Za-z0-9_+-]*)\s*$', d)
            if khop_rao:
                ngon_ngu = (khop_rao.group(1) or '').lower()
                than, i = self._gom_den_rao(dong, i + 1)
                if ngon_ngu in NGON_NGU_CHUA_DUNG:
                    t.insert('end', f'[{GHI_CHU_CHUA_HO_TRO}: {ngon_ngu}]\n', ('chua_ho_tro',))
                t.insert('end', than + '\n', ('khoi_ma',))
                continue

            # khối công thức
            if d.strip().startswith('$$'):
                than, i = self._gom_den_dau(dong, i, '$$')
                t.insert('end', f'[{GHI_CHU_CHUA_HO_TRO}: công thức LaTeX]\n', ('chua_ho_tro',))
                t.insert('end', than + '\n', ('khoi_ma',))
                continue

            # HTML nhúng
            if re.match(r'^\s*<(div|script|style|iframe|table|img|br|hr|span)\b', d, re.I):
                t.insert('end', f'[{GHI_CHU_CHUA_HO_TRO}: HTML nhúng]\n', ('chua_ho_tro',))
                t.insert('end', d + '\n', ('khoi_ma',))
                i += 1
                continue

            # đường kẻ ngang
            if re.match(r'^\s*([-*_])\s*(\1\s*){2,}$', d):
                t.insert('end', '─' * 40 + '\n', ('duong_ke',))
                i += 1
                continue

            # tiêu đề
            khop_h = re.match(r'^(#{1,6})\s+(.*)$', d)
            if khop_h:
                muc = len(khop_h.group(1))
                self._chen_inline(t, khop_h.group(2), (f'h{muc}',))
                t.insert('end', '\n')
                i += 1
                continue

            # bảng pipe
            if '|' in d and i + 1 < len(dong) and re.match(r'^\s*\|?[\s:|-]+\|[\s:|-]*$', dong[i + 1]):
                i = self._dung_bang(t, dong, i)
                continue

            # trích dẫn và callout
            if re.match(r'^\s*>', d):
                i = self._dung_trich(t, dong, i)
                continue

            # danh sách
            khop_ds = re.match(r'^(\s*)([-*+]|\d+[.)])\s+(.*)$', d)
            if khop_ds:
                thut = len(khop_ds.group(1))
                than = khop_ds.group(3)
                dau = '•' if khop_ds.group(2) in '-*+' else khop_ds.group(2)
                khop_task = re.match(r'^\[([ xX])\]\s+(.*)$', than)
                if khop_task:
                    dau = '[x]' if khop_task.group(1).lower() == 'x' else '[ ]'
                    than = khop_task.group(2)
                t.insert('end', ' ' * thut + f'{dau} ', ('danh_sach',))
                self._chen_inline(t, than, ('danh_sach',))
                t.insert('end', '\n')
                i += 1
                continue

            # đoạn rỗng
            if not d.strip():
                t.insert('end', '\n')
                i += 1
                continue

            self._chen_inline(t, d, ())
            t.insert('end', '\n')
            i += 1

    @staticmethod
    def _gom_den_rao(dong, i):
        gom = []
        while i < len(dong) and not re.match(r'^\s*```+\s*$', dong[i]):
            gom.append(dong[i])
            i += 1
        return '\n'.join(gom), i + 1

    @staticmethod
    def _gom_den_dau(dong, i, dau):
        # Khối mở và đóng ngay trên một dòng, ví dụ "$$ E = mc^2 $$". Không xét
        # trường hợp này thì vòng lặp đi tìm dấu đóng ở các dòng sau và nuốt hết
        # phần còn lại của tài liệu.
        con_lai = dong[i].strip()
        if con_lai.startswith(dau) and dau in con_lai[len(dau):]:
            return dong[i], i + 1
        gom = [dong[i]]
        i += 1
        while i < len(dong) and dau not in dong[i]:
            gom.append(dong[i])
            i += 1
        if i < len(dong):
            gom.append(dong[i])
        return '\n'.join(gom), i + 1

    def _dung_bang(self, t, dong, i):
        hang = []
        while i < len(dong) and '|' in dong[i]:
            hang.append(dong[i])
            i += 1
        o = []
        for h in hang:
            if re.match(r'^\s*\|?[\s:|-]+\|[\s:|-]*$', h):
                continue
            o.append([c.strip() for c in h.strip().strip('|').split('|')])
        if not o:
            return i
        so_cot = max(len(r) for r in o)
        rong = [0] * so_cot
        for r in o:
            for k, c in enumerate(r):
                rong[k] = max(rong[k], len(c))
        for r in o:
            dong_chu = '  '.join((r[k] if k < len(r) else '').ljust(rong[k])
                                 for k in range(so_cot))
            t.insert('end', dong_chu.rstrip() + '\n', ('bang',))
        t.insert('end', '\n')
        return i

    def _dung_trich(self, t, dong, i):
        gom = []
        while i < len(dong) and re.match(r'^\s*>', dong[i]):
            gom.append(re.sub(r'^\s*>\s?', '', dong[i]))
            i += 1
        the = 'trich'
        if gom and re.match(r'^\s*\[!\w+\]', gom[0]):
            the = 'callout'
            khop = re.match(r'^\s*\[!(\w+)\]\s*(.*)$', gom[0])
            gom[0] = f'{khop.group(1).upper()}: {khop.group(2)}'.strip()
        for g in gom:
            self._chen_inline(t, g, (the,))
            t.insert('end', '\n', (the,))
        t.insert('end', '\n')
        return i

    MAU_INLINE = re.compile(
        r'(?P<ma>`[^`]+`)'
        r'|(?P<anh>!\[[^\]]*\]\([^)]+\))'
        r'|(?P<lien_ket>\[[^\]]+\]\([^)]+\))'
        r'|(?P<wiki>\[\[[^\]]+\]\])'
        r'|(?P<dam>\*\*[^*]+\*\*)'
        r'|(?P<gach>~~[^~]+~~)'
        r'|(?P<danh_dau>==[^=]+==)'
        r'|(?P<nghieng>(?<!\*)\*[^*\n]+\*(?!\*))'
        r'|(?P<toan>\$[^$\n]+\$)'
    )

    def _chen_inline(self, t, chu, the_goc):
        vi_tri = 0
        for khop in self.MAU_INLINE.finditer(chu):
            if khop.start() > vi_tri:
                t.insert('end', chu[vi_tri:khop.start()], the_goc)
            loai = khop.lastgroup
            gt = khop.group()
            if loai == 'ma':
                t.insert('end', gt[1:-1], the_goc + ('ma',))
            elif loai == 'anh':
                self._chen_anh(t, gt, the_goc)
            elif loai == 'lien_ket':
                nhan = re.match(r'\[([^\]]+)\]', gt).group(1)
                t.insert('end', nhan, the_goc + ('lien_ket',))
            elif loai == 'wiki':
                t.insert('end', gt[2:-2], the_goc + ('lien_ket',))
            elif loai == 'dam':
                t.insert('end', gt[2:-2], the_goc + ('dam',))
            elif loai == 'gach':
                t.insert('end', gt[2:-2], the_goc + ('gach',))
            elif loai == 'danh_dau':
                t.insert('end', gt[2:-2], the_goc + ('danh_dau',))
            elif loai == 'nghieng':
                t.insert('end', gt[1:-1], the_goc + ('nghieng',))
            elif loai == 'toan':
                t.insert('end', gt, the_goc + ('chua_ho_tro',))
            vi_tri = khop.end()
        if vi_tri < len(chu):
            t.insert('end', chu[vi_tri:], the_goc)

    def _chen_anh(self, t, the_anh, the_goc):
        """Chỉ nạp ảnh cục bộ Tk đọc được và không quá lớn; còn lại hiện đường dẫn."""
        khop = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', the_anh)
        if not khop:
            t.insert('end', the_anh, the_goc)
            return
        mo_ta, nguon = khop.group(1), khop.group(2).strip()
        if re.match(r'^[a-zA-Z]+://', nguon):
            t.insert('end', f'[ảnh ngoài, không tải: {nguon}]', the_goc + ('chua_ho_tro',))
            return
        goc = self.duong_dan.parent if self.duong_dan else Path.cwd()
        duong_dan = (goc / nguon).resolve()
        if duong_dan.suffix.lower() not in ANH_TK_DOC_DUOC or not duong_dan.exists():
            t.insert('end', f'[ảnh: {nguon}]', the_goc + ('chua_ho_tro',))
            return
        try:
            if duong_dan.stat().st_size > GIOI_HAN_ANH:
                kb = duong_dan.stat().st_size // 1024
                t.insert('end', f'[ảnh lớn {kb} KB, không nạp: {nguon}]',
                         the_goc + ('chua_ho_tro',))
                return
            anh = tk.PhotoImage(master=self, file=str(duong_dan))
        except (OSError, tk.TclError):
            t.insert('end', f'[ảnh không đọc được: {nguon}]', the_goc + ('chua_ho_tro',))
            return
        self.anh_giu.append(anh)
        t.image_create('end', image=anh)
        if mo_ta:
            t.insert('end', f' {mo_ta}', the_goc + ('nghieng',))


def mo_cua_so(cha, duong_dan=None, ho_chu='Segoe UI', co_chu=11):
    """Mở một cửa sổ mới, kể cả khi file đó đang mở ở cửa sổ khác."""
    return CuaSoMarkdown(cha, duong_dan, ho_chu, co_chu)
