# -*- coding: utf-8 -*-
"""Giao diện Tkinter cho PDF2MD.

Bố cục theo ba ảnh thiết kế trong assets/images: hàng Chức năng và Tác vụ, hàng
Mô tả, hàng Nguồn kèm Duyệt (Browse) / Về input / Quét lại, dòng Lọc và ô Tìm
tên, cây Explorer ba cột có ô chọn, hàng nút chạy, ô Nhật ký và thanh trạng thái.

Hai chức năng đang có:
    Xuất Markdown   chạy các script 2 đến 6, giữ hậu tố _native/_scan/_refined
    Tóm tắt file md gọi src/summary_md.py, đích data/summary, hậu tố _summary

Đích luôn giữ cấu trúc thư mục con tương đối với gốc nguồn. Nguồn nằm ngoài thư
mục mặc định thì thêm tên thư mục gốc đó làm một cấp thư mục trong đích, để các
đợt từ nhiều nguồn ngoài không đổ lẫn vào nhau.
"""
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import tkinter.font as tkfont
import uuid
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

SRC_DIR = Path(__file__).resolve().parent
ROOT = SRC_DIR.parent
INPUT_DIR = ROOT / 'data' / 'input'
OUTPUT_DIR = ROOT / 'data' / 'output'
SUMMARY_DIR = ROOT / 'data' / 'summary'
HISTORY_DIR = ROOT / 'history'

sys.path.insert(0, str(SRC_DIR))
import history_log  # noqa: E402
import khoa_phien  # noqa: E402
import markdown_viewer  # noqa: E402

CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

VIEN_O = '#5a6570'
DAU_TICK = '#1a6fd4'

# Cỡ chữ cơ bản của toàn giao diện. Tăng số này nếu muốn chữ to hơn nữa; chiều
# cao dòng cây và ô chọn đều tính lại theo cỡ chữ.
CO_CHU = 11
HO_CHU = 'Segoe UI'

MO_TA_LOCAL = 'Xử lý trên máy, không dùng API'
MO_TA_API = 'Gửi Gemini API, cần GEMINI_API_KEY trong .env'
MO_TA_SUMMARY = 'Gửi Gemini Flash, cần GEMINI_API_KEY và GEMINI_MODEL dòng Flash'

TAC_VU = [
    {'key': 'native', 'nhan': 'PDF gốc (Native PDF) | Local', 'mo_ta': MO_TA_LOCAL,
     'ext': ('.pdf',), 'suffix': '_native', 'script': '2_pdf_native.py'},
    {'key': 'scan', 'nhan': 'PDF ảnh/scan (Scanned PDF) | Gemini', 'mo_ta': MO_TA_API,
     'ext': ('.pdf',), 'suffix': '_scan', 'script': '3_pdf_scan.py'},
    {'key': 'word', 'nhan': 'Microsoft Word (.docx) | Local', 'mo_ta': MO_TA_LOCAL,
     'ext': ('.docx',), 'suffix': '', 'script': '4_word.py'},
    {'key': 'excel', 'nhan': 'Microsoft Excel (.xlsx) | Local', 'mo_ta': MO_TA_LOCAL,
     'ext': ('.xlsx',), 'suffix': '', 'script': '5_excel.py'},
    {'key': 'refine', 'nhan': 'Hiệu đính (Refine) | Gemini API', 'mo_ta': MO_TA_API,
     'ext': None, 'suffix': '_refined', 'script': '6_gemini_refine.py'},
]

REFINE_SUB = [
    {'nhan': 'PDF Scan (.pdf)', 'ext': ('.pdf',), 'mode': '1'},
    {'nhan': 'Bảng Excel (.xlsx)', 'ext': ('.xlsx',), 'mode': '2'},
    {'nhan': 'Bảng trong Word (.docx)', 'ext': ('.docx',), 'mode': '3'},
]

TAC_VU_SUMMARY = {
    'key': 'summary', 'nhan': 'Tóm tắt file md | Gemini Flash', 'mo_ta': MO_TA_SUMMARY,
    'ext': ('.md',), 'suffix': '_summary', 'script': 'summary_md.py',
}

CHUC_NANG = [
    {'key': 'markdown', 'nhan': 'Xuất Markdown', 'goc_mac_dinh': INPUT_DIR,
     'goc_output': OUTPUT_DIR, 'nhan_ve': 'Về input', 'nhan_chay': 'Bắt đầu',
     'nhan_mo': 'Mở output'},
    {'key': 'summary', 'nhan': 'Tóm tắt file md', 'goc_mac_dinh': OUTPUT_DIR,
     'goc_output': SUMMARY_DIR, 'nhan_ve': 'Về output', 'nhan_chay': 'Tóm tắt',
     'nhan_mo': 'Mở summary'},
]

NGON_NGU = [('song-ngu', 'Song ngữ Việt-Anh'), ('viet', 'Tiếng Việt'), ('anh', 'Tiếng Anh')]
LOAI_VAN_BAN = [('bao-cao', 'Báo cáo / thông thường'), ('ky-thuat', 'Kỹ thuật')]

MA_BO_QUA = 3
# Script con da tao duoc file NHUNG con thieu trang (vd cum PDF scan hong).
# Phai bao rieng, khong duoc gop vao 'Thanh cong' nhu truoc.
MA_THIEU = 4


def bat_nhan_biet_dpi():
    """Bật nhận biết DPI trước khi tạo Tk.

    Phải gọi trước khi có root Tk đầu tiên. Gọi sau thì Windows đã tắt chế độ
    phóng to bù, còn Tk vẫn tính theo 96 dpi, nên chữ hiện rất nhỏ trên màn hình
    đặt 125% hoặc 150%.
    """
    try:
        from ctypes import windll
    except ImportError:
        return
    try:
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        try:
            windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


bat_nhan_biet_dpi()


def _ve_dau_tick(anh, canh):
    """Vẽ dấu tick bằng hai đoạn thẳng, độ dày theo kích thước ô."""
    day = max(2, canh // 7)
    diem = ((canh * 0.26, canh * 0.50), (canh * 0.44, canh * 0.68), (canh * 0.76, canh * 0.28))
    for (x1, y1), (x2, y2) in ((diem[0], diem[1]), (diem[1], diem[2])):
        buoc = max(1, int(abs(x2 - x1)))
        for i in range(buoc + 1):
            t = i / buoc
            x = int(x1 + (x2 - x1) * t)
            y = int(y1 + (y2 - y1) * t)
            anh.put(DAU_TICK, to=(x, y, min(x + day, canh), min(y + day, canh)))


def tao_anh_o_chon(trang_thai, canh=16):
    """Vẽ ô chọn bằng PhotoImage thuần stdlib, kích thước theo cỡ chữ."""
    canh = max(14, int(canh))
    anh = tk.PhotoImage(width=canh, height=canh)
    trai, phai = 1, canh - 1
    day = max(1, canh // 14)
    anh.put('#ffffff', to=(trai, trai, phai, phai))
    anh.put(VIEN_O, to=(trai, trai, phai, trai + day))
    anh.put(VIEN_O, to=(trai, phai - day, phai, phai))
    anh.put(VIEN_O, to=(trai, trai, trai + day, phai))
    anh.put(VIEN_O, to=(phai - day, trai, phai, phai))
    if trang_thai == 'chon':
        _ve_dau_tick(anh, canh)
    elif trang_thai == 'mot_phan':
        le = max(3, canh // 4)
        nua = max(1, canh // 10)
        anh.put(DAU_TICK, to=(le, canh // 2 - nua, canh - le, canh // 2 + nua + 1))
    return anh


class HopThoaiTrung(tk.Toplevel):
    """Hỏi Thay thế / Bỏ qua / Hủy lượt chạy khi file kết quả đã tồn tại."""

    def __init__(self, cha, nguon, dich):
        super().__init__(cha)
        self.ket_qua = 'huy'
        self.title('File kết quả đã tồn tại')
        self.transient(cha)
        self.resizable(False, False)
        rong_chu = getattr(cha, 'px', lambda n: n)(620)

        khung = ttk.Frame(self, padding=18)
        khung.pack(fill='both', expand=True)
        ttk.Label(khung, text=f'Nguồn:   {nguon}', wraplength=rong_chu).pack(anchor='w')
        ttk.Label(khung, text=f'Kết quả: {dich}', wraplength=rong_chu).pack(anchor='w', pady=(2, 0))
        ttk.Label(khung, text='Thay thế: chuyển đổi lại và thay file kết quả khi thành công.',
                  wraplength=rong_chu).pack(anchor='w', pady=(14, 0))
        ttk.Label(khung, text='Bỏ qua: giữ file hiện có, không chuyển đổi.',
                  wraplength=rong_chu).pack(anchor='w')

        hang = ttk.Frame(khung)
        hang.pack(anchor='e', pady=(18, 0))
        ttk.Button(hang, text='Thay thế (Replace)',
                   command=lambda: self._chon('thay_the')).pack(side='left', padx=4)
        nut_bo_qua = ttk.Button(hang, text='Bỏ qua', command=lambda: self._chon('bo_qua'))
        nut_bo_qua.pack(side='left', padx=4)
        ttk.Button(hang, text='Hủy lượt chạy',
                   command=lambda: self._chon('huy')).pack(side='left', padx=4)

        self.protocol('WM_DELETE_WINDOW', lambda: self._chon('huy'))
        self.bind('<Escape>', lambda e: self._chon('huy'))
        nut_bo_qua.focus_set()
        self.update_idletasks()
        self._canh_giua(cha)
        self.grab_set()
        self.wait_window(self)

    def _canh_giua(self, cha):
        x = cha.winfo_rootx() + (cha.winfo_width() - self.winfo_width()) // 2
        y = cha.winfo_rooty() + (cha.winfo_height() - self.winfo_height()) // 3
        self.geometry(f'+{max(x, 0)}+{max(y, 0)}')

    def _chon(self, gia_tri):
        self.ket_qua = gia_tri
        self.destroy()


class UngDung(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('PDF2MD | Chuyển tài liệu sang Markdown')

        self.goc_nguon = INPUT_DIR
        self.dang_chay = False
        self.dung_sau = False
        self.tat_ca_file = []
        self.da_chon = {}
        self.item_map = {}
        self.path_to_iid = {}
        self.q = queue.Queue()
        self._ma_tim = None

        self._chuan_bi_kieu()
        self._dat_kich_thuoc_cua_so()
        self.anh_o = {ten: tao_anh_o_chon(ten, self.canh_o_chon)
                      for ten in ('trong', 'chon', 'mot_phan')}
        self._dung_giao_dien()

        for thu_muc in (INPUT_DIR, OUTPUT_DIR, SUMMARY_DIR):
            thu_muc.mkdir(parents=True, exist_ok=True)
        self._doi_chuc_nang()
        self.after(100, self._poll)

    # ---------- kiểu hiển thị ----------
    def _chuan_bi_kieu(self):
        """Đặt tỷ lệ theo DPI và dùng Segoe UI đúng cỡ cho giao diện Windows."""
        try:
            self.tk.call('tk', 'scaling', self.winfo_fpixels('1i') / 72.0)
        except tk.TclError:
            pass
        # Tỷ lệ so với 96 dpi. Mọi kích thước tính bằng điểm ảnh (bề rộng cột,
        # cỡ cửa sổ, wraplength) phải nhân tỷ lệ này thì ở 125% và 150% mới đủ chỗ.
        self.ty_le = max(1.0, self.winfo_fpixels('1i') / 96.0)
        for ten in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont',
                    'TkTooltipFont', 'TkIconFont', 'TkSmallCaptionFont'):
            try:
                tkfont.nametofont(ten).configure(family=HO_CHU, size=CO_CHU)
            except tk.TclError:
                pass
        self.font_chu = tkfont.nametofont('TkDefaultFont')
        self.option_add('*TCombobox*Listbox.font', (HO_CHU, CO_CHU))

        self.kieu = ttk.Style()
        if 'vista' in self.kieu.theme_names():
            self.kieu.theme_use('vista')
        cao_dong = self.font_chu.metrics('linespace')
        self.canh_o_chon = max(16, cao_dong)
        self.kieu.configure('Treeview', font=self.font_chu, rowheight=cao_dong + 12)
        self.kieu.configure('Treeview.Heading', font=(HO_CHU, CO_CHU, 'bold'))
        self.kieu.configure('TButton', font=self.font_chu, padding=(10, 5))
        self.kieu.configure('TLabel', font=self.font_chu)
        self.kieu.configure('TCheckbutton', font=self.font_chu)
        self.kieu.configure('TRadiobutton', font=self.font_chu)
        self.kieu.configure('TEntry', padding=3)
        self.kieu.configure('ThanhTrangThai.TLabel', foreground='#444444')

    def px(self, so_diem):
        """Đổi kích thước thiết kế ở 96 dpi sang điểm ảnh thật của màn hình."""
        return int(so_diem * self.ty_le)

    def _dat_kich_thuoc_cua_so(self):
        """Cỡ cửa sổ theo tỷ lệ DPI, vẫn phải vừa màn hình như 1366x768."""
        rong = min(self.px(1150), self.winfo_screenwidth() - self.px(40))
        cao = min(self.px(830), self.winfo_screenheight() - self.px(60))
        self.geometry(f'{rong}x{cao}')
        self.minsize(min(self.px(860), rong), min(self.px(560), cao))

    # ---------- dựng giao diện ----------
    def _dung_giao_dien(self):
        tren = ttk.Frame(self, padding=(12, 10, 12, 4))
        tren.pack(fill='x')
        tren.columnconfigure(1, weight=1)

        ttk.Label(tren, text='Chức năng:', width=11).grid(row=0, column=0, sticky='w', pady=4)
        self.combo_chuc_nang = ttk.Combobox(tren, state='readonly', width=24,
                                            values=[c['nhan'] for c in CHUC_NANG])
        self.combo_chuc_nang.current(0)
        self.combo_chuc_nang.grid(row=0, column=1, columnspan=2, sticky='w')
        self.combo_chuc_nang.bind('<<ComboboxSelected>>', lambda e: self._doi_chuc_nang())

        # Hàng tùy chọn đổi theo chức năng: Xuất Markdown dùng combo Tác vụ,
        # Tóm tắt dùng combo Ngôn ngữ và Loại văn bản.
        self.lbl_tuy_chon = ttk.Label(tren, text='Tác vụ:', width=11)
        self.lbl_tuy_chon.grid(row=1, column=0, sticky='w', pady=4)

        self.khung_markdown = ttk.Frame(tren)
        self.combo_tac_vu = ttk.Combobox(self.khung_markdown, state='readonly', width=36,
                                         values=[t['nhan'] for t in TAC_VU])
        self.combo_tac_vu.current(0)
        self.combo_tac_vu.pack(side='left')
        self.combo_tac_vu.bind('<<ComboboxSelected>>', lambda e: self._doi_tac_vu())
        ttk.Label(self.khung_markdown, text='Kiểu Refine:').pack(side='left', padx=(16, 6))
        self.combo_refine = ttk.Combobox(self.khung_markdown, state='disabled', width=22,
                                         values=[s['nhan'] for s in REFINE_SUB])
        self.combo_refine.current(0)
        self.combo_refine.pack(side='left')
        self.combo_refine.bind('<<ComboboxSelected>>', lambda e: self.quet_lai())

        self.khung_summary = ttk.Frame(tren)
        self.combo_ngon_ngu = ttk.Combobox(self.khung_summary, state='readonly', width=20,
                                           values=[n[1] for n in NGON_NGU])
        self.combo_ngon_ngu.current(0)
        self.combo_ngon_ngu.pack(side='left')
        ttk.Label(self.khung_summary, text='Loại văn bản:').pack(side='left', padx=(16, 6))
        self.combo_loai = ttk.Combobox(self.khung_summary, state='readonly', width=24,
                                       values=[l[1] for l in LOAI_VAN_BAN])
        self.combo_loai.current(0)
        self.combo_loai.pack(side='left')

        ttk.Label(tren, text='Mô tả:', width=11).grid(row=2, column=0, sticky='w', pady=4)
        self.lbl_mo_ta = ttk.Label(tren, text=MO_TA_LOCAL)
        self.lbl_mo_ta.grid(row=2, column=1, columnspan=2, sticky='w')

        ttk.Label(tren, text='Nguồn:', width=11).grid(row=3, column=0, sticky='w', pady=4)
        self.bien_nguon = tk.StringVar(value=str(self.goc_nguon))
        self.entry_nguon = ttk.Entry(tren, textvariable=self.bien_nguon, state='readonly')
        self.entry_nguon.grid(row=3, column=1, sticky='ew', padx=(0, 10))
        hang_nut = ttk.Frame(tren)
        hang_nut.grid(row=3, column=2, sticky='e')
        self.btn_duyet = ttk.Button(hang_nut, text='Duyệt (Browse)', command=self._mo_menu_duyet)
        self.btn_duyet.pack(side='left', padx=3)
        self.btn_ve_goc = ttk.Button(hang_nut, text='Về input', command=self._ve_goc_mac_dinh)
        self.btn_ve_goc.pack(side='left', padx=3)
        self.btn_quet = ttk.Button(hang_nut, text='Quét lại', command=self.quet_lai)
        self.btn_quet.pack(side='left', padx=3)

        hang_loc = ttk.Frame(tren)
        hang_loc.grid(row=4, column=1, columnspan=2, sticky='ew', pady=(4, 0))
        self.lbl_loc = ttk.Label(hang_loc, text='Lọc: *.pdf')
        self.lbl_loc.pack(side='left')
        self.bien_de_quy = tk.BooleanVar(value=True)
        self.chk_de_quy = ttk.Checkbutton(hang_loc, text='Bao gồm thư mục con',
                                          variable=self.bien_de_quy, command=self.quet_lai)
        self.chk_de_quy.pack(side='left', padx=(14, 0))
        self.btn_bo_chon = ttk.Button(hang_loc, text='Bỏ chọn',
                                      command=lambda: self._chon_toan_bo(False))
        self.btn_bo_chon.pack(side='right', padx=3)
        self.btn_chon_het = ttk.Button(hang_loc, text='Chọn tất cả',
                                       command=lambda: self._chon_toan_bo(True))
        self.btn_chon_het.pack(side='right', padx=3)
        self.bien_tim = tk.StringVar()
        self.entry_tim = ttk.Entry(hang_loc, textvariable=self.bien_tim, width=30)
        self.entry_tim.pack(side='right', padx=(0, 10))
        ttk.Label(hang_loc, text='Tìm tên:').pack(side='right', padx=(0, 6))
        self.bien_tim.trace_add('write', self._hen_tim)

        giua = ttk.Frame(self, padding=(12, 8, 12, 0))
        giua.pack(fill='both', expand=True)
        # selectmode='browse': dòng nhận được focus để bấm phím cách bật/tắt ô chọn.
        # Việc chọn nhiều file do các ô checkbox quyết định, không do vùng bôi đậm.
        self.tree = ttk.Treeview(giua, columns=('trang_thai', 'ket_qua'),
                                 show='tree headings', selectmode='browse')
        self.tree.heading('#0', text='Tên thư mục / file')
        self.tree.heading('trang_thai', text='Trạng thái')
        self.tree.heading('ket_qua', text='Kết quả')
        self.tree.column('#0', width=self.px(520), minwidth=self.px(240), stretch=True)
        self.tree.column('trang_thai', width=self.px(120), minwidth=self.px(90),
                         stretch=False, anchor='w')
        self.tree.column('ket_qua', width=self.px(330), minwidth=self.px(150),
                         stretch=True, anchor='w')
        thanh_doc = ttk.Scrollbar(giua, orient='vertical', command=self.tree.yview)
        thanh_ngang = ttk.Scrollbar(giua, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=thanh_doc.set, xscrollcommand=thanh_ngang.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        thanh_doc.grid(row=0, column=1, sticky='ns')
        thanh_ngang.grid(row=1, column=0, sticky='ew')
        giua.rowconfigure(0, weight=1)
        giua.columnconfigure(0, weight=1)
        self.tree.tag_configure('da_chon', background='#dce9f9')
        self.tree.bind('<Button-1>', self._nhan_chuot_cay)
        self.tree.bind('<space>', self._nhan_phim_cach)

        duoi = ttk.Frame(self, padding=(12, 6, 12, 0))
        duoi.pack(fill='x')
        self.lbl_dem = ttk.Label(duoi, text='Đã chọn 0 file')
        self.lbl_dem.pack(anchor='w')
        hang_chay = ttk.Frame(duoi)
        hang_chay.pack(anchor='w', pady=(6, 0))
        self.btn_bat_dau = ttk.Button(hang_chay, text='Bắt đầu', command=self._bat_dau)
        self.btn_bat_dau.pack(side='left', padx=(0, 6))
        self.btn_dung = ttk.Button(hang_chay, text='Dừng sau lượt hiện tại',
                                   command=self._yeu_cau_dung, state='disabled')
        self.btn_dung.pack(side='left', padx=6)
        self.btn_mo_output = ttk.Button(hang_chay, text='Mở output', command=self._mo_dich)
        self.btn_mo_output.pack(side='left', padx=6)
        self.btn_xem_md = ttk.Button(hang_chay, text='Xem Markdown',
                                     command=self._mo_xem_markdown, state='disabled')
        self.btn_xem_md.pack(side='left', padx=6)

        khung_log = ttk.Frame(self, padding=(12, 8, 12, 0))
        khung_log.pack(fill='both')
        ttk.Label(khung_log, text='Nhật ký:').pack(anchor='w')
        vung_log = ttk.Frame(khung_log)
        vung_log.pack(fill='both', expand=True)
        self.txt_log = tk.Text(vung_log, height=8, wrap='word', relief='solid',
                               borderwidth=1, font=self.font_chu, padx=6, pady=4)
        thanh_log = ttk.Scrollbar(vung_log, orient='vertical', command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=thanh_log.set, state='disabled')
        self.txt_log.pack(side='left', fill='both', expand=True)
        thanh_log.pack(side='left', fill='y')

        thanh = ttk.Frame(self, padding=(12, 6, 12, 8))
        thanh.pack(fill='x')
        self.lbl_dich = ttk.Label(thanh, text='', style='ThanhTrangThai.TLabel')
        self.lbl_dich.pack(side='left')
        self.lbl_lich_su = ttk.Label(thanh, text='', style='ThanhTrangThai.TLabel')
        self.lbl_lich_su.pack(side='right')
        self._cap_nhat_nhan_lich_su()

    def _cap_nhat_nhan_lich_su(self):
        ten = datetime.now().astimezone().strftime('%Y-%m') + '.log'
        self.lbl_lich_su.configure(text=f'Lịch sử: history\\{ten}')

    # ---------- chức năng và tác vụ ----------
    def chuc_nang_hien_tai(self):
        return CHUC_NANG[self.combo_chuc_nang.current()]

    def tac_vu_hien_tai(self):
        if self.chuc_nang_hien_tai()['key'] == 'summary':
            return TAC_VU_SUMMARY
        return TAC_VU[self.combo_tac_vu.current()]

    def phan_mo_rong(self):
        task = self.tac_vu_hien_tai()
        if task['key'] == 'refine':
            return REFINE_SUB[self.combo_refine.current()]['ext']
        return task['ext']

    def _doi_chuc_nang(self):
        cn = self.chuc_nang_hien_tai()
        la_summary = cn['key'] == 'summary'
        self.lbl_tuy_chon.configure(text='Ngôn ngữ:' if la_summary else 'Tác vụ:')
        if la_summary:
            self.khung_markdown.grid_remove()
            self.khung_summary.grid(row=1, column=1, columnspan=2, sticky='w')
        else:
            self.khung_summary.grid_remove()
            self.khung_markdown.grid(row=1, column=1, columnspan=2, sticky='w')
        self.btn_ve_goc.configure(text=cn['nhan_ve'])
        self.btn_bat_dau.configure(text=cn['nhan_chay'])
        self.btn_mo_output.configure(text=cn['nhan_mo'])
        self.lbl_dich.configure(text=f'Đích: {cn["goc_output"]}')
        self.goc_nguon = cn['goc_mac_dinh']
        self.bien_nguon.set(str(self.goc_nguon))
        self.da_chon.clear()
        self._doi_tac_vu()

    def _doi_tac_vu(self):
        task = self.tac_vu_hien_tai()
        self.lbl_mo_ta.configure(text=task['mo_ta'])
        if self.chuc_nang_hien_tai()['key'] == 'markdown':
            self.combo_refine.configure(
                state='readonly' if task['key'] == 'refine' else 'disabled')
        self.da_chon.clear()
        self.quet_lai()

    # ---------- đường dẫn đích ----------
    def _tien_to_nguon_ngoai(self):
        """Tên thư mục thêm vào đích khi nguồn nằm ngoài thư mục mặc định.

        Nguồn ngoài đổ thẳng vào gốc đích sẽ lẫn với kết quả của các đợt khác và
        dễ đụng tên, nên lấy tên thư mục gốc ngoài làm một cấp thư mục.
        """
        goc_mac_dinh = self.chuc_nang_hien_tai()['goc_mac_dinh']
        try:
            self.goc_nguon.resolve().relative_to(goc_mac_dinh.resolve())
            return None
        except (ValueError, OSError):
            pass
        ten = self.goc_nguon.name
        if not ten:
            ten = re.sub(r'[^0-9A-Za-zÀ-ỹ_.-]+', '-', str(self.goc_nguon)).strip('-')
        return ten or 'nguon-ngoai'

    def duong_dan_output(self, tep_nguon):
        """Đích giữ nguyên cấu trúc thư mục con tương đối với gốc nguồn."""
        goc_out = self.chuc_nang_hien_tai()['goc_output']
        tien_to = self._tien_to_nguon_ngoai()
        if tien_to:
            goc_out = goc_out / tien_to
        try:
            tuong_doi = tep_nguon.relative_to(self.goc_nguon)
        except ValueError:
            tuong_doi = Path(tep_nguon.name)
        ten = f"{tep_nguon.stem}{self.tac_vu_hien_tai()['suffix']}.md"
        return goc_out / tuong_doi.parent / ten

    def ten_hien_thi(self, dich):
        """Tên rút gọn tương đối với gốc đích để hiện ở cột Kết quả."""
        try:
            return str(dich.relative_to(self.chuc_nang_hien_tai()['goc_output']))
        except ValueError:
            return dich.name

    def _nam_trong_dich(self, dich):
        """Chặn trường hợp .. hoặc symlink đưa đích ra ngoài gốc đích."""
        try:
            dich.resolve().relative_to(self.chuc_nang_hien_tai()['goc_output'].resolve())
            return True
        except (ValueError, OSError):
            return False

    # ---------- nguồn ----------
    def _mo_menu_duyet(self):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label='Chọn file...', command=self._duyet_file)
        menu.add_command(label='Chọn thư mục...', command=self._duyet_thu_muc)
        try:
            menu.tk_popup(self.btn_duyet.winfo_rootx(),
                          self.btn_duyet.winfo_rooty() + self.btn_duyet.winfo_height())
        finally:
            menu.grab_release()

    def _duyet_thu_muc(self):
        d = filedialog.askdirectory(title='Chọn thư mục nguồn', initialdir=str(self.goc_nguon))
        if not d:
            return
        if not self._nguon_hop_le(Path(d)):
            return
        self._dat_goc_nguon(Path(d))
        self.da_chon.clear()
        self.quet_lai()

    def _duyet_file(self):
        exts = self.phan_mo_rong()
        loai = [('File hợp lệ', ' '.join(f'*{e}' for e in exts)), ('Tất cả file', '*.*')]
        fs = filedialog.askopenfilenames(title='Chọn file nguồn',
                                         initialdir=str(self.goc_nguon), filetypes=loai)
        if not fs:
            return
        paths = [Path(p) for p in fs]
        if not self._nguon_hop_le(paths[0].parent):
            return
        self._dat_goc_nguon(paths[0].parent)
        self.da_chon.clear()
        for p in paths:
            self.da_chon[str(p)] = True
        self.quet_lai()

    def _nguon_hop_le(self, goc):
        """Không cho chọn nguồn nằm trong history hoặc chính thư mục đích Summary."""
        try:
            that = goc.resolve()
        except OSError:
            return True
        for cam, ten in ((HISTORY_DIR, 'history'), (SUMMARY_DIR, 'data/summary')):
            try:
                that.relative_to(cam.resolve())
            except (ValueError, OSError):
                continue
            messagebox.showerror('Nguồn không hợp lệ',
                                 f'Không dùng thư mục {ten} làm nguồn.')
            return False
        return True

    def _dat_goc_nguon(self, goc):
        self.goc_nguon = goc
        self.bien_nguon.set(str(goc))

    def _ve_goc_mac_dinh(self):
        self._dat_goc_nguon(self.chuc_nang_hien_tai()['goc_mac_dinh'])
        self.da_chon.clear()
        self.quet_lai()

    def _mo_dich(self):
        dich = self.chuc_nang_hien_tai()['goc_output']
        try:
            dich.mkdir(parents=True, exist_ok=True)
            os.startfile(str(dich))  # noqa: S606
        except OSError as loi:
            messagebox.showerror('Lỗi', f'Không mở được thư mục đích.\n{loi}')

    # ---------- quét và dựng cây ----------
    def _thu_muc_bi_loai(self):
        """Các thư mục không đưa vào kết quả quét."""
        loai = [HISTORY_DIR, SUMMARY_DIR]
        if self.chuc_nang_hien_tai()['key'] == 'markdown':
            loai.append(OUTPUT_DIR)
        ra = []
        for t in loai:
            try:
                ra.append(str(t.resolve()).lower())
            except OSError:
                ra.append(str(t).lower())
        return ra

    def _bo_qua_file(self, ten):
        """Summary được đọc output nhưng phải loại summary lặp và fixlog."""
        ten = ten.lower()
        if self.chuc_nang_hien_tai()['key'] == 'summary':
            return ten.endswith('_summary.md') or ten.endswith('.fixlog.md')
        return False

    def _tim_file(self, goc, exts):
        exts = tuple(e.lower() for e in exts)
        cam = self._thu_muc_bi_loai()
        la_summary = self.chuc_nang_hien_tai()['key'] == 'summary'
        ket_qua = []
        de_quy = self.bien_de_quy.get()

        def bi_cam(duong_dan):
            thap = str(duong_dan).lower()
            return any(thap == c or thap.startswith(c + os.sep) for c in cam)

        def duyet(thu_muc):
            if bi_cam(thu_muc):
                return
            try:
                with os.scandir(thu_muc) as it:
                    muc = list(it)
            except OSError as loi:
                self.ghi_log(f'Bỏ qua thư mục không đọc được: {thu_muc} ({loi})')
                return
            for e in muc:
                if e.name.startswith('~$'):
                    continue
                try:
                    if e.is_symlink():
                        continue
                    if e.is_dir():
                        if la_summary and e.name.lower() == 'assets':
                            continue
                        if de_quy:
                            duyet(e.path)
                    elif e.is_file() and os.path.splitext(e.name)[1].lower() in exts:
                        if not self._bo_qua_file(e.name):
                            ket_qua.append(Path(e.path))
                except OSError:
                    continue

        duyet(str(goc))
        return ket_qua

    def quet_lai(self):
        if self.dang_chay:
            return
        exts = self.phan_mo_rong()
        self.lbl_loc.configure(text='Lọc: ' + ' '.join(f'*{e}' for e in exts))
        if not self.goc_nguon.exists():
            try:
                self.goc_nguon.mkdir(parents=True, exist_ok=True)
            except OSError as loi:
                self.ghi_log(f'Không tạo được thư mục nguồn: {loi}')
        self.tat_ca_file = self._tim_file(self.goc_nguon, exts)
        con_lai = {str(p) for p in self.tat_ca_file}
        self.da_chon = {k: v for k, v in self.da_chon.items() if k in con_lai}
        if not self.tat_ca_file:
            self.ghi_log(f'Không tìm thấy file {" ".join(exts)} trong {self.goc_nguon}')
        else:
            self.ghi_log(f'Đã quét {self.goc_nguon}. Tìm thấy {len(self.tat_ca_file)} file.')
        self._dung_cay()

    def _hen_tim(self, *_):
        if self._ma_tim:
            self.after_cancel(self._ma_tim)
        self._ma_tim = self.after(250, self._dung_cay)

    def _dung_cay(self):
        self._ma_tim = None
        self.tree.delete(*self.tree.get_children())
        self.item_map.clear()
        self.path_to_iid.clear()

        tim = self.bien_tim.get().strip().lower()
        goc = self.goc_nguon
        hien = [f for f in self.tat_ca_file if not tim or tim in str(f).lower()]
        # Hiện chính thư mục gốc làm nút đầu cây như ảnh thiết kế, đồng thời cho
        # một ô chọn tổng cho toàn bộ nhánh.
        if hien:
            iid_goc = self.tree.insert('', 'end', text=' ' + (goc.name or str(goc)),
                                       values=('', ''), open=True,
                                       image=self.anh_o['trong'])
            self.item_map[iid_goc] = ('thu_muc', goc)
            cache = {str(goc): iid_goc}
        else:
            cache = {str(goc): ''}
        for f in sorted(hien, key=lambda p: str(p).lower()):
            cha = self._dam_bao_thu_muc(f.parent, cache)
            du_kien = self.duong_dan_output(f)
            iid = self.tree.insert(cha, 'end', text=' ' + f.name,
                                   values=('Chờ', self.ten_hien_thi(du_kien)),
                                   image=self.anh_o['trong'])
            self.item_map[iid] = ('file', f)
            self.path_to_iid[str(f)] = iid
        self._ve_lai_o_chon()

    def _dam_bao_thu_muc(self, thu_muc, cache):
        thu_muc = Path(thu_muc)
        key = str(thu_muc)
        if key in cache:
            return cache[key]
        cha = self._dam_bao_thu_muc(thu_muc.parent, cache)
        iid = self.tree.insert(cha, 'end', text=' ' + thu_muc.name, values=('', ''),
                               open=True, image=self.anh_o['trong'])
        self.item_map[iid] = ('thu_muc', thu_muc)
        cache[key] = iid
        return iid

    # ---------- ô chọn ----------
    def _file_con(self, iid):
        ra = []
        for con in self.tree.get_children(iid):
            loai, gt = self.item_map.get(con, (None, None))
            if loai == 'file':
                ra.append((con, gt))
            elif loai == 'thu_muc':
                ra.extend(self._file_con(con))
        return ra

    def _nhan_chuot_cay(self, e):
        if self.dang_chay:
            return None
        iid = self.tree.identify_row(e.y)
        if not iid:
            return None
        phan_tu = str(self.tree.identify_element(e.x, e.y))
        if 'indicator' in phan_tu:
            return None
        if 'image' in phan_tu or 'text' in phan_tu:
            self.tree.focus(iid)
            self.tree.selection_set(iid)
            self._doi_o_chon(iid)
            return 'break'
        return None

    def _nhan_phim_cach(self, _e):
        iid = self.tree.focus()
        if iid and not self.dang_chay:
            self._doi_o_chon(iid)
        return 'break'

    def _doi_o_chon(self, iid):
        loai, gt = self.item_map.get(iid, (None, None))
        if loai == 'file':
            self.da_chon[str(gt)] = not self.da_chon.get(str(gt), False)
        elif loai == 'thu_muc':
            cons = self._file_con(iid)
            if not cons:
                return
            dat = not all(self.da_chon.get(str(p), False) for _, p in cons)
            for _, p in cons:
                self.da_chon[str(p)] = dat
        self._ve_lai_o_chon()

    def _chon_toan_bo(self, gia_tri):
        if self.dang_chay:
            return
        for iid, (loai, p) in self.item_map.items():
            if loai == 'file':
                self.da_chon[str(p)] = gia_tri
        self._ve_lai_o_chon()

    def _file_da_chon(self):
        return [p for p in sorted(self.tat_ca_file, key=lambda x: str(x).lower())
                if self.da_chon.get(str(p), False)]

    def _ve_lai_o_chon(self):
        for iid in self.tree.get_children(''):
            self._ve_nhanh(iid)
        cac_file = self._file_da_chon()
        self.lbl_dem.configure(text=f'Đã chọn {len(cac_file)} file')
        cho_phep = bool(cac_file) and not self.dang_chay
        self.btn_bat_dau.configure(state='normal' if cho_phep else 'disabled')
        self.btn_xem_md.configure(
            state='normal' if (self._md_de_xem(cac_file) and not self.dang_chay) else 'disabled')

    def _md_de_xem(self, cac_file):
        """File .md sẽ mở khi bấm Xem Markdown, chỉ khi chọn đúng một file."""
        if len(cac_file) != 1:
            return None
        f = cac_file[0]
        if f.suffix.lower() == '.md':
            return f
        dich = self.duong_dan_output(f)
        return dich if dich.exists() else None

    def _ve_nhanh(self, iid):
        """Vẽ lại ô chọn cho một nhánh, trả về (tong_file, so_file_da_chon)."""
        loai, gt = self.item_map.get(iid, (None, None))
        if loai == 'file':
            co = self.da_chon.get(str(gt), False)
            self.tree.item(iid, image=self.anh_o['chon' if co else 'trong'],
                           tags=('da_chon',) if co else ())
            return 1, (1 if co else 0)
        tong = chon = 0
        for con in self.tree.get_children(iid):
            a, b = self._ve_nhanh(con)
            tong += a
            chon += b
        if tong and chon == tong:
            trang_thai = 'chon'
        elif chon:
            trang_thai = 'mot_phan'
        else:
            trang_thai = 'trong'
        self.tree.item(iid, image=self.anh_o[trang_thai])
        return tong, chon

    def _mo_xem_markdown(self):
        f = self._md_de_xem(self._file_da_chon())
        if f is None:
            return
        markdown_viewer.mo_cua_so(self, f, HO_CHU, CO_CHU)

    # ---------- chạy ----------
    def _bat_dau(self):
        if self.dang_chay:
            return
        files = self._file_da_chon()
        if not files:
            messagebox.showinfo('Thông báo', 'Chưa chọn file nào để chạy.')
            return

        task = self.tac_vu_hien_tai()
        ma_luot = uuid.uuid4().hex[:12]

        # Hai input cùng ánh xạ tới một đích phải chặn trước khi chạy, không để
        # hai worker cùng ghi một file.
        da_dung = {}
        for f in files:
            out = self.duong_dan_output(f)
            if not self._nam_trong_dich(out):
                messagebox.showerror('Đích không hợp lệ',
                                     f'Đường dẫn đích nằm ngoài thư mục đích:\n{out}')
                return
            khoa = str(out).lower()
            if khoa in da_dung:
                messagebox.showerror(
                    'Trùng đích',
                    'Hai file nguồn cùng cho ra một file kết quả:\n\n'
                    f'{da_dung[khoa]}\n{f}\n\nĐích: {out}\n\n'
                    'Bỏ bớt một file rồi chạy lại.')
                return
            da_dung[khoa] = f

        jobs = []
        for f in files:
            out = self.duong_dan_output(f)
            ten_dich = self.ten_hien_thi(out)
            if out.exists():
                self.ghi_log(f'Đang chờ lựa chọn cho file trùng tên: {ten_dich}')
                hop = HopThoaiTrung(self, str(f), str(out))
                if hop.ket_qua == 'huy':
                    self.ghi_log('Đã hủy lượt chạy.')
                    return
                if hop.ket_qua == 'bo_qua':
                    self._cap_nhat(f, 'Bỏ qua', ten_dich)
                    self._ghi_history(task, f, out, 'Bỏ qua', 'Bỏ qua', None, ma_luot)
                    continue
            jobs.append((f, out))

        if not jobs:
            self.ghi_log('Không còn file nào để chạy sau khi bỏ qua.')
            return

        self.dang_chay = True
        self.dung_sau = False
        self._khoa(True)
        for f, out in jobs:
            self._cap_nhat(f, 'Chờ chạy', self.ten_hien_thi(out))
        self.ghi_log(f'Bắt đầu lượt {ma_luot}: {len(jobs)} file, tác vụ {task["nhan"]}.')
        tuy_chon = self._tuy_chon_hien_tai()
        threading.Thread(target=self._worker, args=(task, jobs, ma_luot, tuy_chon),
                         daemon=True).start()

    def _tuy_chon_hien_tai(self):
        """Chụp các lựa chọn combo ngay lúc bấm chạy để worker không đọc widget."""
        return {
            'refine_mode': REFINE_SUB[self.combo_refine.current()]['mode'],
            'ngon_ngu': NGON_NGU[self.combo_ngon_ngu.current()][0],
            'loai': LOAI_VAN_BAN[self.combo_loai.current()][0],
        }

    def _worker(self, task, jobs, ma_luot, tuy_chon):
        try:
            if task['key'] == 'native':
                self._chay_native(task, jobs, ma_luot)
            else:
                for f, out in jobs:
                    if self.dung_sau:
                        self.q.put(('log', 'Đã dừng theo yêu cầu, các file còn lại chưa chạy.'))
                        break
                    self._chay_mot_file(task, f, out, ma_luot, tuy_chon)
        finally:
            self.q.put(('xong', None))

    def _tao_thu_muc_dich(self, thu_muc):
        """Chỉ tạo thư mục đích khi thật sự có file sắp chạy."""
        try:
            thu_muc.mkdir(parents=True, exist_ok=True)
            return True, ''
        except OSError as loi:
            return False, f'Không tạo được thư mục đích: {loi}'

    def _chay_mot_file(self, task, f, out, ma_luot, tuy_chon):
        self.q.put(('trang_thai', (f, 'Đang chạy', self.ten_hien_thi(out))))
        xong, loi = self._tao_thu_muc_dich(out.parent)
        if not xong:
            self._bao_ket_qua(task, f, out, 'loi', loi, ma_luot)
            return
        cmd = [sys.executable, '-u', str(SRC_DIR / task['script'])]
        if task['key'] == 'refine':
            cmd.append(tuy_chon['refine_mode'])
        cmd.append(str(f))
        if task['key'] == 'summary':
            cmd += ['--ngon-ngu', tuy_chon['ngon_ngu'], '--loai', tuy_chon['loai']]
        ma, loi = self._chay_subprocess(cmd, out, out.parent)
        self._bao_ket_qua(task, f, out, ma, loi, ma_luot)

    def _chay_native(self, task, jobs, ma_luot):
        """Native chạy theo lô, giữ pool sẵn có của script.

        Mỗi thư mục đích là một lô riêng vì script nhận thư mục output qua biến
        môi trường, mỗi tiến trình con chỉ ghi được vào một thư mục.
        """
        nhom = {}
        for f, out in jobs:
            nhom.setdefault(out.parent, []).append((f, out))

        for thu_muc, cac_job in nhom.items():
            if self.dung_sau:
                self.q.put(('log', 'Đã dừng theo yêu cầu, các file còn lại chưa chạy.'))
                break
            for f, out in cac_job:
                self.q.put(('trang_thai', (f, 'Đang chạy', self.ten_hien_thi(out))))
            xong, loi_tao = self._tao_thu_muc_dich(thu_muc)
            if not xong:
                for f, out in cac_job:
                    self._bao_ket_qua(task, f, out, 'loi', loi_tao, ma_luot)
                continue
            with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False,
                                             encoding='utf-8', newline='\n') as tf:
                for f, _ in cac_job:
                    tf.write(str(f) + '\n')
                danh_sach = tf.name
            try:
                cmd = [sys.executable, '-u', str(SRC_DIR / task['script']),
                       '--list', danh_sach, '--force']
                _, loi_chung = self._chay_subprocess(cmd, None, thu_muc)
                for f, out in cac_job:
                    if out.exists() and out.stat().st_size > 0:
                        self._bao_ket_qua(task, f, out, 'ok', '', ma_luot)
                    else:
                        self._bao_ket_qua(task, f, out, 'loi',
                                          loi_chung or 'Không tạo được file kết quả.', ma_luot)
            finally:
                try:
                    os.unlink(danh_sach)
                except OSError:
                    pass

    def _chay_subprocess(self, cmd, out, thu_muc_dich=None):
        """Trả về (ma, thong_diep) với ma là 'ok', 'bo_qua' hoặc 'loi'."""
        # Script con in tiếng Việt và ký hiệu ngoài bảng mã cp1252. Khi chạy qua
        # pipe, stdout của tiến trình con lấy encoding theo locale nên sẽ lỗi
        # UnicodeEncodeError; ép UTF-8 cho tiến trình con để tránh việc đó.
        moi_truong = os.environ.copy()
        moi_truong['PYTHONIOENCODING'] = 'utf-8'
        moi_truong['PYTHONUTF8'] = '1'
        # Người dùng đã quyết định Thay thế hoặc Bỏ qua ở GUI, nên tắt bước bỏ
        # qua ngầm bên trong script để Thay thế thực sự chạy lại.
        moi_truong['PDF2MD_FORCE'] = '1'
        if thu_muc_dich is not None:
            moi_truong['PDF2MD_OUTPUT_DIR'] = str(thu_muc_dich)
        try:
            kq = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                                encoding='utf-8', errors='replace', env=moi_truong,
                                creationflags=CREATE_NO_WINDOW)
        except Exception as loi:  # noqa: BLE001
            return 'loi', str(loi)
        duoi = ((kq.stdout or '')[-400:] + (kq.stderr or '')[-400:]).strip()
        if kq.returncode == MA_BO_QUA:
            return 'bo_qua', duoi or 'Bỏ qua'
        if kq.returncode == MA_THIEU:
            if out is not None and not (out.exists() and out.stat().st_size > 0):
                return 'loi', duoi or 'Chạy xong nhưng không thấy file kết quả.'
            return 'thieu', duoi or 'Có trang chưa trích xuất được.'
        if kq.returncode != 0:
            return 'loi', duoi or f'Mã lỗi {kq.returncode}'
        if out is not None and not (out.exists() and out.stat().st_size > 0):
            return 'loi', 'Chạy xong nhưng không thấy file kết quả.'
        return 'ok', ''

    def _bao_ket_qua(self, task, f, out, ma, loi, ma_luot):
        ten_dich = self.ten_hien_thi(out)
        if ma == 'ok':
            self.q.put(('trang_thai', (f, 'Thành công', ten_dich)))
            self.q.put(('log', f'[OK] {f.name} sang {ten_dich}'))
            self._ghi_history(task, f, out, 'Thay thế hoặc tạo mới', 'Thành công', None, ma_luot)
        elif ma == 'thieu':
            self.q.put(('trang_thai', (f, 'Thiếu trang', (loi or '')[:150])))
            self.q.put(('log', f'[THIẾU TRANG] {f.name} sang {ten_dich}: {loi}'))
            self._ghi_history(task, f, out, 'Thay thế hoặc tạo mới',
                              'Thành công một phần', loi, ma_luot)
        elif ma == 'bo_qua':
            self.q.put(('trang_thai', (f, 'Bỏ qua', (loi or '')[:150])))
            self.q.put(('log', f'[BỎ QUA] {f.name}: {loi}'))
            self._ghi_history(task, f, out, 'Bỏ qua', 'Bỏ qua', loi, ma_luot)
        else:
            self.q.put(('trang_thai', (f, 'Lỗi', (loi or '')[:150])))
            self.q.put(('log', f'[LỖI] {f.name}: {loi}'))
            self._ghi_history(task, f, out, 'Thay thế hoặc tạo mới', 'Lỗi', loi, ma_luot)

    def _ghi_history(self, task, nguon, dich, lua_chon, trang_thai, loi, ma_luot):
        ban_ghi = {
            'ma_luot': ma_luot,
            'chuc_nang': self.chuc_nang_hien_tai()['nhan'],
            'tac_vu': task['nhan'],
            'nguon': str(nguon),
            'dich': str(dich),
            'lua_chon': lua_chon,
            'trang_thai': trang_thai,
            'loi': loi,
        }
        if task['key'] == 'summary':
            ban_ghi['ngon_ngu'] = NGON_NGU[self.combo_ngon_ngu.current()][0]
            ban_ghi['loai_van_ban'] = LOAI_VAN_BAN[self.combo_loai.current()][0]
            ban_ghi['model'] = (os.getenv('GEMINI_MODEL') or '').strip()
        try:
            history_log.ghi(HISTORY_DIR, ban_ghi)
        except Exception as e:  # noqa: BLE001
            self.q.put(('log', f'Cảnh báo: không ghi được lịch sử ({e})'))

    def _yeu_cau_dung(self):
        self.dung_sau = True
        self.btn_dung.configure(state='disabled')
        self.ghi_log('Sẽ dừng sau lượt hiện tại.')

    # ---------- hỗ trợ ----------
    def _khoa(self, khoa):
        trang_thai = 'disabled' if khoa else 'normal'
        for w in (self.btn_duyet, self.btn_ve_goc, self.btn_quet, self.chk_de_quy,
                  self.btn_chon_het, self.btn_bo_chon, self.btn_bat_dau, self.entry_tim,
                  self.btn_xem_md):
            try:
                w.configure(state=trang_thai)
            except tk.TclError:
                pass
        doc = 'disabled' if khoa else 'readonly'
        for w in (self.combo_chuc_nang, self.combo_tac_vu, self.combo_ngon_ngu,
                  self.combo_loai):
            w.configure(state=doc)
        if khoa or self.tac_vu_hien_tai()['key'] != 'refine':
            self.combo_refine.configure(state='disabled')
        else:
            self.combo_refine.configure(state='readonly')
        self.btn_dung.configure(state='normal' if khoa else 'disabled')

    def _cap_nhat(self, path, trang_thai, ket_qua):
        iid = self.path_to_iid.get(str(path))
        if iid:
            self.tree.set(iid, 'trang_thai', trang_thai)
            self.tree.set(iid, 'ket_qua', ket_qua)

    def ghi_log(self, dong):
        self.txt_log.configure(state='normal')
        self.txt_log.insert('end', dong + '\n')
        if int(self.txt_log.index('end-1c').split('.')[0]) > 2000:
            self.txt_log.delete('1.0', '200.0')
        self.txt_log.see('end')
        self.txt_log.configure(state='disabled')

    def _poll(self):
        try:
            for _ in range(200):
                loai, data = self.q.get_nowait()
                if loai == 'log':
                    self.ghi_log(data)
                elif loai == 'trang_thai':
                    self._cap_nhat(*data)
                elif loai == 'xong':
                    self.dang_chay = False
                    self._khoa(False)
                    self._ve_lai_o_chon()
                    self._cap_nhat_nhan_lich_su()
                    self.ghi_log('Hoàn tất lượt chạy.')
        except queue.Empty:
            pass
        self.after(100, self._poll)


def main():
    # Khóa một phiên để hai bản PDF2MD không cùng thay đổi lịch sử và output.
    khoa = khoa_phien.KhoaPhien(HISTORY_DIR / 'pdf2md.lock')
    if not khoa.thu_khoa():
        goc = tk.Tk()
        goc.withdraw()
        messagebox.showerror(
            'PDF2MD đang chạy',
            'Một phiên PDF2MD khác đang mở và đang giữ khóa ghi.\n\n'
            'Đóng cửa sổ đó rồi mở lại, để hai phiên không cùng ghi lịch sử và output.')
        goc.destroy()
        return 1
    try:
        UngDung().mainloop()
    finally:
        khoa.nha_khoa()
    return 0


if __name__ == '__main__':
    sys.exit(main())
