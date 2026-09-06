import os
import sys
import time
import urllib.parse
import re
import glob
import yt_dlp
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(BASE_DIR, 'data', 'input')
OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'output')

# Nap .env TRUOC khi import pool: pool doc cau hinh ngay luc khoi tao.
load_dotenv(os.path.join(BASE_DIR, '.env'))

from gemini_pool import GeminiPool

FORCE_OVERWRITE = os.environ.get("FORCE_OVERWRITE", "0") == "1"

def is_url(string):
    try:
        result = urllib.parse.urlparse(string)
        return all([result.scheme, result.netloc])
    except:
        return False

def sanitize_filename(name):
    # Cắt bỏ phần sau dấu '|' (tên kênh) hoặc '#' (hashtag) để tên file ngắn gọn
    name = re.split(r'[|#]', name)[0].strip()
    clean_name = re.sub(r'[\\/*?:"<>|]', "_", name)
    return " ".join(clean_name.split())[:150]

def clean_subtitle(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        text_blocks = []
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith("WEBVTT") or line.startswith("Language:") or line.startswith("Kind:"):
                continue
            if "-->" in line:
                continue
            
            if i + 1 < len(lines) and "-->" in lines[i+1]:
                continue
                
            clean_line = re.sub(r'<[^>]+>', '', line)
            if clean_line:
                text_blocks.append(clean_line)
        
        dedup_text = []
        for t in text_blocks:
            if not dedup_text or t not in dedup_text[-1]:
                dedup_text.append(t)
        
        raw_full = " ".join(dedup_text)
        raw_full = re.sub(r'(?<=[.!?])\s+', '\n\n', raw_full)
        return raw_full
    except Exception as e:
        print(f"[WARN] Loi doc phu de: {e}")
        return None

def update_md_table(item_url, title, raw_file_name, refine_file_name):
    md_file = os.path.join(INPUT_DIR, 'build-audio2md.md')
    if not os.path.exists(md_file): 
        return
        
    # Thay the dau | thanh dau - de chong vo bang Markdown
    safe_title = title.replace('|', '-')
    
    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines):
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 7:
                    saved_link = parts[2].strip()
                    if saved_link == item_url:
                        parts[3] = f" {safe_title} "
                        parts[5] = f" [[{raw_file_name}]] "
                        # De trong khi chua co file: wikilink hong se bi Obsidian
                        # bien thanh file rong ngay khi co nguoi bam vao.
                        o_refine = f"[[{refine_file_name}]]" if refine_file_name else ""
                        
                        last_part = parts[6].rstrip()
                        if last_part.endswith('\n'):
                            parts[6] = f" {o_refine} \n"
                        else:
                            if len(parts) > 7:
                                parts[6] = f" {o_refine} "
                            else:
                                parts[6] = f" {o_refine} |\n"
                        lines[i] = "|".join(parts)
                        
        with open(md_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    except Exception as e:
        print(f"[WARN] Khong the cap nhat file md danh sach: {e}")

def xoa_dong_md(item_url):
    """Xoa dong cua link hong khoi bang va danh so lai STT.

    Bat buoc phai danh so lai: build-audio2md.bat dung chinh gia tri STT lam
    chi so mang (link[!raw_stt!]) va dem count theo so dong, nen de hong so
    thu tu se lam lech toan bo danh sach o cac lan chay sau.
    """
    md_file = os.path.join(INPUT_DIR, 'build-audio2md.md')
    if not os.path.exists(md_file):
        return
    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        giu = []
        da_xoa = False
        for line in lines:
            parts = line.split('|')
            if len(parts) >= 7 and parts[2].strip() == item_url and not da_xoa:
                da_xoa = True
                continue
            giu.append(line)

        if not da_xoa:
            return

        # Danh so lai: bang xep moi nhat len dau nen STT giam dan tu tren xuong.
        vi_tri_du_lieu = []
        for i, line in enumerate(giu):
            parts = line.split('|')
            if len(parts) >= 7 and parts[1].strip() not in ('STT', '---', ''):
                vi_tri_du_lieu.append(i)

        tong = len(vi_tri_du_lieu)
        for thu_tu, i in enumerate(vi_tri_du_lieu):
            parts = giu[i].split('|')
            parts[1] = f" {tong - thu_tu} ".ljust(len(parts[1]))
            giu[i] = "|".join(parts)

        with open(md_file, 'w', encoding='utf-8') as f:
            f.writelines(giu)
        print(f"[DON DEP] Da go link hong khoi build-audio2md.md va danh so lai {tong} dong.")
    except Exception as e:
        print(f"[WARN] Khong the go dong khoi file md danh sach: {e}")

def download_media(link):
    print(f"\n[INFO] Dang ket noi toi URL: {link}")
    ydl_opts = {
        'ffmpeg_location': r'C:\FFmpeg\bin' if __import__('os').path.exists(r'C:\FFmpeg\bin\ffmpeg.exe') else (__import__('os').path.join(__import__('os').environ.get('USERPROFILE', ''), 'FFmpeg', 'bin') if __import__('os').path.exists(__import__('os').path.join(__import__('os').environ.get('USERPROFILE', ''), 'FFmpeg', 'bin', 'ffmpeg.exe')) else None),
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(INPUT_DIR, '%(id)s.%(ext)s'),
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['vi', 'en'],
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': False,
        'no_warnings': True,
        'restrictfilenames': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            title = sanitize_filename(info.get('title', 'Unknown_Title'))
            video_id = info.get('id', 'unknown')
            
            sub_files = glob.glob(os.path.join(INPUT_DIR, f"{video_id}*.vtt")) + \
                        glob.glob(os.path.join(INPUT_DIR, f"{video_id}*.srt"))
            
            raw_text = None
            if sub_files:
                print(f"[SUCCESS] Da tim thay phu de tu yt-dlp: {os.path.basename(sub_files[0])}")
                raw_text = clean_subtitle(sub_files[0])
                
                for sf in sub_files:
                    try: os.remove(sf)
                    except: pass
            
            filename = ydl.prepare_filename(info)
            base_ext = os.path.splitext(filename)[0]
            mp3_file = base_ext + '.mp3'
            
            if raw_text:
                print(f"[SUCCESS] Trich xuat nguyen tac thanh cong (Bo qua xu ly Audio).")
                if os.path.exists(mp3_file):
                    os.remove(mp3_file)
                return raw_text, None, title
            else:
                print(f"[INFO] Khong co phu de, da tai am thanh: {os.path.basename(mp3_file)}")
                return None, mp3_file, title
                
    except Exception as e:
        print(f"[WARN] Loi yt-dlp: {e}")
        print("[INFO] Dang thu lai (Chi tai am thanh)...")
        
        ydl_opts['writesubtitles'] = False
        ydl_opts['writeautomaticsub'] = False
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=True)
                title = sanitize_filename(info.get('title', 'Unknown_Title'))
                filename = ydl.prepare_filename(info)
                base_ext = os.path.splitext(filename)[0]
                mp3_file = base_ext + '.mp3'
                
                print(f"[SUCCESS] Da tai am thanh: {os.path.basename(mp3_file)}")
                return None, mp3_file, title
        except Exception as e2:
            print(f"[ERROR] Loi yt-dlp: {e2}")
            return None, None, None

def doc_raw_da_co(raw_md_path):
    """Doc lai ban Raw da luu (bo dong Reference dau file) de khoi boc bang lai."""
    if not os.path.exists(raw_md_path):
        return None
    try:
        with open(raw_md_path, 'r', encoding='utf-8') as f:
            noi_dung = f.read()
    except Exception:
        return None
    noi_dung = re.sub(r'^>[^\n]*Reference:.*?\n', '', noi_dung, count=1).strip()
    return noi_dung or None

def transcribe_raw(pool, file_path, title):
    prompt = """Bạn là chuyên gia bóc băng (transcribe) chuyên nghiệp. Hãy chuyển đổi toàn bộ lời thoại trong file này thành văn bản.
Yêu cầu BẮT BUỘC:
1. GIỮ NGUYÊN 100% NGÔN NGỮ GỐC của audio/video. Tuyệt đối không dịch thuật.
2. Chia thành các đoạn văn (paragraphs) ngắn gọn, hợp lý để dễ đọc trên ứng dụng Obsidian.
3. Không tóm tắt, không lược bỏ, không thêm thắt bất kỳ bình luận nào.
Trả về duy nhất nội dung thô."""

    def boc_bang(client, model):
        # File da upload chi thuoc ve dung key da upload no -> doi key la upload lai.
        print(f"[PROCESSING] Dang Upload '{os.path.basename(file_path)}'...", end="", flush=True)
        uploaded_file = client.files.upload(file=file_path)
        while uploaded_file.state.name == "PROCESSING":
            print(".", end="", flush=True)
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)
        print()
        try:
            response = client.models.generate_content(
                model=model, contents=[uploaded_file, prompt])
            return response.text.strip() if response.text else None
        finally:
            try: client.files.delete(name=uploaded_file.name)
            except Exception: pass

    return pool.chay(boc_bang, f"Boc bang '{title}'")

def refine_content(pool, raw_text, original_title, file_title, reference_str, item_overwrite=False):
    refine_md_path = os.path.join(OUTPUT_DIR, f"{file_title}_refine.md")
    
    if not item_overwrite and os.path.exists(refine_md_path):
        print(f"[SKIP] Da ton tai ban Refine: {refine_md_path}")
        return True
        
    prompt = f"""Bạn là biên tập viên chuyên nghiệp. Dựa vào bản Transcript dưới đây, hãy tinh luyện và chắt lọc nội dung cốt lõi. 
BẮT BUỘC trả về nội dung gồm 2 phần: PHẦN 1 (Tiếng Việt) và PHẦN 2 (Tiếng Anh). Trình bày theo đúng định dạng Markdown sau (không thay đổi cấu trúc):

# [Viết một Tiêu đề Tiếng Việt thật hấp dẫn]

## 1. Tóm tắt 3 câu
(Viết đúng 3 câu tóm tắt toàn bộ bối cảnh và ý chính)

## 2. Bài học cốt lõi
(Dùng bullet points để liệt kê các kiến thức, giá trị hoặc bài học hay nhất)

## 3. Trích dẫn hay nhất
(Trích nguyên văn 1-3 câu nói truyền cảm hứng hoặc đắt giá nhất từ nội dung)

---

# [English Title]

## 1. 3-Sentence Summary
(Translate the 3-sentence summary into English)

## 2. Core Lessons
(Translate the core lessons into English)

## 3. Best Quotes
(Translate the best quotes into English)

LƯU Ý QUAN TRỌNG: 
- Bỏ qua các đoạn dạo đầu, chào hỏi, quảng cáo, kêu gọi like/share.
- Tuyệt đối KHÔNG tự ý sáng tạo hay ảo tưởng thêm thông tin ngoài transcript.

Nội dung Transcript:
{raw_text}
"""
    
    def tinh_luyen(client, model):
        response = client.models.generate_content(model=model, contents=prompt)
        return response.text.strip() if response.text else None

    refined_text = pool.chay(tinh_luyen, f"Refine '{file_title}'")
    if refined_text:
        final_output = f"{refined_text}\n\n---\n**Reference:** {reference_str}"
        with open(refine_md_path, 'w', encoding='utf-8') as f:
            f.write(final_output)
        print(f"[SUCCESS] Da luu ban Refine song ngu: {file_title}_refine.md")
        return True

    print(f"[WARN] Khong tao duoc ban Refine cho '{file_title}'.")
    return False

def main():
    if len(sys.argv) < 2:
        print("[ERROR] Thieu file danh sach input.")
        return
        
    temp_list_path = sys.argv[1]
    if not os.path.exists(temp_list_path):
        return
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
    try:
        pool = GeminiPool()
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    
    with open(temp_list_path, 'r', encoding='utf-8') as f:
        items = [line.strip() for line in f.readlines() if line.strip()]
        
    for item in items:
        raw_text = None
        target_audio = None
        file_title = "Unknown"
        original_title = "Unknown"
        is_temp = False
        reference_str = "" 
        item_overwrite = FORCE_OVERWRITE
        
        print(f"\n[INFO] Bat dau xu ly: {item}")
        if is_url(item):
            reference_str = item 
            print("[INFO] Dang kiem tra thong tin tieu de...")
            try:
                with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                    info = ydl.extract_info(item, download=False)
                    original_title = info.get('title', 'Unknown_Title')
                    file_title = sanitize_filename(original_title)
            except Exception as e:
                # Link bi chan bao mat, can dang nhap, da xoa hoac rieng tu.
                print(f"[LOI] Khong lay duoc thong tin link: {str(e).splitlines()[0][:160]}")
                print(f"[BO QUA] Khong tong hop link hong vao build-audio2md.md: {item}")
                xoa_dong_md(item)
                continue

            raw_md_path = os.path.join(OUTPUT_DIR, f"{file_title}_raw.md")
            refine_md_path = os.path.join(OUTPUT_DIR, f"{file_title}_refine.md")
            
            if not item_overwrite and (os.path.exists(raw_md_path) or os.path.exists(refine_md_path)):
                ans = input(f"[?] File MD cua '{file_title}' da ton tai. Ban co muon ghi de khong? (Y/N): ")
                if ans.strip().lower() != 'y':
                    print(f"[SKIP] Bo qua link: {item}")
                    continue
                item_overwrite = True

            raw_text, target_audio, file_title = download_media(item)
            if not file_title or (raw_text is None and target_audio is None):
                print(f"[BO QUA] Tai that bai, khong tong hop vao build-audio2md.md: {item}")
                xoa_dong_md(item)
                continue
            is_temp = True

        else:
            target_audio = item
            original_title = os.path.splitext(os.path.basename(item))[0]
            file_title = sanitize_filename(original_title)
            is_temp = False
            reference_str = os.path.basename(item) 
            
            raw_md_path = os.path.join(OUTPUT_DIR, f"{file_title}_raw.md")
            refine_md_path = os.path.join(OUTPUT_DIR, f"{file_title}_refine.md")
            
            if not item_overwrite and (os.path.exists(raw_md_path) or os.path.exists(refine_md_path)):
                ans = input(f"[?] File MD cua '{file_title}' da ton tai. Ban co muon ghi de khong? (Y/N): ")
                if ans.strip().lower() != 'y':
                    print(f"[SKIP] Bo qua file: {item}")
                    continue
                item_overwrite = True
            
        raw_md_path = os.path.join(OUTPUT_DIR, f"{file_title}_raw.md")
        
        if raw_text:
            raw_text_content = f"> **Reference:** {reference_str}\n\n{raw_text}"
            with open(raw_md_path, 'w', encoding='utf-8') as f:
                f.write(raw_text_content)
            print(f"[SUCCESS] Da luu ban Nguyen Tac (Raw): {file_title}_raw.md")
            
        elif target_audio and os.path.exists(target_audio):
            # Chi tai su dung ban Raw cu khi nguoi dung KHONG yeu cau ghi de.
            raw_text = None if item_overwrite else doc_raw_da_co(raw_md_path)
            if raw_text:
                print(f"[TIET KIEM] Da co ban Raw -> bo qua boc bang lai: {file_title}_raw.md")
            else:
                raw_text = transcribe_raw(pool, target_audio, file_title)
                if raw_text:
                    raw_text_content = f"> **Reference:** {reference_str}\n\n{raw_text}"
                    with open(raw_md_path, 'w', encoding='utf-8') as f:
                        f.write(raw_text_content)
                    print(f"[SUCCESS] Da luu ban Nguyen Tac (Raw): {file_title}_raw.md")

            if is_temp and os.path.exists(target_audio):
                os.remove(target_audio)
                print(f"[CLEANUP] Da xoa file tam: {target_audio}")
                
        if not raw_text:
            # Boc bang that bai (het key, API loi...) -> khong de lai dong rac
            # tro toi file khong ton tai. Bam vao wikilink hong, Obsidian se tu
            # tao ra file rong.
            print(f"[BO QUA] Khong tao duoc noi dung: {item}")
            if is_url(item):
                xoa_dong_md(item)
            continue

        co_refine = refine_content(pool, raw_text, original_title, file_title,
                                   reference_str, item_overwrite)

        # Chi ghi vao bang khi da thuc su co file. Ghi o day (thay vi truoc khi
        # tai) de wikilink khop dung ten file cuoi cung do download_media tra ve.
        if is_url(item):
            update_md_table(item, original_title, f"{file_title}_raw",
                            f"{file_title}_refine" if co_refine else None)

    pool.tong_ket()

if __name__ == "__main__":
    main()