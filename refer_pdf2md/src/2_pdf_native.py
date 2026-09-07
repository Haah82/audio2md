"""Menu [2]: PDF goc (Digital/Native PDF) sang Markdown - Local, zero token.

Wrapper mong cho pdf_native_core (file src/pdf_native_core.py, ban sao giong
het voi repo SecondBrain_Vault). Toan bo logic trich xuat va hau xu ly nam
trong lo i do, sua mot lan la ca hai repo cung duoc huong.

Cach goi:
    python src/2_pdf_native.py "C:\\duong\\dan\\file.pdf"        1 file
    python src/2_pdf_native.py "a.pdf" "b.pdf" "c.pdf"          nhieu file
    python src/2_pdf_native.py --list "%TEMP%\\danh_sach.txt"    doc danh sach tu file
    python src/2_pdf_native.py ALL                              tat ca PDF trong data/input
Tuy chon:
    --jobs N    so tien trinh song song (mac dinh: tu chon, toi da 4)
    --force     lam lai ca nhung file da co ket qua

Ket qua:  data/output/<ten>_native.md
Nhat ky:  data/output/<ten>_native.fixlog.md
"""
import os
import sys
import glob
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdf_native_core as core

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(BASE_DIR, "data", "input")
# GUI dat PDF2MD_OUTPUT_DIR de giu cau truc thu muc con cua input trong output.
# Khong dat bien nay thi hanh vi CLI cu giu nguyen.
OUTPUT_DIR = os.environ.get("PDF2MD_OUTPUT_DIR") or os.path.join(BASE_DIR, "data", "output")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def out_paths(fpath):
    base = os.path.splitext(os.path.basename(fpath))[0]
    stem = os.path.join(OUTPUT_DIR, base + "_native")
    return stem + ".md", stem + ".fixlog.md"


def convert_one(fpath):
    """Chuyen mot file. Tra ve dict thay vi nem loi, de mot file hong khong
    lam chet ca me chuyen doi khi chay song song."""
    name = os.path.basename(fpath)
    md_path, log_path = out_paths(fpath)
    try:
        if not os.path.exists(fpath):
            return {"ok": False, "name": name, "err": "khong tim thay file"}
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        res = core.convert(fpath)

        with open(md_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(res.markdown)
        if res.fixlog.entries:
            with open(log_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(res.fixlog.to_markdown(name))

        return {"ok": True, "name": name, "stats": res.stats,
                "fixes": len(res.fixlog.entries), "log": bool(res.fixlog.entries)}
    except MemoryError:
        return {"ok": False, "name": name,
                "err": "het bo nho, thu lai voi --jobs 1"}
    except Exception as e:
        return {"ok": False, "name": name, "err": f"{type(e).__name__}: {e}"}


def collect_targets(argv):
    """Gom danh sach file can xu ly tu tham so dong lenh."""
    files, i = [], 0
    while i < len(argv):
        a = argv[i]
        if a == "--list":
            i += 1
            if i >= len(argv):
                print("Loi: --list thieu duong dan file danh sach.")
                return []
            try:
                with open(argv[i], "r", encoding="utf-8-sig", errors="replace") as f:
                    for line in f:
                        line = line.strip().strip('"')
                        if line:
                            files.append(line)
            except OSError as e:
                print(f"Loi: khong doc duoc danh sach {argv[i]}: {e}")
                return []
        elif a.upper() == "ALL":
            files.extend(sorted(glob.glob(os.path.join(INPUT_DIR, "*.pdf"))))
        elif a.startswith("--"):
            if a == "--jobs":
                i += 1                      # bo qua gia tri di kem
        else:
            files.append(a)
        i += 1

    # Bo trung, giu thu tu
    seen, uniq = set(), []
    for f in files:
        key = os.path.abspath(f).lower()
        if key not in seen:
            seen.add(key)
            uniq.append(f)
    return uniq


def main():
    argv = sys.argv[1:]
    force = "--force" in argv

    jobs = 0
    if "--jobs" in argv:
        try:
            jobs = int(argv[argv.index("--jobs") + 1])
        except (IndexError, ValueError):
            print("Canh bao: --jobs khong hop le, dung mac dinh.")

    targets = collect_targets(argv)
    if not targets:
        print("Khong co file PDF nao duoc chon.")
        print('Vi du: python src/2_pdf_native.py "data\\input\\tai-lieu.pdf"')
        return 1

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    todo = []
    for f in targets:
        md_path, _ = out_paths(f)
        if os.path.exists(md_path) and not force:
            print(f"[BO QUA] {os.path.basename(f)} - da co ket qua (dung --force de lam lai)")
            continue
        todo.append(f)

    if not todo:
        print("Khong con file nao can xu ly.")
        return 0

    if jobs <= 0:
        jobs = min(4, max(1, os.cpu_count() or 1), len(todo))
    jobs = max(1, min(jobs, len(todo)))

    engine = "layout" if core._layout_engine_active() else "legacy"
    print(f"[PDF Native] {len(todo)} file | {jobs} tien trinh song song | engine: {engine}")
    t0 = time.time()

    if jobs == 1:
        results = [convert_one(f) for f in todo]
    else:
        results = []
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            futures = {ex.submit(convert_one, f): f for f in todo}
            for fut in as_completed(futures):
                try:
                    results.append(fut.result())
                except Exception as e:
                    results.append({"ok": False,
                                    "name": os.path.basename(futures[fut]),
                                    "err": f"tien trinh con hong: {type(e).__name__}: {e}"})

    ok = fail = 0
    for r in sorted(results, key=lambda x: x["name"].lower()):
        if r["ok"]:
            ok += 1
            s = r["stats"]
            extra = f", {r['fixes']} muc tu sua" if r["fixes"] else ""
            print(f"  [OK]  {r['name']}  ({s['pages']} trang, {s['seconds']}s{extra})")
        else:
            fail += 1
            print(f"  [LOI] {r['name']}: {r['err']}")

    print(f"\nHoan tat: {ok} thanh cong, {fail} loi, tong {time.time()-t0:.1f}s")
    print(f"Ket qua tai: {os.path.relpath(OUTPUT_DIR, BASE_DIR)}")
    if any(r.get("log") for r in results):
        print("Xem them cac file *_native.fixlog.md de ra soat nhung cho script da tu sua.")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
