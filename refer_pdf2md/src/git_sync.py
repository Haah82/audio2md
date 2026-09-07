"""Dong bo Git an toan cho pdf2md.

Thay cho phan logic git viet bang batch trong git-push.bat. Ly do thay:

- Batch khong kiem tra ma loi tra ve, nen ban cu in "[OK] thanh cong!" ngay ca
  khi git commit hoac git push that bai. Bao thanh cong gia la loi nguy hiem
  nhat vi nguoi dung tuong da sao luu xong trong khi thuc te chua co gi tren
  GitHub.
- Batch goi 'git stash' roi 'git stash pop' vo dieu kien. Khi khong co thay doi
  nao, stash khong tao gi ca, con 'stash pop' se lay ra mot stash CU khong lien
  quan va tron vao cay lam viec.
- Truyen noi dung commit qua bien batch co dau '!' hoac '%' se bi nuot ky tu.
  Ban nay goi git bang danh sach tham so, khong qua shell, nen giu nguyen van.

Chay:
    python src/git_sync.py status          xem trang thai
    python src/git_sync.py pull            keo ve an toan
    python src/git_sync.py push            commit va push
    python src/git_sync.py push -m "..."   kem noi dung commit
    python src/git_sync.py sync            keo ve roi day len, mot luot
    python src/git_sync.py sync -y         khong hoi xac nhan
"""
import datetime
import os
import re
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def git(*args):
    """Goi git bang danh sach tham so, khong qua shell.

    Tra ve (thanh_cong, stdout, stderr). Khong dung shell=True de noi dung
    commit chua ky tu dac biet khong bi shell dien giai.
    """
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=BASE_DIR)
    except FileNotFoundError:
        return False, "", "Khong tim thay lenh 'git'. Cai Git for Windows truoc."
    return r.returncode == 0, (r.stdout or "").strip(), (r.stderr or "").strip()


# ------------------------------------------------------------- KIEM TRA NEN

def preflight():
    """Kiem tra tuan tu cac dieu kien can. Tra ve ten nhanh, hoac None neu hong."""
    ok, _, _ = git("rev-parse", "--is-inside-work-tree")
    if not ok:
        print("[X] Day chua phai repository Git. Chay: git init")
        return None

    ok, remote, _ = git("remote")
    if not remote:
        print("[X] Chua khai bao remote. Chay: git remote add origin <url>")
        return None

    _, uname, _ = git("config", "user.name")
    _, email, _ = git("config", "user.email")
    if not uname or not email:
        print("[X] Chua cau hinh danh tinh Git. Chay 2 lenh sau roi thu lai:")
        print('    git config --global user.name "Ten cua ban"')
        print('    git config --global user.email "email@cua.ban"')
        return None

    ok, branch, _ = git("rev-parse", "--abbrev-ref", "HEAD")
    if not ok or not branch or branch == "HEAD":
        print("[X] Khong xac dinh duoc nhanh hien tai (co the dang o detached HEAD).")
        return None
    return branch


# --------------------------------------------------------- QUET BI MAT

# Ten file khong bao gio duoc phep len GitHub.
_SECRET_NAMES = re.compile(
    r"(^|/)(\.env(\..*)?|.*\.pem|.*\.key|.*credentials.*\.json|.*token.*\.json)$",
    re.IGNORECASE,
)

# Dau van cua khoa that. Chi bao dong, khong in ra gia tri khoa.
_SECRET_CONTENT = [
    ("Anthropic API key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI API key", re.compile(r"\bsk-[A-Za-z0-9]{32,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}")),
    ("GitHub token", re.compile(r"\b(ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})")),
    ("Telegram bot token", re.compile(r"\b\d{8,12}:AA[A-Za-z0-9_\-]{30,}")),
]

_TEXT_EXT = {".py", ".bat", ".sh", ".md", ".txt", ".json", ".yml", ".yaml",
             ".ini", ".cfg", ".toml", ".env", ".ps1", ".js", ".ts"}


def scan_staged_for_secrets():
    """Quet nhung gi SAP duoc commit. Tra ve danh sach canh bao.

    Quet o vung staged chu khong quet ca thu muc, vi dung cai sap len GitHub
    moi la cai can chan.
    """
    ok, out, _ = git("diff", "--cached", "--name-only")
    if not ok or not out:
        return []

    warnings = []
    for rel in out.splitlines():
        rel = rel.strip().strip('"')
        if not rel:
            continue

        if _SECRET_NAMES.search(rel):
            warnings.append(f"ten file nhay cam: {rel}")
            continue

        ext = os.path.splitext(rel)[1].lower()
        if ext and ext not in _TEXT_EXT:
            continue

        path = os.path.join(BASE_DIR, rel)
        try:
            if os.path.getsize(path) > 2_000_000:
                continue
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            continue

        for label, pat in _SECRET_CONTENT:
            if pat.search(content):
                warnings.append(f"nghi co {label} trong: {rel}")
                break
    return warnings


# ------------------------------------------------------------------ LENH

def cmd_status():
    branch = preflight()
    if not branch:
        return 1
    print(f"Nhanh hien tai: {branch}")
    _, out, _ = git("status", "--short")
    print(out if out else "Cay lam viec sach, khong co thay doi.")
    ok, ahead, _ = git("rev-list", "--count", f"origin/{branch}..{branch}")
    if ok and ahead and ahead != "0":
        print(f"Dang co {ahead} commit chua push len GitHub.")
    return 0


def cmd_pull():
    branch = preflight()
    if not branch:
        return 1

    _, dirty, _ = git("status", "--porcelain")
    has_local = bool(dirty.strip())

    stashed = False
    if has_local:
        print("[+] Cat tam thay doi dang lam do (git stash)...")
        ok, out, err = git("stash", "push", "-u", "-m", "git_sync-tam")
        if not ok:
            print(f"[X] Khong stash duoc, dung lai de tranh mat du lieu: {err or out}")
            return 1
        stashed = "No local changes" not in out
    else:
        print("[+] Khong co thay doi local, bo qua buoc stash.")

    print(f"[+] Keo code moi nhat (git pull --rebase origin {branch})...")
    ok, out, err = git("pull", "--rebase", "origin", branch)
    if not ok:
        print(f"[X] Pull that bai: {err or out}")
        if stashed:
            print("    Thay doi cua ban van con trong stash. Xem bang: git stash list")
            print("    Lay lai bang: git stash pop")
        return 1
    print(out or "Da cap nhat.")

    # Chi pop khi chinh lan chay nay da stash. Day la cho ban batch cu lam sai:
    # pop vo dieu kien co the lay nham mot stash cu khong lien quan.
    if stashed:
        print("[+] Khoi phuc thay doi cua ban (git stash pop)...")
        ok, out, err = git("stash", "pop")
        if not ok:
            print(f"[X] Xung dot khi khoi phuc: {err or out}")
            print("    Giai quyet xung dot thu cong roi chay lai.")
            return 1
    print("[OK] Pull xong.")
    return 0


def cmd_push(message=None, assume_yes=False):
    branch = preflight()
    if not branch:
        return 1

    _, dirty, _ = git("status", "--porcelain")
    if not dirty.strip():
        ok, ahead, _ = git("rev-list", "--count", f"origin/{branch}..{branch}")
        if ok and ahead and ahead != "0":
            print(f"Khong co thay doi moi, nhung con {ahead} commit chua push. Dang push...")
            ok, _, err = git("push", "origin", branch)
            print("[OK] Push xong." if ok else f"[X] Push that bai: {err}")
            return 0 if ok else 1
        print("Khong co gi de commit hay push. Cay lam viec da sach.")
        return 0

    ok, _, err = git("add", "-A")
    if not ok:
        print(f"[X] git add that bai: {err}")
        return 1

    # Quet bi mat SAU khi add, TRUOC khi commit.
    warnings = scan_staged_for_secrets()
    if warnings:
        print("\n[!] CANH BAO BAO MAT - dung lai truoc khi commit:")
        for w in warnings:
            print(f"    - {w}")
        print("\n    Go khoi vung staged bang: git restore --staged <file>")
        print("    Va them file do vao .gitignore truoc khi thu lai.")
        git("reset")
        print("    Da huy staged de ban xu ly. Khong commit gi ca.")
        return 1

    _, staged, _ = git("diff", "--cached", "--stat")
    print("\nNhung thay doi sap duoc commit:")
    print(staged or "(khong co)")

    if not assume_yes:
        try:
            ans = input("\nXac nhan commit va push? (Y/N): ").strip().lower()
        except EOFError:
            ans = "n"
        if ans != "y":
            git("reset")
            print("Da huy. Khong commit gi ca.")
            return 0

    if not message:
        message = "Update: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ok, out, err = git("commit", "-m", message)
    if not ok:
        blob = (out + err).lower()
        if "nothing to commit" in blob or "no changes added" in blob:
            print("Khong co thay doi moi de commit.")
            return 0
        print(f"[X] Commit that bai: {out or err}")
        return 1
    print(f"[+] Da commit: {message}")

    ok, out, err = git("push", "origin", branch)
    if not ok:
        print(f"[X] Push that bai: {err or out}")
        print("    Commit da duoc luu o may. Chay lai lenh push sau khi xu ly xong.")
        return 1
    print("[OK] Da push len GitHub thanh cong.")
    return 0


def cmd_sync(message=None, assume_yes=False):
    """Dong bo hai chieu mot luot: keo ve truoc, roi day len.

    Keo ve TRUOC khi day la co y: neu tren GitHub co thay doi moi ma minh chua
    co, push thang se bi tu choi. Keo ve truoc thi lan push sau gan nhu luon
    thanh cong.
    """
    print("=" * 55)
    print("  BUOC 1/2: KEO VE TU GITHUB")
    print("=" * 55)
    rc = cmd_pull()
    if rc != 0:
        print("\n[X] Dung lai o buoc keo ve, chua day gi len.")
        print("    Xu ly xong van de tren roi chay lai.")
        return rc

    print()
    print("=" * 55)
    print("  BUOC 2/2: COMMIT VA DAY LEN GITHUB")
    print("=" * 55)
    return cmd_push(message, assume_yes)


def main():
    argv = sys.argv[1:]
    action = argv[0].lower() if argv else "status"

    message = None
    if "-m" in argv:
        try:
            message = argv[argv.index("-m") + 1]
        except IndexError:
            print("[X] Thieu noi dung sau -m")
            return 1
    assume_yes = "-y" in argv

    if action == "status":
        return cmd_status()
    if action == "pull":
        return cmd_pull()
    if action == "push":
        return cmd_push(message, assume_yes)
    if action == "sync":
        return cmd_sync(message, assume_yes)

    print(f"Lenh khong hop le: {action}")
    print('Dung: python src/git_sync.py [status|pull|push|sync] [-m "ghi chu"] [-y]')
    return 1


if __name__ == "__main__":
    sys.exit(main())
