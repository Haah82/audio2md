"""Doi ten hoi to toan bo data/output/ sang NNN_Ten_raw.md / NNN_Ten_refine.md.

Doc data/input/build-audio2md.md, voi moi dong tinh ten moi bang dung logic
ten_dai_dien()/sanitize_filename() ma main_audio2md.py dung cho file moi
(xem plan-audio2md.md muc IV.2), roi git mv file Raw/Refine hien co sang ten
moi va cap nhat lai 2 wikilink trong dong tuong ung.

Chay voi --dry-run de xem truoc danh sach doi ten ma khong doi gi.
Dong nao wikilink khong khop file nao tren dia (da bi xoa, hoac khong con
wikilink nhu dong da danh dau "Raw da bi xoa") thi bo qua, khong doan ten.
"""
import os
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main_audio2md as m

BASE_DIR = m.BASE_DIR
INPUT_DIR = m.INPUT_DIR
OUTPUT_DIR = m.OUTPUT_DIR
MD_FILE = os.path.join(INPUT_DIR, 'build-audio2md.md')

WIKILINK = re.compile(r'\[\[(.+?)\]\]')


def tach_dong(line):
    parts = line.rstrip('\n').split('|')
    if len(parts) >= 9 and parts[1].strip().isdigit():
        return parts
    return None


def ten_moi_cho_dong(stt, url, title):
    ten = m.ten_dai_dien(url, title)
    return f"{stt:03d}_{m.sanitize_filename(ten)}"


def doi_ten_vat_ly(old_path, new_path, dry_run):
    """Doi ten vat ly bang os.replace(); 'git add -A data/output' chay mot
    lan duy nhat o cuoi main() se ghi nhan het (file da theo doi thanh
    rename, file moi/chua theo doi thanh file moi o ten moi). Tra ve True
    neu da dung ten moi (vua doi, hoac da duoc doi tu lan chay truoc do
    bi dut giua duong) de con cap nhat lai wikilink."""
    if os.path.abspath(old_path) == os.path.abspath(new_path):
        return False
    if os.path.exists(new_path):
        # Co the da doi roi tu lan chay truoc (vd script bi dut giua duong);
        # khong doi lai nhung van bao de cap nhat wikilink cho khop.
        return True
    if not os.path.exists(old_path):
        print(f"[WARN] Khong thay file de doi: {os.path.basename(old_path)}")
        return False
    print(f"{'[DRY-RUN] ' if dry_run else ''}{os.path.basename(old_path)} -> {os.path.basename(new_path)}")
    if not dry_run:
        os.replace(old_path, new_path)
    return True


def main():
    dry_run = '--dry-run' in sys.argv

    with open(MD_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    doi = 0
    bo_qua = 0
    for i, line in enumerate(lines):
        parts = tach_dong(line)
        if not parts:
            continue
        stt = int(parts[1].strip())
        url = parts[2].strip()
        title = parts[3].strip()
        ten_moi = ten_moi_cho_dong(stt, url, title)

        doi_dong = False
        for col, hau_to in ((5, '_raw'), (6, '_refine')):
            khop = WIKILINK.search(parts[col])
            if not khop:
                continue
            ten_cu = khop.group(1)
            ten_moi_day_du = f"{ten_moi}{hau_to}"
            if ten_cu == ten_moi_day_du:
                continue
            old_path = os.path.join(OUTPUT_DIR, f"{ten_cu}.md")
            new_path = os.path.join(OUTPUT_DIR, f"{ten_moi_day_du}.md")
            if doi_ten_vat_ly(old_path, new_path, dry_run):
                parts[col] = f" [[{ten_moi_day_du}]] "
                doi_dong = True
                doi += 1
            else:
                bo_qua += 1

        if doi_dong:
            lines[i] = "|".join(parts) + "\n"

    if not dry_run and doi:
        with open(MD_FILE, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        subprocess.run(['git', 'add', '-A', '--', OUTPUT_DIR], check=True, cwd=BASE_DIR)

    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Da doi {doi} file, bo qua {bo_qua}.")


if __name__ == '__main__':
    main()
