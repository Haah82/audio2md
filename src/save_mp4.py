"""Tải tuần tự danh sách URL thành MP4 mà không gọi Gemini hay ghi Markdown."""
import argparse
import os
import re
import sys
from pathlib import Path

import yt_dlp

import main_audio2md as pipeline


def safe_custom_name(value):
    """Return a Windows-safe base name, without a user-supplied .mp4 suffix."""
    raw_name = value.strip()
    # ``splitext('.mp4')`` treats the whole string as a basename, so remove
    # the requested output suffix explicitly before sanitizing.
    name = raw_name[:-4] if raw_name.lower().endswith('.mp4') else raw_name
    name = re.sub(r'[\\/*?:"<>|]', '_', name)
    name = ' '.join(name.split()).rstrip('.')
    if not name:
        raise ValueError('Ten file khong duoc de trong.')
    # A filename must fit independently of its selected parent directory.
    # Count UTF-16 code units, the unit Windows uses for its filename limit.
    while len(name.encode('utf-16-le')) // 2 > 120:
        name = name[:-1]
    return name


def custom_name(url, used, output_dir):
    while True:
        entered = input(f'\nTen MP4 cho link sau (Enter = ten mac dinh):\n{url}\n> ')
        if not entered.strip():
            return None
        try:
            name = safe_custom_name(entered)
        except ValueError as error:
            print(f'[X] {error}')
            continue
        if name.lower() in used or (output_dir / f'{name}.mp4').exists():
            print('[X] Ten nay da duoc dung trong danh sach hoac da ton tai. Hay nhap ten khac.')
            continue
        used.add(name.lower())
        return name


def options(output_dir, max_height, name=None):
    # Precision in the template is applied before yt-dlp creates its `.part`
    # files. `trim_file_name` is applied too late/inconsistently for some
    # Facebook reel download paths.
    stem = f'{name}.%(ext)s' if name else '%(title).120B.%(ext)s'
    return {
        'format': pipeline.mp4_format(max_height),
        'merge_output_format': 'mp4',
        'outtmpl': str(output_dir / stem),
        'noplaylist': True,
        'nooverwrites': True,
        # Facebook captions can be several hundred characters long. Windows
        # compatibility protects invalid punctuation; the bounded template
        # above prevents a path-too-long `.mp4.part` filename.
        'windowsfilenames': True,
        'retries': 10,
        'fragment_retries': 10,
        'extractor_retries': 5,
    }


def download_one(url, output_dir, max_height, name=None, emit=print):
    """Download one URL, retaining the active YouTube client fallback policy."""
    base = options(output_dir, max_height, name)
    clients = pipeline.danh_sach_client(url)
    for client in clients:
        if len(clients) > 1:
            emit(f'[INFO] Thu client: {client}')
        try:
            with yt_dlp.YoutubeDL(pipeline.opts_theo_client(base, client)) as ydl:
                code = ydl.download([url])
            if code:
                raise RuntimeError(f'yt-dlp ket thuc voi ma {code}')
            emit(f'[SUCCESS] Da luu MP4 vao: {output_dir}')
            return True
        except Exception as error:
            emit(f"[WARN] Tai MP4 loi voi client '{client}': {str(error).splitlines()[0][:160]}")
            if pipeline.loi_vinh_vien(error):
                break
    emit('[ERROR] Khong the tai MP4 cho link nay.')
    return False


def read_urls(list_file):
    with open(list_file, encoding='utf-8') as source:
        return [line.strip() for line in source if line.strip()]


def main(argv=None):
    parser = argparse.ArgumentParser(description='Save a list of online videos as MP4.')
    parser.add_argument('list_file')
    parser.add_argument('output_dir')
    parser.add_argument('max_height', choices=('720', '1080'))
    parser.add_argument('--custom-names', action='store_true')
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    urls = read_urls(args.list_file)
    if not urls:
        print('[X] Danh sach link trong.')
        return 1

    print(f'[INFO] Luu {len(urls)} link vao: {output_dir}')
    print(f'[INFO] Chat luong toi da: {args.max_height}p (khong tai ma hoa lai).')
    used_names = set()
    success = 0
    for index, url in enumerate(urls, start=1):
        print(f'\n=== [{index}/{len(urls)}] {url} ===')
        name = custom_name(url, used_names, output_dir) if args.custom_names else None
        success += download_one(url, output_dir, args.max_height, name)
    print(f'\n[SUMMARY] Thanh cong: {success}/{len(urls)} | Thu muc: {output_dir}')
    return 0 if success == len(urls) else 1


if __name__ == '__main__':
    sys.exit(main())
