"""Chuyển PDF theo lối LAI GHÉP: chạy native trước (miễn phí, tại máy), chỉ gọi
Gemini cho đúng những trang native không xử lý được.

VÌ SAO
    Hồ sơ thầu thực tế là bản Word xuất PDF GHÉP với bản scan giấy tờ. Đẩy cả
    tập sang đường scan là trả 258 token cho từng trang, kể cả những trang vốn
    đã có sẵn lớp chữ đọc được miễn phí.

    Đo trên data/input/afd/AFD-Tuan Giao...pdf (475 trang):
        322 trang có lớp chữ  -> native, 0 token
        123 trang ảnh phủ kín -> Gemini (chữ OCR nhúng sẵn sai bét)
         30 trang ảnh trắng chữ -> Gemini
        => chỉ 153/475 trang phải gọi API, giảm ~68% token đầu vào
           (122.550 -> 39.474 token vào).

CÁCH LÀM
    1. Phân loại từng trang trước khi chạy.
    2. Chạy native cho cả tài liệu (một lượt, miễn phí).
    3. HẬU KIỂM: trang nào lẽ ra có chữ mà native cho ra rỗng/quá ít thì bổ sung
       vào danh sách phải quét lại - phân loại tĩnh không bắt hết được (bảng vỡ
       cấu trúc, font lạ).
    4. Gọi Gemini đúng những dải trang đó, chèn vào đúng vị trí trong markdown
       native. Dùng lại nguyên bộ máy đối chiếu + chèn vá đã có.
"""

import os
import re
import sys

import pymupdf

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import pdf_native_core as core          # noqa: E402
import patch_missing_pages as patch     # noqa: E402
import image_extractor                  # noqa: E402

scan = patch.scan
gemini_pool = scan.gemini_pool

BASE_DIR = os.path.dirname(_HERE)

# Trang có ảnh phủ từ ngần này diện tích trở lên là bản scan giấy tờ: chữ trên
# đó (nếu có) là OCR của bên khác nhúng sẵn, thường sai bét nên phải để Gemini
# đọc lại từ ảnh. Đo thực tế: trang text gốc phủ 0.9%, trang scan phủ 100%.
NGUONG_ANH_PHU = 0.9
# Trang có ít hơn ngần này ký tự coi như không có lớp chữ.
NGUONG_IT_CHU = scan.SCAN_PAGE_MAX_CHARS
# Hậu kiểm: trang lẽ ra có N ký tự mà markdown native chỉ ra được dưới tỉ lệ này
# thì coi như native đã hỏng ở trang đó.
TI_LE_HAU_KIEM = 0.30
# Hai dải cần quét cách nhau <= ngần này trang thì gộp làm một lượt gọi API.
GOP_DAI_CACH = 2

NATIVE, SCAN, ANH = 'native', 'scan', 'anh'


def phan_loai_trang(doc):
    """Nhãn cho từng trang: 'native' | 'scan' (ảnh phủ kín) | 'anh' (không chữ)."""
    nhan = []
    for p in range(doc.page_count):
        pg = doc[p]
        try:
            so_chu = len(pg.get_text().strip())
        except Exception:
            so_chu = 0
        if scan._ti_le_anh_phu_trang(pg) >= NGUONG_ANH_PHU:
            nhan.append(SCAN)
        elif so_chu < NGUONG_IT_CHU:
            nhan.append(ANH)
        else:
            nhan.append(NATIVE)
    return nhan


def thanh_dai(nhan, cac_loai, gop=GOP_DAI_CACH):
    """Gom các trang mang nhãn trong `cac_loai` thành dải (1-based, gồm 2 đầu)."""
    trang = [i + 1 for i, l in enumerate(nhan) if l in cac_loai]
    return patch.find_gaps(None, trang, merge_gap=gop) if trang else []


def kieu_nen_dung(doc, nhan=None):
    """Tự nhận diện nên chạy kiểu gì cho tài liệu này.

    'native'    - hầu như toàn chữ, không cần gọi API lần nào
    'scan'      - hầu như toàn ảnh, lai ghép không lợi gì mà thêm phức tạp
    'lai_ghep'  - lẫn lộn (chính là ca hồ sơ thầu)
    """
    nhan = nhan or phan_loai_trang(doc)
    if not nhan:
        return 'native'
    so_can_api = sum(1 for l in nhan if l != NATIVE)
    ti_le = so_can_api / len(nhan)
    if ti_le <= 0.02:
        return 'native'
    if ti_le >= 0.95:
        return 'scan'
    return 'lai_ghep'


def _tom_tat_phan_loai(nhan):
    from collections import Counter
    c = Counter(nhan)
    return (f"{c.get(NATIVE, 0)} trang chữ | {c.get(SCAN, 0)} trang scan | "
            f"{c.get(ANH, 0)} trang ảnh")


# --- Hậu kiểm bản native ------------------------------------------------------

def trang_native_hong(doc, trang_md, nhan):
    """Trang lẽ ra đọc được mà markdown native lại rỗng/quá ít -> phải quét lại.

    Phân loại tĩnh không bắt được mọi ca: bảng vỡ cấu trúc, font lạ, trang bị
    engine bỏ sót. Hậu kiểm bằng chính số ký tự thu được so với lớp text gốc.
    """
    hong = []
    for i, l in enumerate(nhan):
        if l != NATIVE or i >= len(trang_md):
            continue
        try:
            goc = len(scan._norm(doc[i].get_text()))
        except Exception:
            continue
        if goc < 200:            # trang thưa chữ, không đủ cơ sở kết luận
            continue
        ra = len(scan._norm(trang_md[i] or ''))
        if ra < goc * TI_LE_HAU_KIEM:
            hong.append(i + 1)
    return hong


# --- Chạy lai ghép ------------------------------------------------------------

def chay(pdf_path, out_path, be_key=None, model=None, in_ra=print,
         chi_dung_paid=False):
    """Chuyển 1 PDF theo lối lai ghép. Trả về dict thống kê."""
    doc = pymupdf.open(pdf_path)
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    out_dir = os.path.dirname(os.path.abspath(out_path))
    assets_dir = os.path.join(out_dir, image_extractor.ASSETS_DIRNAME)
    tk = {'trang': doc.page_count, 'goi_api': 0, 'trang_qua_api': 0}

    try:
        nhan = phan_loai_trang(doc)
        in_ra(f"📑 {doc.page_count} trang: {_tom_tat_phan_loai(nhan)}")

        # --- Bước 1: native cho cả tài liệu, miễn phí ---
        in_ra("🖥️  Chạy native tại máy (không tốn token)...")
        kq = core.convert(pdf_path, show_progress=False)
        md_native = kq.markdown
        tk['fixlog'] = kq.fixlog

        # --- Bước 2: chốt danh sách trang phải gọi API ---
        can_api = {i + 1 for i, l in enumerate(nhan) if l != NATIVE}
        trang_md = md_native.split('\f') if '\f' in md_native else None
        if trang_md and len(trang_md) == doc.page_count:
            them = trang_native_hong(doc, trang_md, nhan)
            if them:
                in_ra(f"🔍 Hậu kiểm: {len(them)} trang native cho ra quá ít chữ, "
                      f"bổ sung vào danh sách quét lại.")
                can_api |= set(them)

        if not can_api:
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(md_native)
            in_ra("✅ Toàn bộ tài liệu đọc được tại máy - KHÔNG tốn token nào.")
            tk['markdown'] = md_native
            return tk

        dai = patch.find_gaps(None, sorted(can_api), merge_gap=GOP_DAI_CACH)
        tk['trang_qua_api'] = len(can_api)
        in_ra(f"🤖 {len(can_api)}/{doc.page_count} trang phải gọi Gemini "
              f"({len(can_api)/doc.page_count*100:.0f}%), gom thành {len(dai)} dải: "
              f"{scan._fmt_ranges(sorted(can_api))}")
        in_ra(f"   Ước tính {len(can_api) * 258:,} token vào, thay vì "
              f"{doc.page_count * 258:,} nếu quét cả tập.")

        # --- Bước 3: gọi Gemini đúng các dải đó ---
        be_key = be_key or gemini_pool.pool()
        if not be_key.keys:
            raise RuntimeError("Chưa khai báo API key nào trong .env")
        model = model or (os.getenv('GEMINI_MODEL') or scan.DEFAULT_MODEL).strip()

        saved_imgs = image_extractor.extract_images(pdf_path, assets_dir, base_name=base)
        annex = {p: f for p, f in
                 scan.render_annex_pages(doc, assets_dir, base).items() if p in can_api}
        ctx = scan._Ctx(be_key, model, pdf_path, base, doc, saved_imgs, annex, scan.PROMPT)

        md_lines = md_native.split('\n')
        pos, _unv, _c = patch.align_pages(doc, md_lines)
        con_thieu = []
        for s, e in sorted(dai, reverse=True):     # vá từ dưới lên, khỏi lệch dòng
            in_ra(f"── Quét trang {s}-{e}")
            text, missing = scan.convert_range(ctx, s - 1, e - 1)
            tk['goi_api'] += 1
            con_thieu.extend(missing)
            if not (text or '').strip():
                continue
            at = patch.insert_line_for(s, e, pos, len(md_lines))
            khoi = ["", f"<!-- ▼ QUÉT LẠI BẰNG GEMINI: TRANG {s}-{e} -->", ""]
            khoi += text.strip().split('\n')
            khoi += ["", f"<!-- ▲ HẾT PHẦN QUÉT TRANG {s}-{e} -->", ""]
            md_lines[at:at] = khoi

        md_cuoi = '\n'.join(md_lines)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(md_cuoi)
        tk['markdown'] = md_cuoi
        tk['con_thieu'] = con_thieu
        in_ra(f"✅ Xong: {tk['goi_api']} lượt gọi API cho {len(can_api)} trang "
              f"(tiết kiệm {(doc.page_count - len(can_api)) * 258:,} token vào).")
        return tk
    finally:
        doc.close()


def main():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, '.env'))
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        print(__doc__)
        return 2
    pdf = args[0]
    if not os.path.exists(pdf):
        print(f"❌ Không thấy: {pdf}")
        return 2
    out_dir = os.environ.get('PDF2MD_OUTPUT_DIR') or os.path.join(BASE_DIR, 'data', 'output')
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(pdf))[0]
    out = os.path.join(out_dir, base + '_laighep.md')

    if '--chi-phan-loai' in sys.argv:
        d = pymupdf.open(pdf)
        nhan = phan_loai_trang(d)
        print(f"{os.path.basename(pdf)}: {_tom_tat_phan_loai(nhan)}")
        print(f"Kiểu nên dùng: {kieu_nen_dung(d, nhan)}")
        can = sorted(i + 1 for i, l in enumerate(nhan) if l != NATIVE)
        if can:
            print(f"Trang phải gọi API: {scan._fmt_ranges(can)}")
            print(f"Token vào ước tính: {len(can)*258:,} (quét cả tập: "
                  f"{d.page_count*258:,})")
        d.close()
        return 0

    tk = chay(pdf, out)
    print(f"\nKết quả: {out}")
    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
