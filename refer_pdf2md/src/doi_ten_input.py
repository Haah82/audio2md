"""Chuẩn hoá tên file trong data/input về dạng không dấu, chữ thường, gạch nối -
chạy TRƯỚC khi chuyển đổi sang Markdown.

    python src/doi_ten_input.py                  # xem trước, không đổi gì
    python src/doi_ten_input.py --that           # đổi tên thật
    python src/doi_ten_input.py "data/input/afd" --that --de-quy
    python src/doi_ten_input.py --duoi pdf --that

VÌ SAO CẦN
    1. SDK google-genai nhét tên file vào HTTP header rồi mã hoá ASCII, nên MỌI
       file có dấu tiếng Việt trong tên đều chết ngay ở bước upload:
           'ascii' codec can't encode character '\\u1ebf'   (chữ 'ế')
       Đổi tên từ đầu là cách chữa tận gốc, không phải chữa triệu chứng.
    2. Tên file sạch còn giúp Obsidian, git và đường dẫn tương đối trong Markdown
       không phải mã hoá phần trăm loằng ngoằng (%C4%90%C3%AA...).

LOGIC ĐỔI TÊN
    Lấy nguyên từ refer_rename_tool/rename-tool.py để hai công cụ cho ra cùng
    một kết quả: đ/Đ -> d, bỏ dấu bằng NFKD, về chữ thường, mọi ký tự không phải
    chữ/số thành '-', rồi cắt '-' ở hai đầu.

AN TOÀN
    - Mặc định CHỈ XEM TRƯỚC. Phải thêm --that mới đổi thật.
    - File .md đã xuất tương ứng trong data/output được đổi tên THEO, giữ nguyên
      hậu tố _scan/_native, để cặp PDF-Markdown không bị đứt (lệnh vá trang
      thiếu dựa vào cặp này). Thư mục assets/ của tài liệu cũng đổi theo.
    - Ghi nhật ký vào rename.log để lần ngược lại được.
    - Trùng tên thì thêm hậu tố -2, -3... chứ không ghi đè.
"""

import os
import re
import sys
import glob
import datetime
import unicodedata

_HERE = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_HERE)
INPUT_DIR = os.path.join(BASE_DIR, 'data', 'input')
OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'output')

HAU_TO_MD = ('_scan', '_native', '_refined', '')


def chuan_hoa_ten(text):
    """Port nguyên logic format_filename() của refer_rename_tool/rename-tool.py."""
    # 1. Chữ 'đ/Đ' của tiếng Việt phải xử lý riêng vì NFKD không tách được.
    text = text.replace('đ', 'd').replace('Đ', 'd')
    # 2. Chuẩn hoá Unicode rồi bỏ dấu.
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    # 3. Về chữ thường.
    text = text.lower()
    # 4. Mọi ký tự không phải chữ/số (kể cả / \ : * ? " < > |) thành '-'.
    text = re.sub(r'[^a-z0-9]+', '-', text)
    # 5. Bỏ '-' thừa ở hai đầu.
    return text.strip('-')


def _cung_mot_file(a, b):
    """Windows không phân biệt hoa/thường trong tên file, nên khi chỉ đổi hoa
    thành thường thì os.path.exists() thấy CHÍNH NÓ và tưởng là trùng tên -
    dẫn tới thêm hậu tố -2 hoàn toàn oan. Phải loại trừ trường hợp này."""
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _ten_chua_dung(thu_muc, ten, duoi, bo_qua=None):
    """Tránh ghi đè: đã có file KHÁC trùng tên thì thêm -2, -3..."""
    i = 1
    while True:
        ung_vien = f"{ten}{duoi}" if i == 1 else f"{ten}-{i}{duoi}"
        day_du = os.path.join(thu_muc, ung_vien)
        if not os.path.exists(day_du) or (bo_qua and _cung_mot_file(day_du, bo_qua)):
            return ung_vien
        i += 1


def tim_md_di_kem(pdf_path):
    """Các file .md trong data/output ứng với một file input (theo cấu trúc
    thư mục con và hậu tố _scan/_native/_refined)."""
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    thu_muc = os.path.dirname(os.path.abspath(pdf_path))
    doi = re.sub(r'([\\/])input([\\/]|$)', r'\1output\2', thu_muc)
    ket_qua = []
    for d in {doi, thu_muc}:
        for hau_to in HAU_TO_MD:
            p = os.path.join(d, f"{base}{hau_to}.md")
            if os.path.exists(p):
                ket_qua.append((p, hau_to))
    return ket_qua


def _slug_assets(ten):
    """image_extractor.slugify() dùng cùng quy tắc nhưng GIỮ HOA - phải khớp
    đúng để đổi tên được thư mục ảnh của tài liệu."""
    try:
        sys.path.insert(0, _HERE)
        import image_extractor
        return image_extractor.slugify(ten)
    except Exception:
        return None


def lap_ke_hoach(goc, duoi_loc='all', de_quy=False):
    """Trả về danh sách việc cần làm: [(loai, duong_dan_cu, duong_dan_moi), ...]."""
    if os.path.isfile(goc):
        files = [goc]
    else:
        mau = os.path.join(goc, '**', '*') if de_quy else os.path.join(goc, '*')
        files = [f for f in glob.glob(mau, recursive=de_quy) if os.path.isfile(f)]

    viec = []
    for f in sorted(files):
        ten_file = os.path.basename(f)
        if ten_file.startswith('.') or ten_file == 'rename.log':
            continue
        ten, duoi = os.path.splitext(ten_file)
        if duoi_loc != 'all' and duoi.lower().lstrip('.') != duoi_loc.lower().lstrip('.'):
            continue
        ten_moi = chuan_hoa_ten(ten)
        if not ten_moi or ten_moi + duoi == ten_file:
            continue
        thu_muc = os.path.dirname(f)
        viec.append(('input', f,
                     os.path.join(thu_muc, _ten_chua_dung(thu_muc, ten_moi, duoi, f))))

        # Kéo theo file .md đã xuất và thư mục ảnh, để cặp PDF-Markdown không đứt.
        for md_path, hau_to in tim_md_di_kem(f):
            d_md = os.path.dirname(md_path)
            viec.append(('markdown', md_path,
                         os.path.join(d_md, _ten_chua_dung(d_md, ten_moi + hau_to, '.md', md_path))))
        slug_cu, slug_moi = _slug_assets(ten), _slug_assets(ten_moi)
        if slug_cu and slug_moi and slug_cu != slug_moi:
            for d_out in {re.sub(r'([\\/])input([\\/]|$)', r'\1output\2',
                                 os.path.dirname(os.path.abspath(f)))}:
                cu = os.path.join(d_out, 'assets', slug_cu)
                if os.path.isdir(cu):
                    moi_asset = os.path.join(d_out, 'assets', slug_moi)
                    if not (os.path.exists(moi_asset)
                            and not _cung_mot_file(moi_asset, cu)):
                        viec.append(('assets', cu, moi_asset))
    return viec


def thuc_hien(viec, that=False, log_path=None):
    """Đổi tên theo kế hoạch. that=False thì chỉ in ra, không đụng vào đĩa."""
    xong = 0
    log = None
    if that and log_path:
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            log = open(log_path, 'a', encoding='utf-8')
        except Exception:
            log = None
    try:
        for loai, cu, moi in viec:
            nhan = {'input': 'FILE  ', 'markdown': '  .md ', 'assets': '  ảnh '}[loai]
            print(f"  {nhan} {os.path.basename(cu)}")
            print(f"         -> {os.path.basename(moi)}")
            if not that:
                continue
            try:
                os.rename(cu, moi)
                xong += 1
                if log:
                    dau_thoi_gian = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    log.write(f"[{dau_thoi_gian}] {os.path.relpath(cu, BASE_DIR)} -> "
                              f"{os.path.relpath(moi, BASE_DIR)}\n")
            except Exception as e:  # noqa: BLE001
                print(f"         ❌ không đổi được: {e}")
    finally:
        if log:
            log.close()
    return xong


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    that = '--that' in sys.argv
    de_quy = '--de-quy' in sys.argv or '--r' in sys.argv
    duoi_loc = 'all'
    for i, a in enumerate(sys.argv):
        if a == '--duoi' and i + 1 < len(sys.argv):
            duoi_loc = sys.argv[i + 1]
        elif a.startswith('--duoi='):
            duoi_loc = a.split('=', 1)[1]

    goc = args[0] if args else INPUT_DIR
    if not os.path.exists(goc):
        print(f"❌ Không thấy: {goc}")
        return 2

    viec = lap_ke_hoach(goc, duoi_loc, de_quy)
    if not viec:
        print(f"✅ Mọi tên file trong {os.path.relpath(goc, BASE_DIR)} đã đúng chuẩn, "
              f"không cần đổi.")
        return 0

    so_input = sum(1 for v in viec if v[0] == 'input')
    so_theo = len(viec) - so_input
    print(f"\n{'ĐỔI TÊN THẬT' if that else 'XEM TRƯỚC (chưa đổi gì)'}: "
          f"{so_input} file nguồn"
          + (f", kéo theo {so_theo} file/thư mục kết quả" if so_theo else "") + "\n")
    xong = thuc_hien(viec, that, os.path.join(BASE_DIR, 'data', 'rename.log'))

    if that:
        print(f"\n✅ Đã đổi {xong}/{len(viec)} mục. Nhật ký: data/rename.log")
    else:
        print(f"\nℹ️  Đây mới là xem trước. Thêm --that để đổi thật.")
        print("   Các file .md và thư mục ảnh đã xuất sẽ được đổi tên theo, "
              "nên cặp PDF-Markdown không bị đứt.")
    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
