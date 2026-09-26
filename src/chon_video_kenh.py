"""Chon video tu mot link kenh/playlist YouTube cho Menu 4 > O.

Batch goi:  python src/chon_video_kenh.py "<link>" "<file_ket_qua>"

Ma thoat:
    0 - da ghi it nhat mot link vao file ket qua
    1 - loi mang, kenh rong, hoac moi video deu da co trong danh sach
    2 - nguoi dung chon quay lai
"""
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yt_dlp

from main_audio2md import INPUT_DIR, canonical_url

MOI_TRANG = 20

# Cac dang path duoc coi la kenh hoac playlist chu khong phai video don le.
MAU_KENH = (
    re.compile(r'^/@[^/]+(/(videos|streams|shorts|playlists))?/?$'),
    re.compile(r'^/channel/[^/]+(/(videos|streams|shorts|playlists))?/?$'),
    re.compile(r'^/(c|user)/[^/]+(/(videos|streams|shorts|playlists))?/?$'),
    re.compile(r'^/playlist/?$'),
)


def la_link_kenh(url):
    parsed = urllib.parse.urlsplit(url.strip())
    host = parsed.netloc.lower().removeprefix('www.')
    if host not in ('youtube.com', 'm.youtube.com'):
        return False
    # `/watch?v=X&list=Y` la link mot video dang xem trong playlist: nguoi dung
    # dan link do thi muon dung video ay, khong phai ca playlist.
    if parsed.path.rstrip('/') != '/watch' and 'list' in urllib.parse.parse_qs(parsed.query):
        return True
    return any(mau.match(parsed.path) for mau in MAU_KENH)


def chuan_hoa_kenh(url):
    """`/@handle` tran tro ve trang gioi thieu; them /videos de lay tab video."""
    parsed = urllib.parse.urlsplit(url.strip())
    if 'list' in urllib.parse.parse_qs(parsed.query):
        return url.strip()
    path = parsed.path.rstrip('/')
    if re.match(r'^/(@[^/]+|channel/[^/]+|(c|user)/[^/]+)$', path):
        path += '/videos'
    return urllib.parse.urlunsplit((parsed.scheme or 'https', parsed.netloc,
                                    path, parsed.query, ''))


def lay_danh_sach(url):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ie = ydl.extract_info(chuan_hoa_kenh(url), download=False)

    videos = []
    for muc in (ie.get('entries') or []):
        if not muc:
            continue
        link = muc.get('url') or f"https://www.youtube.com/watch?v={muc.get('id')}"
        videos.append({
            'url': link,
            'title': muc.get('title') or muc.get('id') or 'Khong ro tieu de',
            'duration': muc.get('duration') or 0,
        })
    return ie.get('title') or 'Kenh YouTube', videos


def link_da_co():
    """Tap khoa cac link da nam trong build-audio2md.md."""
    md_file = os.path.join(INPUT_DIR, 'build-audio2md.md')
    khoa = set()
    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.rstrip('\n').split('|')
                if len(parts) >= 9 and parts[1].strip().isdigit():
                    khoa.add(canonical_url(parts[2].strip()))
    except OSError:
        pass
    return khoa


def dinh_dang_thoi_luong(giay):
    if not giay:
        return "  --  "
    return f"{int(giay) // 60:3d}:{int(giay) % 60:02d}"


def phan_tich_lua_chon(chuoi, tong):
    """Doc cu phap '1', '1,3,5', '2-4' - giong quy uoc cua Menu 4."""
    chon = set()
    for phan in chuoi.replace(';', ',').replace(' ', ',').split(','):
        phan = phan.strip()
        if not phan:
            continue
        if '-' in phan:
            dau, _, cuoi = phan.partition('-')
            if not (dau.strip().isdigit() and cuoi.strip().isdigit()):
                return None
            a, b = int(dau), int(cuoi)
            if a > b:
                a, b = b, a
            chon.update(range(a, b + 1))
        elif phan.isdigit():
            chon.add(int(phan))
        else:
            return None
    chon = {i for i in chon if 1 <= i <= tong}
    return sorted(chon) or None


def in_trang(ten_kenh, videos, trang, so_trang):
    dau = trang * MOI_TRANG
    cuoi = min(dau + MOI_TRANG, len(videos))
    print()
    print(f"=== {ten_kenh} | {len(videos)} video | Trang {trang + 1}/{so_trang} ===")
    for i in range(dau, cuoi):
        v = videos[i]
        print(f"  [{i + 1:2d}] {dinh_dang_thoi_luong(v['duration'])}  {v['title'][:70]}")
    print("-" * 55)
    print(" Go so de chon (VD: 1 hoac 1,3,5 hoac 2-4)")
    if so_trang > 1:
        print(" [N] Trang sau   [P] Trang truoc")
    print(f" [A] Chon toan bo {len(videos)} video")
    print(" [0] Quay lai")


def xac_nhan_tat_ca(so_video):
    print()
    print(f"[?] Se xu ly {so_video} video, uoc tinh {so_video}-{so_video * 2} "
          "luot goi Gemini.")
    return input("    Tiep tuc (Y/N)? ").strip().lower() == 'y'


def chon_video(ten_kenh, videos):
    """Tra ve danh sach link da chon, hoac None khi nguoi dung quay lai."""
    so_trang = max(1, (len(videos) + MOI_TRANG - 1) // MOI_TRANG)
    trang = 0
    while True:
        in_trang(ten_kenh, videos, trang, so_trang)
        tra_loi = input(" Lua chon cua ban: ").strip()

        if not tra_loi or tra_loi == '0':
            return None
        if tra_loi.lower() == 'n':
            trang = min(trang + 1, so_trang - 1)
            continue
        if tra_loi.lower() == 'p':
            trang = max(trang - 1, 0)
            continue
        if tra_loi.lower() == 'a':
            if xac_nhan_tat_ca(len(videos)):
                return [v['url'] for v in videos]
            print("[-] Da huy.")
            continue

        chon = phan_tich_lua_chon(tra_loi, len(videos))
        if not chon:
            print("[X] Lua chon khong hop le.")
            continue
        return [videos[i - 1]['url'] for i in chon]


def ghi_ket_qua(duong_dan, links):
    with open(duong_dan, 'w', encoding='utf-8') as f:
        for link in links:
            f.write(link + '\n')


def tach_link(chuoi):
    """Tach link theo dau phay/cham phay, giu thu tu va bo link trung."""
    ket_qua = []
    da_thay = set()
    for muc in re.split(r'[,;]', chuoi):
        link = muc.strip()
        if not link:
            continue
        parsed = urllib.parse.urlsplit(link)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise ValueError(f'Link khong hop le: {link[:100]}')
        khoa = canonical_url(link)
        if khoa not in da_thay:
            ket_qua.append(link)
            da_thay.add(khoa)
    return ket_qua


def main():
    if len(sys.argv) < 3:
        print("[X] Thieu tham so: <link> <file_ket_qua>")
        return 1

    try:
        links_nhap = tach_link(sys.argv[1])
    except ValueError as e:
        print(f'[X] {e}')
        return 1
    if not links_nhap:
        print('[X] Chua nhap link hop le.')
        return 1
    file_ket_qua = sys.argv[2]
    ket_qua = []
    da_thay = set()
    da_co = link_da_co()
    for link in links_nhap:
        if not la_link_kenh(link):
            chon = [link]
        else:
            print(f"[INFO] Dang lay danh sach video cua kenh: {link}")
            try:
                ten_kenh, videos = lay_danh_sach(link)
            except Exception as e:
                print(f"[X] Khong lay duoc danh sach kenh: {str(e).splitlines()[0][:160]}")
                return 1
            if not videos:
                print('[X] Kenh khong co video nao.')
                return 1
            tong = len(videos)
            videos = [v for v in videos if canonical_url(v['url']) not in da_co]
            print(f'[INFO] Kenh co {tong} video | bo qua {tong - len(videos)} da co | con {len(videos)} video')
            if not videos:
                continue
            chon = chon_video(ten_kenh, videos)
            if not chon:
                return 2
        for video_url in chon:
            khoa = canonical_url(video_url)
            if khoa not in da_thay:
                ket_qua.append(video_url)
                da_thay.add(khoa)
    if not ket_qua:
        print('[X] Khong co link moi de xu ly.')
        return 1
    ghi_ket_qua(file_ket_qua, ket_qua)
    print(f'[+] Da chon {len(ket_qua)} link; se xu ly lan luot.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
