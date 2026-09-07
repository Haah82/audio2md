"""Ước tính token TRƯỚC KHI chạy, để không bấm nhầm một bộ hồ sơ trăm trang rồi
mới biết nó ăn hết credit.

    python src/uoc_chi_phi.py                      # quét cả data/input
    python src/uoc_chi_phi.py "data/input/afd"     # một thư mục
    python src/uoc_chi_phi.py "ho-so.pdf"          # một file

CƠ SỞ TÍNH
    Google tính mỗi trang PDF là 258 token đầu vào, CỐ ĐỊNH bất kể độ phân giải
    ("Each document page is equivalent to 258 tokens" - tài liệu Gemini API).
    Nên chi phí đầu vào của một tài liệu scan chỉ phụ thuộc SỐ TRANG, không phụ
    thuộc file nặng hay nhẹ. Muốn giảm thì chỉ có cách gửi ít trang hơn - đó
    đúng là việc mà cache theo cụm và lệnh vá trang thiếu đang làm.

    Token đầu ra ước theo mật độ chữ của lớp text (khoảng 4 ký tự/token, cộng
    thêm phần markdown sinh ra cho bảng biểu). Với trang scan thuần ảnh không có
    lớp text thì lấy mức trung bình đo được trên tài liệu thật.

Con số ở đây là ƯỚC TÍNH để so sánh và cảnh báo, không phải hoá đơn.
"""

import os
import sys
import glob

import pymupdf

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

BASE_DIR = os.path.dirname(_HERE)
INPUT_DIR = os.path.join(BASE_DIR, 'data', 'input')
OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'output')

# Trang PDF luôn là 258 token đầu vào (tài liệu Gemini API).
TOKEN_MOI_TRANG = 258
# Ước 4 ký tự / 1 token cho tiếng Việt lẫn tiếng Anh trong tài liệu kỹ thuật.
KY_TU_MOI_TOKEN = 4.0
# Markdown sinh ra thường dài hơn lớp text gốc (thêm ký hiệu bảng, tiêu đề).
HE_SO_PHINH_MARKDOWN = 1.25
# Trang scan không có lớp text: lấy mức trung bình đo trên tài liệu AFD.
TOKEN_RA_TRANG_SCAN = 320


def _lay_scan(pdf_path):
    """Đọc mô-đun 3_pdf_scan.py để dùng đúng thuật toán chia cụm thật."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'pdf_scan', os.path.join(_HERE, '3_pdf_scan.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def uoc_mot_file(pdf_path, scan):
    """Trả về dict ước tính cho một PDF."""
    doc = pymupdf.open(pdf_path)
    try:
        so_trang = doc.page_count
        ky_tu = 0
        trang_khong_text = 0
        for p in range(so_trang):
            n = len(doc[p].get_text())
            ky_tu += n
            if n < scan.SCAN_PAGE_MAX_CHARS:
                trang_khong_text += 1
        cum = scan.plan_chunks(doc)

        token_vao = so_trang * TOKEN_MOI_TRANG
        token_ra = int(ky_tu / KY_TU_MOI_TOKEN * HE_SO_PHINH_MARKDOWN
                       + trang_khong_text * TOKEN_RA_TRANG_SCAN)
        return {
            'ten': os.path.basename(pdf_path),
            'trang': so_trang,
            'trang_scan': trang_khong_text,
            'cum': len(cum),
            'token_vao': token_vao,
            'token_ra': token_ra,
            'mb': os.path.getsize(pdf_path) / 1e6,
        }
    finally:
        doc.close()


def da_co_ket_qua(pdf_path):
    """File đã có .md tương ứng thì lần chạy sau chỉ tốn tiền cho phần thiếu."""
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    thu_muc = os.path.dirname(os.path.abspath(pdf_path))
    import re
    doi = re.sub(r'([\\/])input([\\/]|$)', r'\1output\2', thu_muc)
    for d in (doi, thu_muc):
        for hau_to in ('_scan', '_native'):
            if os.path.exists(os.path.join(d, f"{base}{hau_to}.md")):
                return True
    return False


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    goc = args[0] if args else INPUT_DIR
    if not os.path.exists(goc):
        print(f"❌ Không thấy: {goc}")
        return 2

    if os.path.isdir(goc):
        files = sorted(glob.glob(os.path.join(goc, '**', '*.pdf'), recursive=True))
    else:
        files = [goc]
    if not files:
        print(f"❌ Không thấy file PDF nào trong: {goc}")
        return 2

    scan = _lay_scan(None)
    print(f"\n📐 Ước tính token cho {len(files)} file PDF")
    print(f"   Cơ sở: mỗi trang PDF = {TOKEN_MOI_TRANG} token vào (cố định, "
          f"không phụ thuộc độ phân giải)\n")
    print(f"   {'Tài liệu':<44} {'Trang':>6} {'Cụm':>5} "
          f"{'Token vào':>11} {'Token ra':>10}  Ghi chú")
    print("   " + "-" * 96)

    tong_vao = tong_ra = tong_trang = 0
    da_xong = []
    for f in files:
        try:
            u = uoc_mot_file(f, scan)
        except Exception as e:  # noqa: BLE001
            print(f"   {os.path.basename(f)[:44]:<44} lỗi đọc: {e}")
            continue
        xong = da_co_ket_qua(f)
        ghi_chu = "đã có .md -> chỉ cần VÁ phần thiếu" if xong else ""
        if xong:
            da_xong.append(u)
        else:
            tong_vao += u['token_vao']
            tong_ra += u['token_ra']
            tong_trang += u['trang']
        ten = u['ten'][:44]
        print(f"   {ten:<44} {u['trang']:>6,} {u['cum']:>5} "
              f"{u['token_vao']:>11,} {u['token_ra']:>10,}  {ghi_chu}")

    print("   " + "-" * 96)
    print(f"\n   CHƯA XỬ LÝ: {tong_trang:,} trang | "
          f"{tong_vao:,} token vào + {tong_ra:,} token ra "
          f"= {tong_vao + tong_ra:,} token")
    if da_xong:
        v = sum(u['token_vao'] for u in da_xong)
        r = sum(u['token_ra'] for u in da_xong)
        print(f"   ĐÃ CÓ .md : {len(da_xong)} file, chạy lại từ đầu sẽ tốn thêm "
              f"{v + r:,} token.")
        print(f"               Dùng mục 2.1 (vá phần thiếu) thay vì chạy lại "
              f"để khỏi trả tiền hai lần.")
    print("\n   Ghi chú: con số là ước tính để so sánh và cảnh báo, không phải "
          "hoá đơn.\n"
          "   Cache theo cụm và lệnh vá trang thiếu đã giúp không phải trả tiền\n"
          "   lại cho những cụm trang vốn đã chuyển đổi tốt.")
    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
