import os
import sys
import time
import urllib.parse
import re
import glob
import yt_dlp

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(BASE_DIR, 'data', 'input')
OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'output')
MP4_DIR = os.path.join(BASE_DIR, 'data', 'mp4')
MP3_DIR = os.path.join(BASE_DIR, 'data', 'mp3')

# Đọc .env nội bộ để hỗ trợ cả dạng chuẩn KEY=VALUE và cấu hình save-mp4: Yes.
def load_project_env():
    try:
        with open(os.path.join(BASE_DIR, '.env'), encoding='utf-8') as config:
            for line in config:
                match = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*[:=]\s*(.*?)\s*(?:#.*)?$', line)
                if match:
                    key, value = match.groups()
                    os.environ.setdefault(key.replace('-', '_').upper(), value.strip())
    except OSError:
        pass

load_project_env()

def env_yes(key, custom_key):
    """Accept normal dotenv keys and the documented save-mp4/save-mp3 keys."""
    value = os.environ.get(key, '')
    if value:
        return value.strip().lower() == 'yes'
    return os.environ.get(custom_key.replace('-', '_').upper(), '').strip().lower() == 'yes'

from gemini_pool import GeminiPool

FORCE_OVERWRITE = os.environ.get("FORCE_OVERWRITE", "0") == "1"
SAVE_MP4 = env_yes("SAVE_MP4", "save-mp4")
SAVE_MP3 = env_yes("SAVE_MP3", "save-mp3")

# Gioi han do phan giai video nguon, khong ma hoa lai. Mac dinh 1080p.
MP4_MAX_HEIGHT = os.environ.get('MP4_MAX_HEIGHT', '1080').strip()
if MP4_MAX_HEIGHT not in ('720', '1080'):
    print(f"[WARN] MP4_MAX_HEIGHT={MP4_MAX_HEIGHT!r} khong hop le; dung 1080.")
    MP4_MAX_HEIGHT = '1080'

try:
    MP4_FILENAME_LIMIT = int(os.environ.get('MP4_FILENAME_LIMIT', '150'))
except ValueError:
    MP4_FILENAME_LIMIT = 150
if not 80 <= MP4_FILENAME_LIMIT <= 180:
    print(f"[WARN] MP4_FILENAME_LIMIT={MP4_FILENAME_LIMIT!r} khong hop le; dung 150.")
    MP4_FILENAME_LIMIT = 150


def mp4_output_template():
    """Bound default media titles before yt-dlp opens a Windows .part file."""
    return f'%(title).{MP4_FILENAME_LIMIT}B.%(ext)s'


def mp4_format(max_dimension):
    """Best MP4 source capped for landscape and portrait videos alike."""
    return (
        f'bestvideo[height<={max_dimension}]+bestaudio/'
        f'best[height<={max_dimension}]/'
        f'bestvideo[width<={max_dimension}]+bestaudio/'
        f'best[width<={max_dimension}]/'
        # A few extractors expose only an unknown-resolution muxed format.
        'best'
    )

def is_url(string):
    try:
        result = urllib.parse.urlparse(string)
        return all([result.scheme, result.netloc])
    except:
        return False

def canonical_url(value):
    """Return one stable key for a media URL, ignoring harmless trackers."""
    parsed = urllib.parse.urlsplit(value.strip())
    host = parsed.netloc.lower().removeprefix('www.')
    path = parsed.path.rstrip('/')

    # A YouTube video can be expressed as youtu.be, /watch, or /shorts.
    if host in ('youtube.com', 'm.youtube.com', 'youtu.be'):
        video_id = ''
        if host == 'youtu.be':
            video_id = path.lstrip('/').split('/')[0]
        elif path == '/watch':
            video_id = urllib.parse.parse_qs(parsed.query).get('v', [''])[0]
        elif path.startswith('/shorts/'):
            video_id = path.split('/')[2]
        if video_id:
            return f'youtube:{video_id}'

    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, val) for key, val in query
             if not key.lower().startswith('utm_') and key.lower() not in ('fbclid', 'si', 'pp')]
    normalized_query = urllib.parse.urlencode(query)
    return urllib.parse.urlunsplit((parsed.scheme.lower(), host, path, normalized_query, ''))

def youtube_extraction_url(value):
    """Strip tracking parameters before handing a YouTube URL to yt-dlp."""
    parsed = urllib.parse.urlsplit(value.strip())
    host = parsed.netloc.lower().removeprefix('www.')
    if host == 'youtu.be':
        video_id = parsed.path.lstrip('/').split('/')[0]
    elif host in ('youtube.com', 'm.youtube.com') and parsed.path == '/watch':
        video_id = urllib.parse.parse_qs(parsed.query).get('v', [''])[0]
    elif host in ('youtube.com', 'm.youtube.com') and parsed.path.startswith('/shorts/'):
        video_id = parsed.path.split('/')[2]
    else:
        video_id = ''
    if video_id:
        return f'https://www.youtube.com/watch?v={video_id}'
    return value.strip()

def sanitize_filename(name):
    # Cắt bỏ phần sau dấu '|' (tên kênh) hoặc '#' (hashtag) để tên file ngắn gọn
    name = re.split(r'[|#]', name)[0].strip()
    clean_name = re.sub(r'[\\/*?:"<>|]', "_", name)
    return " ".join(clean_name.split())[:150]

def local_media_title(file_path):
    """Get the default output title from a local media filename, never from a URL."""
    return sanitize_filename(os.path.splitext(os.path.basename(file_path))[0])

def normalize_generated_text(text):
    """Keep generated Markdown plain: short hyphens, no emoji/AI icons."""
    if not text:
        return text

    # Replace en/em dashes (and the common horizontal bar variants) with '-'.
    text = re.sub(r'[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]', '-', text)

    # Remove emoji and pictographic symbols so output stays suitable for plain Markdown.
    text = re.sub(
        r'[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]',
        '',
        text,
    )
    return re.sub(r'[ \t]{2,}', ' ', text).strip()

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
            
        matches = []
        target_key = canonical_url(item_url)
        for i, line in enumerate(lines):
            parts = line.rstrip('\n').split('|')
            if len(parts) >= 9 and parts[1].strip().isdigit() and canonical_url(parts[2]) == target_key:
                matches.append((i, parts))

        if not matches:
            # Link moi (vi du chon tu menu kenh): chen mot dong ngay duoi header
            # thay vi bo qua. Nho vay batch khong can ghi truoc dong 'Pending'.
            them_dong_moi(md_file, lines, item_url, safe_title,
                          raw_file_name, refine_file_name)
            return
        if len(matches) > 1:
            print(f"[WARN] Tim thay {len(matches)} dong trung link; chi cap nhat dong dau tien.")

        i, parts = matches[0]
        parts[3] = f" {safe_title} "
        parts[5] = f" [[{raw_file_name}]] "
        parts[6] = f" [[{refine_file_name}]] " if refine_file_name else " "
        parts[7] = " Done " if refine_file_name else " Raw only "
        lines[i] = "|".join(parts) + "\n"
                        
        with open(md_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    except Exception as e:
        print(f"[WARN] Khong the cap nhat file md danh sach: {e}")

def them_dong_moi(md_file, lines, item_url, safe_title, raw_file_name, refine_file_name):
    """Chen mot dong moi ngay duoi header bang, STT = so lon nhat + 1."""
    stt_max = 0
    vi_tri_chen = len(lines)
    for i, line in enumerate(lines):
        parts = line.rstrip('\n').split('|')
        if len(parts) >= 9 and parts[1].strip().isdigit():
            stt_max = max(stt_max, int(parts[1].strip()))
            vi_tri_chen = min(vi_tri_chen, i)

    if vi_tri_chen == len(lines):
        # Bang chua co dong du lieu nao; chen sau header va dong ke phan cach.
        vi_tri_chen = min(2, len(lines))

    thoi_gian = time.strftime('%d/%m/%y %H:%M:%S')
    refine_o = f" [[{refine_file_name}]] " if refine_file_name else " "
    trang_thai = " Done " if refine_file_name else " Raw only "
    dong_moi = "|".join([
        "", f" {stt_max + 1} ", f" {item_url} ", f" {safe_title} ",
        f" {thoi_gian} ", f" [[{raw_file_name}]] ", refine_o, trang_thai, "",
    ]) + "\n"

    lines.insert(vi_tri_chen, dong_moi)
    with open(md_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f"[+] Da them vao danh sach o STT {stt_max + 1}: {safe_title}")

def ghi_loi_md(item_url, reason):
    """Keep failed URLs visible and mark the row for a later retry."""
    md_file = os.path.join(INPUT_DIR, 'build-audio2md.md')
    if not os.path.exists(md_file):
        return
    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        target_key = canonical_url(item_url)
        found = False
        for i, line in enumerate(lines):
            parts = line.rstrip('\n').split('|')
            if len(parts) >= 9 and parts[1].strip().isdigit() and canonical_url(parts[2]) == target_key:
                parts[7] = f" Failed: {reason[:80]} "
                lines[i] = "|".join(parts) + "\n"
                found = True
                break

        if not found:
            return

        with open(md_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"[LOI] Da danh dau link de thu lai sau: {item_url}")
    except Exception as e:
        print(f"[WARN] Khong the go dong khoi file md danh sach: {e}")

# Chi nhung thong bao thuc su tuyet doi moi coi la hong han. Rieng
# "This video is not available" KHONG thuoc nhom nay: da kiem chung 23/09/2026
# rang client web bi tu choi nhung client android van tai duoc binh thuong.
PERMANENT_ERROR_PATTERNS = (
    'private video',
    'removed by the uploader',
    'account associated with this video has been terminated',
    'members-only',
)

def loi_vinh_vien(message):
    """True khi yt-dlp bao link khong the tai duoc du co thu lai."""
    text = str(message).lower()
    return any(pattern in text for pattern in PERMANENT_ERROR_PATTERNS)

# Thu tu dua tren bang kiem chung 23/09/2026 voi link tUCyf4jvwWs.
YOUTUBE_CLIENT_FALLBACKS = ('default', 'android', 'ios', 'mweb', 'tv')

COOKIES_FROM_BROWSER = os.environ.get('YT_COOKIES_FROM_BROWSER', '').strip()

def la_link_youtube(url):
    host = urllib.parse.urlsplit(url).netloc.lower().removeprefix('www.')
    return host in ('youtube.com', 'm.youtube.com', 'youtu.be')

def opts_theo_client(base_opts, client):
    """Gan player_client cho mot ban sao cua base_opts; 'default' giu nguyen."""
    opts = dict(base_opts)
    if client == 'default':
        opts.pop('extractor_args', None)
    else:
        opts['extractor_args'] = {'youtube': {'player_client': [client]}}
    if client == 'cookies':
        opts.pop('extractor_args', None)
        opts['cookiesfrombrowser'] = (COOKIES_FROM_BROWSER,)
    return opts

def danh_sach_client(url):
    """Cac client se thu lan luot; link khong phai YouTube chi chay mot luot."""
    if not la_link_youtube(url):
        return ('default',)
    clients = list(YOUTUBE_CLIENT_FALLBACKS)
    if COOKIES_FROM_BROWSER:
        clients.append('cookies')
    return tuple(clients)

def thu_tung_client(base_opts, url, mo_ta, action, uu_tien=None):
    """Chay `action(ydl)` lan luot qua cac client, tra ve (ket_qua, client).

    `action` nhan mot YoutubeDL da cau hinh va tra ve ket qua; neu nem exception
    thi chuyen sang client ke tiep. Tra ve (None, None) khi tat ca deu that bai.
    """
    clients = danh_sach_client(url)
    if uu_tien and uu_tien in clients:
        clients = (uu_tien,) + tuple(c for c in clients if c != uu_tien)

    for client in clients:
        if len(clients) > 1:
            print(f"[INFO] {mo_ta} - thu client: {client}")
        try:
            with yt_dlp.YoutubeDL(opts_theo_client(base_opts, client)) as ydl:
                ket_qua = action(ydl)
            print(f"[SUCCESS] {mo_ta} - dung client: {client}")
            return ket_qua, client
        except Exception as e:
            print(f"[WARN] {mo_ta} loi voi client '{client}': {str(e).splitlines()[0][:160]}")
            if loi_vinh_vien(e):
                print("[LOI] Link bi go/rieng tu, khong thu them client nao.")
                break
    return None, None

def download_media(link, uu_tien_client=None):
    print(f"\n[INFO] Dang ket noi toi URL: {link}")
    download_url = youtube_extraction_url(link)
    common_opts = {
        'ffmpeg_location': r'C:\FFmpeg\bin' if __import__('os').path.exists(r'C:\FFmpeg\bin\ffmpeg.exe') else (__import__('os').path.join(__import__('os').environ.get('USERPROFILE', ''), 'FFmpeg', 'bin') if __import__('os').path.exists(__import__('os').path.join(__import__('os').environ.get('USERPROFILE', ''), 'FFmpeg', 'bin', 'ffmpeg.exe')) else None),
        'outtmpl': os.path.join(INPUT_DIR, '%(id)s.%(ext)s'),
        'quiet': False,
        'no_warnings': True,
        'restrictfilenames': True,
        'retries': 10,
        'fragment_retries': 10,
        'extractor_retries': 5,
    }
    subtitle_opts = {
        **common_opts,
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        # English captions are usually the original track and are less likely
        # to be rate-limited than translated Vietnamese auto-captions.
        'subtitleslangs': ['en', 'vi'],
        'sleep_interval_subtitles': 2,
    }
    audio_opts = {
        **common_opts,
        'format': 'bestaudio/bestaudio*/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    video_opts = {
        **common_opts,
        'format': mp4_format(MP4_MAX_HEIGHT),
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(MP4_DIR, mp4_output_template()),
        'windowsfilenames': True,
    }

    info = None
    video_key = canonical_url(download_url).removeprefix('youtube:')
    client = uu_tien_client

    if SAVE_MP4:
        print(f"[INFO] MP4: chon ban nguon toi da {MP4_MAX_HEIGHT}p neu co.")
        os.makedirs(MP4_DIR, exist_ok=True)
        _, client_mp4 = thu_tung_client(
            video_opts, download_url, "Tai video MP4",
            lambda ydl: ydl.download([download_url]), client)
        if client_mp4:
            print(f"[SUCCESS] Da luu video vao: {MP4_DIR}")
            if client_mp4 != 'default':
                # Cac client thay the chi tra ve mot format muxed 360p.
                print(f"[WARN] MP4 tai qua client '{client_mp4}' nen toi da chi 360p; "
                      "client 'default' moi co ban do phan giai cao.")
            client = client or client_mp4
        else:
            print("[WARN] Khong tai duoc MP4, van tiep tuc buoc boc bang.")

    # Chi thu dung client ma buoc metadata da chon. Cac client khac thuong bao
    # 'Requested format is not available' chu khong phai 'khong co phu de',
    # nen do them chi ton thoi gian ma khong doi duoc ket qua.
    try:
        with yt_dlp.YoutubeDL(opts_theo_client(subtitle_opts, client or 'default')) as ydl:
            info = ydl.extract_info(download_url, download=True)
    except Exception as e:
        print(f"[WARN] Tai phu de loi voi client '{client or 'default'}': "
              f"{str(e).splitlines()[0][:160]}")
        info = None

    sub_files = glob.glob(os.path.join(INPUT_DIR, f"{video_key}*.vtt")) + \
                glob.glob(os.path.join(INPUT_DIR, f"{video_key}*.srt"))
    for sub_file in sub_files:
        raw_text = clean_subtitle(sub_file)
        if raw_text:
            if not info:
                info, _ = thu_tung_client(
                    {'quiet': True, 'no_warnings': True, 'noplaylist': True},
                    download_url, "Lay tieu de",
                    lambda ydl: ydl.extract_info(download_url, download=False), client)
                info = info or {}
            title = sanitize_filename(info.get('title', video_key or 'Unknown_Title'))
            for sf in sub_files:
                try: os.remove(sf)
                except OSError: pass
            print(f"[SUCCESS] Da dung phu de: {os.path.basename(sub_file)}")
            return raw_text, None, title

    print("[INFO] Khong co phu de hop le, dang tai am thanh...")

    def tai_audio(ydl):
        thong_tin = ydl.extract_info(download_url, download=True)
        return thong_tin, os.path.splitext(ydl.prepare_filename(thong_tin))[0] + '.mp3'

    ket_qua, _ = thu_tung_client(audio_opts, download_url, "Tai am thanh",
                                 tai_audio, client)
    if not ket_qua:
        print("[ERROR] Da thu het cac client nhung khong tai duoc am thanh.")
        return None, None, None

    info, mp3_file = ket_qua
    title = sanitize_filename(info.get('title', 'Unknown_Title'))
    if SAVE_MP3 and os.path.exists(mp3_file):
        os.makedirs(MP3_DIR, exist_ok=True)
        saved_mp3 = os.path.join(MP3_DIR, os.path.basename(mp3_file))
        os.replace(mp3_file, saved_mp3)
        mp3_file = saved_mp3
        print(f"[SUCCESS] Da luu audio vao: {MP3_DIR}")
    print(f"[SUCCESS] Da tai am thanh: {os.path.basename(mp3_file)}")
    return None, mp3_file, title

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
4. KHÔNG dùng gạch ngang dài (—, –, ―). Nếu cần, chỉ dùng dấu gạch ngang ngắn '-'.
5. KHÔNG dùng emoji, biểu tượng AI hoặc ký hiệu trang trí.
Trả về duy nhất nội dung thô, ở dạng Markdown thuần."""

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
            return normalize_generated_text(response.text) if response.text else None
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

***

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
- Không dùng gạch ngang dài (—, –, ―); chỉ dùng dấu gạch ngang ngắn '-'.
- Không dùng emoji, biểu tượng AI hoặc ký hiệu trang trí.

Nội dung Transcript:
{raw_text}
"""
    
    def tinh_luyen(client, model):
        response = client.models.generate_content(model=model, contents=prompt)
        return normalize_generated_text(response.text) if response.text else None

    refined_text = pool.chay(tinh_luyen, f"Refine '{file_title}'")
    if refined_text:
        final_output = f"{refined_text}\n\n***\n**Reference:** {reference_str}"
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
            metadata_opts = {
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
            }
            metadata_url = youtube_extraction_url(item)
            info, client_metadata = thu_tung_client(
                metadata_opts, metadata_url, "Lay thong tin link",
                lambda ydl: ydl.extract_info(metadata_url, download=False))
            if info:
                original_title = info.get('title', 'Unknown_Title')
                file_title = sanitize_filename(original_title)
            else:
                # Khong client nao lay duoc metadata. Van thu buoc tai media:
                # mot so client khong cho xem thong tin nhung van cho tai.
                print("[LOI] Khong lay duoc thong tin link qua bat ky client nao.")
                original_title = canonical_url(item).removeprefix('youtube:') or 'Unknown_Title'
                file_title = sanitize_filename(original_title)

            raw_md_path = os.path.join(OUTPUT_DIR, f"{file_title}_raw.md")
            refine_md_path = os.path.join(OUTPUT_DIR, f"{file_title}_refine.md")
            
            if not item_overwrite and (os.path.exists(raw_md_path) or os.path.exists(refine_md_path)):
                ans = input(f"[?] File MD cua '{file_title}' da ton tai. Ban co muon ghi de khong? (Y/N): ")
                if ans.strip().lower() != 'y':
                    print(f"[SKIP] Bo qua link: {item}")
                    continue
                item_overwrite = True

            raw_text, target_audio, file_title = download_media(item, client_metadata)
            if not file_title or (raw_text is None and target_audio is None):
                so_client = len(danh_sach_client(youtube_extraction_url(item)))
                print(f"[BO QUA] Tai that bai, khong tong hop vao build-audio2md.md: {item}")
                ghi_loi_md(item, f"Tai that bai (da thu {so_client} client)")
                continue
            is_temp = True

        else:
            target_audio = item
            original_title = local_media_title(item)
            file_title = original_title
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
            raw_text_content = f"> **Reference:** {reference_str}\n\n{normalize_generated_text(raw_text)}"
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
                    raw_text_content = f"> **Reference:** {reference_str}\n\n{normalize_generated_text(raw_text)}"
                    with open(raw_md_path, 'w', encoding='utf-8') as f:
                        f.write(raw_text_content)
                    print(f"[SUCCESS] Da luu ban Nguyen Tac (Raw): {file_title}_raw.md")

            if is_temp and not SAVE_MP3 and os.path.exists(target_audio):
                os.remove(target_audio)
                print(f"[CLEANUP] Da xoa file tam: {target_audio}")
                
        if not raw_text:
            # Keep the failed URL in the list so it can be retried later.
            print(f"[BO QUA] Khong tao duoc noi dung: {item}")
            if is_url(item):
                ghi_loi_md(item, "Khong tao duoc noi dung")
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
