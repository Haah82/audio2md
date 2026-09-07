"""Chuyển văn bản font tiếng Việt đời cũ (VNI-Times, TCVN3/.VnTime) sang Unicode
NGAY TẠI MÁY, không tốn một token nào.

VÌ SAO CẦN
    Tài liệu soạn bằng font đời cũ lưu ra PDF thì lớp text là mã của font đó chứ
    không phải Unicode: 'khái niệm đàm phán' đọc ra thành 'khaùi nieäm ñaøm
    phaùn'. Hậu quả trong pipeline này:
      - Đường native (miễn phí) cho ra markdown rác -> buộc phải đẩy sang đường
        scan, trả 258 token/trang cho việc lẽ ra không mất đồng nào.
      - Bộ dò trang thiếu so lớp text sai với markdown đúng -> báo thiếu giả cả
        tài liệu (bộ slide 'Negotiate in PM' bị báo thiếu 11/12 trang).

NGUỒN BẢNG MÃ
    Bảng tra lấy từ refer-2-convert_font/font_maps.py (bản sinh tự động từ
    TN.FONTVIET-R8-CODE/P01Font.bas). Ở đây chỉ NẠP LẠI, không chép bảng, để dữ
    liệu chỉ có một nguồn duy nhất. Thiếu thư mục đó thì mọi hàm trả về nguyên
    văn đầu vào - chuyển font là bước phụ trợ, tuyệt đối không được làm hỏng
    luồng chính.

CẢNH BÁO QUAN TRỌNG
    KHÔNG được chạy hàm chuyển lên cả trang văn bản hỗn hợp. Đo thực tế: chạy
    vni_to_unicode() lên tiếng Việt Unicode đúng làm 'Nông' thành 'Nơng',
    tcvn3_to_unicode() làm 'khái' thành 'khỏi'. Phải chuyển THEO TỪNG SPAN kèm
    đúng tên font của span đó - dùng bang_thay_the() bên dưới.
"""

import os
import sys
import importlib.util
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_HERE)
THU_MUC_THAM_CHIEU = os.path.join(BASE_DIR, 'refer-2-convert_font')


def _nap_thu_vien():
    """Nạp encoding_core của công cụ convert_font.

    Thư viện đó import theo tên gói 'convert_font' nên phải dựng sẵn một gói bí
    danh trỏ vào thư mục tham chiếu thì mới nạp được từ ngoài.
    """
    if not os.path.isdir(THU_MUC_THAM_CHIEU):
        return None
    try:
        if 'convert_font' not in sys.modules:
            goi = types.ModuleType('convert_font')
            goi.__path__ = [THU_MUC_THAM_CHIEU]
            sys.modules['convert_font'] = goi
        for ten in ('font_maps', 'encoding_core'):
            khoa = f'convert_font.{ten}'
            if khoa in sys.modules:
                continue
            spec = importlib.util.spec_from_file_location(
                khoa, os.path.join(THU_MUC_THAM_CHIEU, f'{ten}.py'))
            mod = importlib.util.module_from_spec(spec)
            sys.modules[khoa] = mod
            spec.loader.exec_module(mod)
        return sys.modules['convert_font.encoding_core']
    except Exception:
        return None


_EC = _nap_thu_vien()
SAN_SANG = _EC is not None


def ho_font(ten_font):
    """'VNI-Times' -> 'vni'; '.VnTime' -> 'tcvn3'; còn lại -> 'unicode'."""
    if not SAN_SANG:
        return 'unicode'
    try:
        return _EC.detect_font_family(ten_font or '').value
    except Exception:
        return 'unicode'


def la_font_doi_cu(ten_font):
    return ho_font(ten_font) in ('vni', 'tcvn3')


def sang_unicode(text, ten_font):
    """Chuyển một đoạn văn bản BIẾT TRƯỚC tên font sang Unicode."""
    if not SAN_SANG or not text:
        return text
    try:
        return _EC.convert_segment(text, ten_font or '', _EC.FontFamily.UNICODE)
    except Exception:
        return text


# --- Áp dụng cho một trang/tài liệu PDF --------------------------------------

def quet_span_doi_cu(doc, tu_trang=0, den_trang=None):
    """Duyệt các span trong PDF, trả về (tong_ky_tu, ky_tu_font_cu, danh_sach).

    danh_sach là [(text_goc, ten_font), ...] của riêng những span dùng font đời
    cũ - đủ để dựng bảng thay thế mà không đụng tới phần Unicode sẵn đúng.
    """
    den_trang = doc.page_count - 1 if den_trang is None else den_trang
    tong = cu = 0
    ds = []
    for p in range(tu_trang, min(den_trang, doc.page_count - 1) + 1):
        try:
            khoi = doc[p].get_text('dict')['blocks']
        except Exception:
            continue
        for b in khoi:
            for l in b.get('lines', []):
                for s in l.get('spans', []):
                    t = s.get('text') or ''
                    if not t.strip():
                        continue
                    tong += len(t)
                    if la_font_doi_cu(s.get('font')):
                        cu += len(t)
                        ds.append((t, s.get('font')))
    return tong, cu, ds


def ti_le_font_doi_cu(doc, so_trang_mau=8):
    """Tỉ lệ ký tự dùng font đời cũ, lấy mẫu vài trang đầu cho nhanh."""
    tong, cu, _ = quet_span_doi_cu(doc, 0, min(so_trang_mau, doc.page_count) - 1)
    return (cu / tong) if tong else 0.0


def bang_thay_the(danh_sach_span):
    """Dựng bảng {chuoi_goc: chuoi_unicode} từ các span font đời cũ.

    Sắp theo độ dài giảm dần khi áp dụng để chuỗi dài được thay trước, tránh
    một chuỗi ngắn nằm lọt trong chuỗi dài bị thay trước làm hỏng chuỗi dài.
    """
    bang = {}
    for text, ten_font in danh_sach_span:
        for dang in (text, text.strip()):
            if not dang or dang in bang:
                continue
            moi = sang_unicode(dang, ten_font)
            if moi != dang:
                bang[dang] = moi
    return bang


def ap_bang(van_ban, bang):
    """Thay thế theo bảng, chuỗi dài trước. Trả về (van_ban_moi, so_lan_thay)."""
    if not bang or not van_ban:
        return van_ban, 0
    so_lan = 0
    for goc in sorted(bang, key=len, reverse=True):
        if goc in van_ban:
            so_lan += van_ban.count(goc)
            van_ban = van_ban.replace(goc, bang[goc])
    return van_ban, so_lan


# Chữ cái Latin chỉ xuất hiện trong font đời cũ, KHÔNG có trong tiếng Việt lẫn
# tiếng Anh. Một từ chứa chúng thì chắc chắn là mã font cũ -> chuyển được an toàn.
# Ngược lại 'Nông' chỉ chứa 'ô' hợp lệ nên không bị đụng tới (chạy vni_to_unicode
# lên nó sẽ ra 'Nơng' - chính là cái bẫy phải né).
_DAU_HIEU_RIENG = set('ñøöäïåæ')


def _vet_tu_con_sot(van_ban):
    """Vét nốt những TỪ còn sót mã font cũ sau khi đã thay theo span.

    Span khớp được ~90%; phần hụt là do engine markdown cắt/ghép lại chuỗi. Ở
    đây chỉ đụng vào từ nào còn mang dấu hiệu riêng của font cũ nên không thể
    làm hỏng văn bản Unicode.
    """
    if not SAN_SANG or not van_ban:
        return van_ban, 0
    import re
    so_lan = [0]

    def _doi(m):
        tu = m.group(0)
        co_dau_hieu = bool(_DAU_HIEU_RIENG & set(tu.lower()))
        for ten_font in ('VNI-Times', '.VnTime'):
            moi = sang_unicode(tu, ten_font)
            if moi == tu:
                continue
            # VNI ghép 2 ký tự (chữ gốc + ký tự dấu) thành 1 ký tự Unicode, nên
            # chuyển ĐÚNG thì từ phải NGẮN LẠI: 'caàn'(4) -> 'cần'(3),
            # 'yù'(2) -> 'ý'(1). Ngược lại phép đổi 1-đổi-1 giữ nguyên độ dài
            # chính là cái bẫy phá dữ liệu: 'Nông'(4) -> 'Nơng'(4). Chỉ nhận khi
            # từ ngắn lại, hoặc khi từ mang chữ cái chỉ có ở font đời cũ.
            if len(moi) < len(tu) or co_dau_hieu:
                so_lan[0] += 1
                return moi
        return tu

    return re.sub(r'\S+', _doi, van_ban), so_lan[0]


def sua_markdown_theo_pdf(van_ban_md, doc):
    """Sửa markdown đã trích xuất bằng bảng thay thế lấy từ chính PDF.

    Chỉ đụng vào đúng những chuỗi xuất phát từ span font đời cũ, nên phần văn
    bản vốn đã là Unicode không hề bị động tới - đây là điểm mấu chốt vì tài
    liệu thực tế thường trộn cả hai (VNI-Times cho thân bài, Times New Roman
    cho tên riêng và số trang).

    Trả về (van_ban_moi, so_lan_thay, ti_le_font_cu).
    """
    if not SAN_SANG or not van_ban_md:
        return van_ban_md, 0, 0.0
    tong, cu, ds = quet_span_doi_cu(doc)
    if not ds:
        return van_ban_md, 0, 0.0
    moi, so_lan = ap_bang(van_ban_md, bang_thay_the(ds))
    moi, them = _vet_tu_con_sot(moi)
    return moi, so_lan + them, (cu / tong if tong else 0.0)
