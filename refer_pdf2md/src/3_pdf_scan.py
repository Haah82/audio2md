import os, sys, glob, time, re, math, tempfile, unicodedata
import logging, warnings
from google import genai
try:
    from google.genai import types as genai_types
except Exception:
    genai_types = None
from dotenv import load_dotenv
import pymupdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import image_extractor
import gemini_pool

logging.getLogger("google").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(BASE_DIR, 'data', 'input')
# GUI dat PDF2MD_OUTPUT_DIR de giu cau truc thu muc con cua input trong output.
# ASSETS_DIR duoi day dua theo OUTPUT_DIR nen anh di theo dung thu muc Markdown.
OUTPUT_DIR = os.environ.get('PDF2MD_OUTPUT_DIR') or os.path.join(BASE_DIR, 'data', 'output')
FORCE = os.environ.get('PDF2MD_FORCE') == '1'
ASSETS_DIR = os.path.join(OUTPUT_DIR, image_extractor.ASSETS_DIRNAME)

# Ma thoat bao cho GUI biet file DA TAO nhung con thieu trang - khac han loi han.
EXIT_THIEU_TRANG = 4

# Model đọc thẳng từ .env (biến GEMINI_MODEL) để tránh vòng lặp quét 404 qua
# một mảng ứng viên. Muốn nâng cấp model chỉ cần sửa 1 dòng trong .env.
DEFAULT_MODEL = 'gemini-1.5-flash'

# --- Chia cụm ĐỘNG theo mật độ chữ -------------------------------------------
# Bài học từ tài liệu AFD 475 trang: cụm 40 trang có chỗ 191K ký tự, có chỗ chỉ
# 17K (chênh 11 lần). Cụm dày chữ vượt trần output của model -> markdown bị CẮT
# CỤT ở đuôi và các trang cuối cụm mất trắng trong im lặng. Nên trần thật sự là
# SỐ KÝ TỰ chứ không phải số trang; số trang chỉ còn là chặn trên.
CHUNK_MAX_PAGES = int(os.environ.get('PDF2MD_CHUNK_PAGES') or 40)
CHUNK_MAX_CHARS = int(os.environ.get('PDF2MD_CHUNK_CHARS') or 60000)
# Không chia nhỏ hơn mức này khi lập kế hoạch ban đầu (lúc sửa lỗi thì được).
CHUNK_MIN_PAGES = 4
# Số lần được phép bổ đôi một dải trang khi phát hiện thiếu.
MAX_SPLIT_DEPTH = 5
# Một trang coi là ĐÃ CÓ trong markdown nếu >= tỉ lệ này số câu mẫu khớp.
# Vì sao 0.25: nhiều dòng công thức bị model xuất ra dạng LaTeX ($C_{QLDA}$)
# nên câu mẫu chữ thuần không bao giờ khớp, kéo trang xuống 2/6 hay 3/10 dù
# nội dung vẫn còn đủ. Trang MẤT THẬT thì khớp 0/N chứ không lưng chừng.
# Đo trên file .bak (bản hỏng đã biết chắc): 0.34 / 0.30 / 0.25 đều ra cùng
# một tập dải thiếu, tới 0.20 mới bắt đầu mất phát hiện thật (dải 158-159).
# Chọn 0.25 - mức thấp nhất còn giữ nguyên mọi phát hiện đúng.
COVERAGE_MIN_RATIO = float(os.environ.get('PDF2MD_TI_LE_BAO_PHU') or 0.25)
# So cau mau toi thieu de duoc phep ket luan mot trang la THIEU. Trang chi co
# 1-2 cau mau (trang bia, trang toan cong thuc, trang bang so) cho bang chung
# qua mong -> xep vao dien khong doi chieu duoc thay vi bao thieu oan.
SO_CAU_MAU_TOI_THIEU = int(os.environ.get('PDF2MD_SO_CAU_MAU_TOI_THIEU') or 3)
# Trang có ít hơn ngần này ký tự ở lớp text => trang scan thuần ảnh: không thể
# đối chiếu bằng chữ, và là ứng viên chụp ảnh nguyên trang cho phần phụ lục.
SCAN_PAGE_MAX_CHARS = 20
# DPI + ảnh xám cho bản chụp nguyên trang phụ lục (hợp đồng, chứng nhận...).
ANNEX_DPI = 100

# Nén ảnh nhúng trong cụm PDF trước khi upload. Chỉ làm với cụm nặng hơn ngưỡng
# này (MB) vì mỗi lần nén tốn ~15s CPU cho 40 trang. Đặt 0 để tắt hẳn.
NEN_ANH_TU_MB = float(os.environ.get('PDF2MD_NEN_ANH_TU_MB') or 6)
NEN_ANH_DPI = int(os.environ.get('PDF2MD_NEN_ANH_DPI') or 150)
NEN_ANH_QUALITY = int(os.environ.get('PDF2MD_NEN_ANH_QUALITY') or 70)
# Mặc định GIỮ MÀU: bản vẽ kỹ thuật (mặt bằng móng, cấu tạo cừ Larsen) hay dùng
# màu để phân lớp, ép về xám sẽ mất thông tin dù file nhẹ hơn ~5%.
NEN_ANH_XAM = os.environ.get('PDF2MD_NEN_ANH_XAM') == '1'


def clean_text_safely(text):
    # 1. Xóa thẻ <a> ẩn nếu có
    text = re.sub(r'</?a[^>]*>', '', text)

    # 2. Dọn dẹp đường kẻ rác
    text = re.sub(r'_{3,}', '', text)

    # 3. Dọn dẹp escape thừa nhưng NÉ các khối công thức LaTeX (bọc trong $...$ hoặc $$...$$)
    # ÉP NGẮT DÒNG CHO KHỐI TOÁN HỌC TRƯỚC KHI TÁCH CHUỖI
    text = text.replace('$$', '\n$$\n')

    parts = re.split(r'(\$\$.*?\$\$|\$.*?\$)', text, flags=re.DOTALL)

    for i in range(len(parts)):
        # Các index chẵn là văn bản thường, index lẻ là công thức LaTeX
        if i % 2 == 0:
            parts[i] = re.sub(r'\\([.\-\+\(\)\[\]*_])', r'\1', parts[i])
    text = "".join(parts)

    # 4. Tối ưu khoảng trắng
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text


# --- Đối chiếu bao phủ trang --------------------------------------------------

def _norm(s):
    """Chuẩn hoá để so khớp: bỏ dấu câu/khoảng trắng thừa, về chữ thường."""
    s = unicodedata.normalize('NFC', s).lower()
    s = re.sub(r'[^0-9a-zA-Zà-ỹ]+', ' ', s)
    return ' '.join(s.split())


# Một số PDF nhúng font hỏng bảng ToUnicode: cụm ghép fl/ff/fi bị đọc ra thành
# '!' hoặc ô vuông (vd 'flood' -> '!ood', 'different' -> 'di!erent'). Câu mẫu lấy
# từ những dòng đó KHÔNG BAO GIỜ khớp với markdown (nơi model đọc đúng chữ), gây
# báo nhầm là thiếu trang. Phát hiện thì bỏ dòng đó đi, không dùng làm câu mẫu.
_LIGATURE_HONG = re.compile(r'[A-Za-zÀ-ỹ][!�□]')

# Font thiếu hẳn bảng ToUnicode thì PyMuPDF trả ra chuỗi mã hoá đặc ký tự lạ và
# ký tự điều khiển (vd trang 425 tài liệu AFD: '2\x00j\x00"$%Y&\x0006...').
# Đo thực tế: dòng hỏng kiểu này chỉ đạt 0.15-0.52 ký tự "sạch", trong khi MỌI
# trang đọc được - kể cả bảng biểu và tiếng Việt có dấu - đều từ 0.98 trở lên.
_KY_TU_SACH = re.compile(r"[0-9A-Za-zÀ-ỹ \.,;:()\[\]/\-–—'\"%&+°]")
TI_LE_SACH_TOI_THIEU = 0.90


# Tài liệu soạn bằng font tiếng Việt đời cũ (VNI-Times, TCVN3/ABC) lưu ra PDF thì
# lớp text là mã của font đó, không phải Unicode: 'khái niệm đàm phán' đọc ra
# thành 'khaùi nieäm ñaøm phaùn'. Gemini nhìn ẢNH nên đọc đúng chữ, còn ta so với
# lớp text sai -> báo thiếu giả cả tài liệu (bộ slide 'Negotiate in PM' bị báo
# thiếu 11/12 trang dù file .md có đủ nội dung).
# Dấu hiệu: các chữ cái Latin KHÔNG có trong cả tiếng Việt lẫn tiếng Anh.
# Đo thực tế: trang dùng font đời cũ 10.9-12.9%, trang Unicode bình thường
# 0.0-0.1%. Lấy ngưỡng 3% cho biên rộng về cả hai phía.
_CHU_CAI_LA = set('ñøöäïåæßœÿýþðčšžğı')
TI_LE_CHU_LA_TOI_DA = 0.03


def _font_doi_cu(line):
    """Dòng có dấu hiệu font tiếng Việt đời cũ (VNI/TCVN3) hay không."""
    chu = [c for c in line if c.isalpha()]
    if not chu:
        return False
    la = sum(1 for c in chu if c.lower() in _CHU_CAI_LA)
    return la / len(chu) > TI_LE_CHU_LA_TOI_DA


def _du_sach(line):
    """Dòng có đủ tỉ lệ ký tự đọc được để dùng làm câu mẫu đối chiếu hay không."""
    if not line:
        return False
    sach = sum(1 for c in line if _KY_TU_SACH.match(c))
    return sach / len(line) >= TI_LE_SACH_TOI_THIEU


def _ti_le_anh_phu_trang(page):
    """Tỉ lệ diện tích ảnh lớn nhất trên trang so với diện tích cả trang."""
    try:
        dien_tich = abs(page.rect.width * page.rect.height)
        if dien_tich <= 0:
            return 0.0
        lon_nhat = 0.0
        for khoi in page.get_text('dict')['blocks']:
            if khoi.get('type') == 1:  # 1 = khối ảnh
                x0, y0, x1, y1 = khoi['bbox']
                lon_nhat = max(lon_nhat, abs((x1 - x0) * (y1 - y0)) / dien_tich)
        return lon_nhat
    except Exception:
        return 0.0


def _page_probes(page, max_probes=10, words=9):
    """Lấy vài 'câu mẫu' đủ dài của một trang để dò xem trang đó có mặt trong
    markdown hay không. Trang scan thuần ảnh trả về [] -> miễn kiểm tra."""
    # Trang bị một tấm ảnh phủ gần kín là bản scan giấy tờ. Chữ trên đó (nếu có)
    # là OCR của bên khác đã nhúng sẵn, thường sai bét: 'Độc lập - Tự do - Hạnh
    # phúc' ra thành 'Doc lap - Tu. do - Hanh ph&'. Câu mẫu lấy từ đó không bao
    # giờ khớp với bản Gemini đọc đúng, gây báo thiếu giả và kéo theo cả chuỗi
    # chia nhỏ chạy lại vô ích. Đo thực tế trên tài liệu AFD: trang text gốc phủ
    # 0.9%, brochure có ảnh lớn phủ 27%, trang scan giấy tờ phủ 100%.
    if _ti_le_anh_phu_trang(page) >= 0.9:
        return []
    probes = []
    for line in page.get_text().split('\n'):
        line = line.strip()
        if len(line) < 40:
            continue
        if (_LIGATURE_HONG.search(line) or not _du_sach(line)
                or _font_doi_cu(line)):
            continue
        w = _norm(line).split()
        if len(w) < words:
            continue
        probes.append(' '.join(w[:words]))
        if len(probes) >= max_probes:
            break
    return probes


# Lấy câu mẫu của một trang phải gọi get_text('dict') để đo tỉ lệ ảnh phủ, mà
# hàm đó khá nặng: 10s cho 475 trang. Trong một lượt dò, cùng bộ câu mẫu bị tính
# lại tới BA lần (align_pages, _pages_missing, rồi collect_missing) -> 38s cho
# việc lẽ ra chỉ tốn 13s. Nhớ lại theo từng tài liệu để chỉ tính đúng một lần.
_CACHE_CAU_MAU = {}


def cau_mau_cua(doc, p0):
    """Câu mẫu của trang p0 (0-based) trong `doc`, có nhớ lại kết quả."""
    khoa = (id(doc), doc.page_count, p0)
    cu = _CACHE_CAU_MAU.get(khoa)
    if cu is None:
        cu = _page_probes(doc[p0])
        # Chặn trên cho bộ nhớ: quét cả thư mục nhiều tài liệu thì dọn bớt.
        if len(_CACHE_CAU_MAU) > 20000:
            _CACHE_CAU_MAU.clear()
        _CACHE_CAU_MAU[khoa] = cu
    return cu


def xoa_cache_cau_mau():
    _CACHE_CAU_MAU.clear()


def _pages_missing(doc, start0, end0, markdown):
    """Trả về danh sách trang (1-based) trong dải [start0,end0] KHÔNG tìm thấy
    trong `markdown`. Trang không có lớp text được bỏ qua (không đối chiếu được)."""
    if not markdown:
        return list(range(start0 + 1, end0 + 2))
    hay = _norm(markdown)
    missing = []
    for p0 in range(start0, end0 + 1):
        probes = cau_mau_cua(doc, p0)
        # Ít hơn ngần này câu mẫu thì bằng chứng quá mỏng để kết luận: chỉ cần
        # model diễn đạt khác đi một chỗ là thành "thiếu trang" oan. Đo trên tài
        # liệu P-y: trang 1 và 37 mỗi trang chỉ có 1 câu mẫu, và trang 1 bị báo
        # nhầm dù nội dung vẫn còn nguyên. Thà bỏ sót còn hơn gọi API oan rồi
        # chèn nội dung trùng vào một file vốn đã tốt.
        if len(probes) < SO_CAU_MAU_TOI_THIEU:
            continue
        hit = sum(1 for pr in probes if pr in hay)
        if hit / len(probes) < COVERAGE_MIN_RATIO:
            missing.append(p0 + 1)
    return missing


# --- Gọi Gemini ---------------------------------------------------------------

def _response_text(res):
    """Lấy text kể cả khi model dừng vì chạm trần output. res.text của SDK có
    thể trả None/ném lỗi trong ca đó, nên vét thẳng từ candidates/parts để CỨU
    phần đã sinh thay vì vứt cả cụm."""
    try:
        t = res.text
        if t:
            return t
    except Exception:
        pass
    out = []
    for cand in (getattr(res, 'candidates', None) or []):
        content = getattr(cand, 'content', None)
        for part in (getattr(content, 'parts', None) or []):
            piece = getattr(part, 'text', None)
            if piece:
                out.append(piece)
    return "".join(out)


def _finish_reason(res):
    for cand in (getattr(res, 'candidates', None) or []):
        fr = getattr(cand, 'finish_reason', None)
        if fr is not None:
            return str(fr).upper()
    return ""


def _drop_partial_tail(text):
    """Khi bị cắt cụt, dòng cuối thường đứt giữa chừng -> bỏ dòng đó cho sạch."""
    lines = text.rstrip().split('\n')
    if len(lines) > 1:
        lines = lines[:-1]
    return '\n'.join(lines)


def _mot_luot_goi(client, model_name, pdf_path, prompt, label=""):
    """Trọn gói upload + gọi model + xoá file TRÊN CÙNG MỘT client.

    Phải trọn gói vì file đã upload chỉ tồn tại trong project của key đó; đổi key
    là phải upload lại từ đầu. Ném lỗi ra ngoài để bể key phân loại và định tuyến.
    """
    uploaded = client.files.upload(file=pdf_path)
    try:
        print(f"⏳ Đang chờ Google xử lý{label}", end="")
        while "PROCESSING" in str(uploaded.state):
            print(".", end="", flush=True)
            time.sleep(2)
            uploaded = client.files.get(name=uploaded.name)
        print()
        if "FAILED" in str(uploaded.state):
            raise RuntimeError(f"Server Gemini xử lý file thất bại{label}.")

        print(f"🧠 Đang trích xuất bằng {model_name}{label}...")
        kwargs = {'model': model_name, 'contents': [uploaded, prompt]}
        if genai_types is not None:
            max_out = os.environ.get('GEMINI_MAX_OUTPUT_TOKENS')
            if max_out:
                kwargs['config'] = genai_types.GenerateContentConfig(
                    max_output_tokens=int(max_out))
        return client.models.generate_content(**kwargs)
    finally:
        try:
            client.files.delete(name=uploaded.name)
        except Exception:
            pass


def _gemini_convert_file(be_key, model_name, pdf_path, prompt, label=""):
    """Chuyển 1 cụm PDF sang markdown, tự xoay vòng qua bể API key.

    Trả về (markdown_da_don, bi_cat_cut); (None, False) nếu thất bại hoàn toàn.
    """
    try:
        res, key = be_key.goi(
            lambda client, ten: _mot_luot_goi(client, model_name, pdf_path,
                                              prompt, f"{label} [{ten}]"),
            nhan=label)
    except gemini_pool.LoiHetPool as e:
        print(f"❌ {e}")
        return None, False
    except Exception as e:  # noqa: BLE001
        if "404" in str(e) or "not found" in str(e).lower():
            print(f"❌ Lỗi 404: Model [{model_name}] không khả dụng với key này.")
            print("   👉 Vui lòng kiểm tra lại biến GEMINI_MODEL trong file .env!")
        else:
            print(f"⚠️ Lỗi nội bộ với {model_name}{label}: {e}")
        return None, False

    text = _response_text(res)
    reason = _finish_reason(res)
    truncated = 'MAX_TOKEN' in reason
    if not text:
        if reason and 'STOP' not in reason:
            print(f"⚠️ Model dừng bất thường{label}: {reason}")
        return None, truncated
    text = text.replace("```markdown", "").replace("```", "").strip()
    if truncated:
        print(f"✂️  Model chạm trần output{label} -> giữ phần đã sinh, "
              f"phần còn lại sẽ chạy lại ở cụm nhỏ hơn.")
        text = _drop_partial_tail(text)
    return clean_text_safely(text), truncated


def _nen_anh_trong_cum(chunk):
    """Hạ độ phân giải ảnh nhúng trong cụm PDF trước khi upload.

    LƯU Ý VỀ CHI PHÍ: việc này KHÔNG giảm token. Google tính mỗi trang PDF là
    258 token đầu vào bất kể độ phân giải ("There is no cost reduction for pages
    at lower sizes, other than bandwidth"). Cái nó tiết kiệm là BĂNG THÔNG và
    THỜI GIAN UPLOAD, đồng thời giảm số lần upload hỏng giữa chừng - mà mỗi lần
    hỏng phải gọi lại cả cụm nên gián tiếp vẫn đỡ tốn token.

    Đo trên cụm 40 trang nặng nhất của tài liệu AFD: 14.8 MB -> 10.2 MB (giảm
    31%) ở 150 DPI, lớp text giữ nguyên 40.061 ký tự không suy suyển. Giữ lớp
    text là bắt buộc: model Gemini 3 đọc chữ gốc từ PDF và KHÔNG tính tiền phần
    chữ đó, nên tuyệt đối không được render trang thành ảnh phẳng.
    """
    if not hasattr(chunk, 'rewrite_images'):
        return False
    try:
        chunk.rewrite_images(dpi_target=NEN_ANH_DPI, quality=NEN_ANH_QUALITY,
                             set_to_gray=NEN_ANH_XAM)
        return True
    except Exception:
        return False


def _make_chunk_pdf(src_path, start0, end0):
    """Tạo file PDF tạm chứa các trang [start0, end0] (0-based, gồm cả 2 đầu).
    Trả về đường dẫn file tạm; người gọi có trách nhiệm xoá."""
    src = pymupdf.open(src_path)
    chunk = pymupdf.open()
    chunk.insert_pdf(src, from_page=start0, to_page=end0)

    fd, tmp = tempfile.mkstemp(suffix=".pdf", prefix="pdf2md_chunk_")
    os.close(fd)
    # Chỉ bỏ công nén với cụm thật sự nặng: nén tốn ~15s CPU cho 40 trang, không
    # đáng với cụm vài trăm KB vốn upload đã xong trong nháy mắt.
    truoc = len(chunk.tobytes()) if NEN_ANH_TU_MB > 0 else 0
    if truoc >= NEN_ANH_TU_MB * 1_000_000 and _nen_anh_trong_cum(chunk):
        chunk.save(tmp, garbage=3, deflate=True)
        sau = os.path.getsize(tmp)
        if sau < truoc:
            print(f"🗜️  Nén ảnh cụm: {truoc/1e6:.1f} -> {sau/1e6:.1f} MB "
                  f"(nhẹ băng thông, KHÔNG đổi số token)")
        else:  # nén không ăn thua thì quay lại bản gốc cho chắc
            chunk.close()
            chunk = pymupdf.open()
            chunk.insert_pdf(src, from_page=start0, to_page=end0)
            chunk.save(tmp)
    else:
        chunk.save(tmp)

    chunk.close()
    src.close()
    return tmp


def _submanifest(saved_imgs, start0, end0):
    """Lọc manifest hình về đúng cụm trang và ĐỔI số trang sang cục bộ trong cụm
    (trang đầu cụm = 1) để Gemini đặt ảnh đúng chỗ khi chỉ thấy các trang trong cụm."""
    sub = {}
    for page, files in saved_imgs.items():
        if start0 + 1 <= page <= end0 + 1:
            sub[page - start0] = files
    return sub


# --- Phụ lục scan: chụp ảnh nguyên trang --------------------------------------

def render_annex_pages(doc, assets_dir, base_name, dpi=ANNEX_DPI):
    """Chụp ảnh nguyên trang (xám, DPI thấp) cho các trang scan thuần ảnh -
    hợp đồng, chứng nhận đăng ký kinh doanh, Kbis... Những trang này model
    không nên chép toàn văn (làm vỡ trần token) mà chỉ tóm tắt kèm ảnh gốc.

    Trả về dict {so_trang_1based: duong_dan_tuong_doi_tu_assets_dir}."""
    slug = image_extractor.slugify(base_name)
    subdir = os.path.join(assets_dir, slug)
    try:
        os.makedirs(subdir, exist_ok=True)
    except Exception:
        return {}
    zoom = dpi / 72.0
    matrix = pymupdf.Matrix(zoom, zoom)
    out = {}
    for p0 in range(doc.page_count):
        try:
            if len(doc[p0].get_text().strip()) > SCAN_PAGE_MAX_CHARS:
                continue
            name = f"page-{p0+1:04d}-full.png"
            path = os.path.join(subdir, name)
            if not os.path.exists(path):
                pix = doc[p0].get_pixmap(matrix=matrix, colorspace=pymupdf.csGRAY)
                pix.save(path)
            out[p0 + 1] = f"{slug}/{name}"
        except Exception:
            continue
    return out


def _annex_manifest(annex_imgs, start0, end0,
                    assets_dirname=image_extractor.ASSETS_DIRNAME):
    """Đoạn prompt liệt kê ảnh nguyên trang của các trang phụ lục trong cụm."""
    sub = {p - start0: f for p, f in annex_imgs.items() if start0 + 1 <= p <= end0 + 1}
    if not sub:
        return ""
    lines = [
        "",
        "PHỤ LỤC ẢNH NGUYÊN TRANG (trang scan thuần ảnh, ĐÃ CHỤP SẴN):",
        "Các trang dưới đây là bản scan giấy tờ (hợp đồng, chứng nhận đăng ký "
        "kinh doanh, quyết định, Kbis...). Với các trang này KHÔNG chép toàn văn. "
        "Thay vào đó ghi một mục ngắn gồm: tiêu đề giấy tờ, số hiệu/số hợp đồng, "
        "các bên, giá trị, ngày tháng - rồi chèn NGAY thẻ ảnh Markdown "
        "`![Trang N - mô tả](" + assets_dirname + "/TÊN-FILE)` dùng ĐÚNG tên file "
        "liệt kê bên dưới. TUYỆT ĐỐI không được bỏ trắng trang nào trong danh sách này.",
    ]
    for page in sorted(sub):
        lines.append(f"- Trang {page}: {sub[page]}")
    lines.append("")
    return "\n".join(lines)


# --- Lập kế hoạch chia cụm ----------------------------------------------------

def plan_chunks(doc, max_pages=CHUNK_MAX_PAGES, max_chars=CHUNK_MAX_CHARS,
                min_pages=CHUNK_MIN_PAGES):
    """Gom trang thành cụm sao cho mỗi cụm <= max_pages trang VÀ <= max_chars
    ký tự lớp text. Trả về list [(start0, end0), ...]."""
    chunks = []
    start0 = 0
    chars = 0
    for p0 in range(doc.page_count):
        try:
            n = len(doc[p0].get_text())
        except Exception:
            n = 0
        pages_so_far = p0 - start0
        if pages_so_far >= min_pages and (
                pages_so_far >= max_pages or chars + n > max_chars):
            chunks.append((start0, p0 - 1))
            start0 = p0
            chars = 0
        chars += n
    if start0 < doc.page_count:
        chunks.append((start0, doc.page_count - 1))
    return chunks


# --- Cache theo cụm để chạy lại chỉ tốn API cho phần hỏng ----------------------

def _cache_dir(base):
    return os.path.join(OUTPUT_DIR, '.pdf2md_cache', image_extractor.slugify(base))


def _cache_path(base, start0, end0):
    return os.path.join(_cache_dir(base), f"p{start0+1:04d}-{end0+1:04d}.md")


def _cache_get(base, start0, end0):
    if os.environ.get('PDF2MD_NOCACHE') == '1':
        return None
    path = _cache_path(base, start0, end0)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8') as fh:
            return fh.read()
    except Exception:
        return None


def _cache_put(base, start0, end0, text):
    try:
        os.makedirs(_cache_dir(base), exist_ok=True)
        with open(_cache_path(base, start0, end0), 'w', encoding='utf-8') as fh:
            fh.write(text)
    except Exception:
        pass


def _fmt_ranges(pages):
    """Gom [1,2,3,7,8] thành '1-3, 7-8' cho dễ đọc."""
    if not pages:
        return ""
    pages = sorted(set(pages))
    out, s, p = [], pages[0], pages[0]
    for x in pages[1:]:
        if x == p + 1:
            p = x
        else:
            out.append((s, p))
            s = p = x
    out.append((s, p))
    return ', '.join(str(a) if a == b else f"{a}-{b}" for a, b in out)


# --- Chuyển đổi một dải trang, tự kiểm tra và tự sửa --------------------------

class _Ctx:
    def __init__(self, be_key, model, pdf_path, base, doc, saved_imgs,
                 annex_imgs, prompt):
        self.be_key = be_key
        self.model = model
        self.pdf_path = pdf_path
        self.base = base
        self.doc = doc
        self.saved_imgs = saved_imgs
        self.annex_imgs = annex_imgs
        self.prompt = prompt


def convert_range(ctx, start0, end0, depth=0):
    """Chuyển một dải trang sang markdown, ĐỐI CHIẾU lại từng trang, và tự chia
    nhỏ chạy lại phần thiếu. Trả về (markdown, danh_sach_trang_van_thieu)."""
    cached = _cache_get(ctx.base, start0, end0)
    if cached is not None:
        print(f"♻️  Dùng lại cache trang {start0+1}-{end0+1}")
        return cached, []

    label = f" (trang {start0+1}-{end0+1})"
    chunk_prompt = (ctx.prompt
                    + image_extractor.build_prompt_manifest(
                        _submanifest(ctx.saved_imgs, start0, end0))
                    + _annex_manifest(ctx.annex_imgs, start0, end0))
    tmp = _make_chunk_pdf(ctx.pdf_path, start0, end0)
    try:
        text, _truncated = _gemini_convert_file(ctx.be_key, ctx.model, tmp,
                                                chunk_prompt, label)
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass

    missing = _pages_missing(ctx.doc, start0, end0, text)
    if not missing:
        _cache_put(ctx.base, start0, end0, text or "")
        return text or "", []

    n_pages = end0 - start0 + 1
    print(f"🔍 Thiếu {len(missing)}/{n_pages} trang ở dải {start0+1}-{end0+1}: "
          f"{_fmt_ranges(missing)}")

    if depth >= MAX_SPLIT_DEPTH or n_pages <= 1:
        marker = (f"\n\n<!-- ⚠️ VẪN THIẾU TRANG {_fmt_ranges(missing)} "
                  f"sau {depth+1} lần thử -->\n\n")
        return (text or "") + marker, missing

    # Ca 1: phần thiếu nằm gọn ở ĐUÔI (dấu hiệu bị cắt cụt) -> giữ nguyên phần
    # đã sinh, chỉ chạy lại đúng phần đuôi. Không tốn API cho phần đã tốt.
    if text and min(missing) > start0 + 1 and \
            set(missing) == set(range(min(missing), end0 + 2)):
        cut0 = min(missing) - 1
        print(f"   ↳ Phần thiếu ở đuôi -> giữ trang {start0+1}-{cut0}, "
              f"chạy lại {cut0+1}-{end0+1}")
        tail, still = convert_range(ctx, cut0, end0, depth + 1)
        merged = (text + "\n\n" + tail).strip()
        if not still:
            _cache_put(ctx.base, start0, end0, merged)
        return merged, still

    # Ca 2: thủng ở giữa hoặc mất cả cụm -> bổ đôi dải trang rồi chạy lại.
    mid = start0 + (n_pages // 2) - 1
    if mid < start0:
        mid = start0
    print(f"   ↳ Bổ đôi: {start0+1}-{mid+1} và {mid+2}-{end0+1}")
    left, ml = convert_range(ctx, start0, mid, depth + 1)
    right, mr = convert_range(ctx, mid + 1, end0, depth + 1)
    merged = (left + "\n\n" + right).strip()
    still = ml + mr
    if not still:
        _cache_put(ctx.base, start0, end0, merged)
    return merged, still


PROMPT = (
    "Đóng vai chuyên gia phân tích dữ liệu. Chuyển đổi tài liệu PDF scan này sang định dạng Markdown.\n"
    "YÊU CẦU NGHIÊM NGẶT:\n"
    "0. BẮT BUỘC xử lý HẾT MỌI TRANG của tệp, theo đúng thứ tự, KHÔNG được bỏ qua hay gộp tắt bất kỳ trang nào - kể cả trang phụ lục, trang scan mờ hay trang lặp nội dung.\n"
    "1. BẮT BUỘC CHỈ trả về văn bản Markdown. Không bổ sung câu chào hỏi hay giải thích.\n"
    "2. BẢNG BIỂU: Phải dùng cú pháp Markdown Table chuẩn (| Cột 1 | Cột 2 |). Nếu chữ trong một ô bị xuống dòng, CHỈ dùng thẻ <br> để ngắt dòng, tuyệt đối không dùng phím Enter/xuống dòng thực tế làm vỡ bảng. Không dùng bất kỳ thẻ HTML nào khác ngoài <br>.\n"
    "3. CÔNG THỨC TOÁN HỌC: Bắt buộc sử dụng cú pháp LaTeX chuẩn.\n"
    "   - Công thức nội tuyến (nằm cùng dòng văn bản) phải bọc bằng dấu $, ví dụ: $A = B + C$.\n"
    "   - Công thức độc lập (nằm riêng một dòng) phải bọc bằng dấu $$, ví dụ: $$x = \\frac{y}{z}$$.\n"
    "4. LÀM SẠCH: Bỏ qua toàn bộ các đường kẻ ngang rác, dấu chấm lửng (....) hoặc gạch dưới (___) sinh ra do lỗi scan định dạng.\n"
    "5. HÌNH ẢNH & BIỂU ĐỒ: Khi phát hiện biểu đồ, sơ đồ kỹ thuật hay hình minh hoạ (ví dụ: đường cong P-y, mặt cắt địa chất, sơ đồ móng cọc...), BẮT BUỘC chèn thẻ hình theo cú pháp `![Mô tả ngắn gọn](assets/Ten-file-khong-dau.png)` tại đúng vị trí hình xuất hiện. Nếu có phần PHỤ LỤC HÌNH ẢNH liệt kê tên file bên dưới, PHẢI dùng đúng tên file đó, không được bịa tên khác."
)


def process():
    load_dotenv(os.path.join(BASE_DIR, '.env'))
    be_key = gemini_pool.pool()
    if not be_key.keys:
        print("❌ Chưa khai báo API key nào trong .env "
              "(GEMINI_API_KEY hoặc GEMINI_API_KEY_FREE_1/_PAID).")
        return 1
    model_name = os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    so_free = sum(1 for k in be_key.keys if not k.tra_phi)
    print(f"⚙️  Model: {model_name} | Bể key: {so_free} free + "
          f"{len(be_key.keys) - so_free} trả phí (ưu tiên free trước)")

    target = sys.argv[1] if len(sys.argv) > 1 else "ALL"
    if target == "ALL":
        files = glob.glob(os.path.join(INPUT_DIR, '*.pdf'))
    else:
        file_path = os.path.join(INPUT_DIR, target)
        if not os.path.exists(file_path):
            print(f"❌ Khong tim thay file: {target}")
            return 1
        files = [file_path]

    co_thieu = False
    for f in files:
        base = os.path.splitext(os.path.basename(f))[0]
        out_path = os.path.join(OUTPUT_DIR, f"{base}_scan.md")
        if os.path.exists(out_path) and not FORCE:
            continue
        print(f"\n🤖 [PDF Scan Gemini] Dang xu ly: {base}...")

        # Bóc tách hình/biểu đồ ra assets/<ten-file>/ (local, zero token) rồi
        # liệt kê tên file vào prompt để Gemini chèn đúng thẻ ảnh Markdown.
        saved_imgs = image_extractor.extract_images(f, ASSETS_DIR, base_name=base)
        if saved_imgs:
            total = sum(len(v) for v in saved_imgs.values())
            print(f"🖼️  Đã tách {total} hình/biểu đồ vào assets/{image_extractor.slugify(base)}/")

        try:
            doc = pymupdf.open(f)
        except Exception as e:
            co_thieu = True
            print(f"❌ Không mở được PDF: {e}")
            continue

        try:
            annex_imgs = render_annex_pages(doc, ASSETS_DIR, base)
            if annex_imgs:
                print(f"📑 Đã chụp {len(annex_imgs)} trang phụ lục scan thuần ảnh "
                      f"(tóm tắt + chèn ảnh, không chép toàn văn).")

            chunks = plan_chunks(doc)
            print(f"📄 Tài liệu {doc.page_count} trang -> {len(chunks)} cụm "
                  f"(chia động theo mật độ chữ, trần {CHUNK_MAX_CHARS} ký tự/cụm).")

            ctx = _Ctx(be_key, model_name, f, base, doc, saved_imgs, annex_imgs, PROMPT)
            parts, thieu = [], []
            for ci, (s0, e0) in enumerate(chunks):
                n_chars = sum(len(doc[p].get_text()) for p in range(s0, e0 + 1))
                print(f"\n── Cụm {ci+1}/{len(chunks)}: trang {s0+1}-{e0+1} "
                      f"({n_chars} ký tự)")
                text, missing = convert_range(ctx, s0, e0)
                parts.append(text)
                thieu.extend(missing)

            if any(p.strip() for p in parts):
                with open(out_path, 'w', encoding='utf-8') as out:
                    out.write("\n\n".join(parts))
                if thieu:
                    co_thieu = True
                    print(f"\n⚠️ Đã tạo {base}_scan.md NHƯNG còn thiếu "
                          f"{len(set(thieu))} trang: {_fmt_ranges(thieu)}")
                    print("   👉 Tìm dấu ⚠️ trong file để tới đúng chỗ thiếu.")
                else:
                    print(f"\n✅ Đã tạo thành công: {base}_scan.md ({len(chunks)} cụm, "
                          f"đủ {doc.page_count} trang, Model: {model_name})")
            else:
                co_thieu = True
                print("❌ Không tạo được nội dung cho tài liệu này.")
        except Exception as e:
            co_thieu = True
            print(f"❌ Lỗi tổng thể: {e}")
        finally:
            doc.close()

    print()
    print(be_key.tong_ket())
    return EXIT_THIEU_TRANG if co_thieu else 0


if __name__ == "__main__":
    sys.exit(process() or 0)
