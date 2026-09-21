import requests
import re
from pathlib import Path
from bs4 import BeautifulSoup

def extract_aeon_mp3_url(target_url: str) -> str:
    """
    Trích xuất đường dẫn MP3 từ bài luận của Aeon bằng cách phân tích DOM và SSR Hydration.
    """
    # Bypass cơ bản các WAF filter chặn request không có User-Agent chuẩn
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(target_url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        return f"System Error: Network request failed. Details: {e}"

    html_content = response.text
    soup = BeautifulSoup(html_content, 'html.parser')

    # Method 1: Traverse DOM tìm Open Graph Audio meta tag (Chuẩn Semantic Web)
    meta_audio = soup.find('meta', property='og:audio')
    if meta_audio and meta_audio.get('content'):
        return meta_audio.get('content')

    # Method 2: Fallback bằng Regex quét qua Next.js Hydration JSON / Script tag
    # Target pattern: https://cdn.aeon.co/.../xxxx.mp3
    mp3_pattern = re.compile(r'(https?://[^"\'\s>]+?\.mp3)')
    match = mp3_pattern.search(html_content)
    
    if match:
        return match.group(1)
        
    return "Data Exception: Không tìm thấy node chứa định dạng MP3 trong cấu trúc HTML hiện tại."

# Trigger function
url = "https://aeon.co/essays/play-is-doing-its-work-even-if-were-not-keeping-score"
mp3_link = extract_aeon_mp3_url(url)
print(f"Extracted MP3 Link: {mp3_link}")

if not mp3_link.startswith("http"):
    raise RuntimeError(mp3_link)

output_path = Path(r"C:\audio2md\data\input\more-nothing-more.mp3")
output_path.parent.mkdir(parents=True, exist_ok=True)

try:
    with requests.get(
        mp3_link,
        headers={"User-Agent": "Mozilla/5.0"},
        stream=True,
        timeout=30,
    ) as response:
        response.raise_for_status()
        with output_path.open("wb") as output_file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output_file.write(chunk)
except requests.RequestException as e:
    raise RuntimeError(f"Không thể tải MP3: {e}") from e

print(f"MP3 saved to: {output_path}")
