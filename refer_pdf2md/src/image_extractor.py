"""Bóc tách hình/biểu đồ trong PDF ra thư mục assets/ (local, zero token).

Dùng chung cho 3_pdf_scan.py và 6_gemini_refine.py. Toàn bộ thao tác chạy bằng
PyMuPDF (fitz) ở máy trạm, không tốn token. Sau khi tách xong, danh sách file
hình theo từng trang được truyền vào prompt để Gemini chèn đúng thẻ Markdown
`![mô tả](assets/ten-file.png)` tại vị trí biểu đồ xuất hiện.

CÁCH LÀM: RENDER THEO VÙNG TRANG (không dump object thô).
Lý do (rút ra từ chính tài liệu phân tích cọc P-y):
- Rất nhiều hình được lưu dạng ảnh raster kèm SMask (kênh alpha). Nếu dump thẳng
  object nền bằng doc.extract_image() mà KHÔNG ghép alpha, lớp nền phẳng màu tối
  sẽ cho ra một ô ĐEN kịt (đúng lỗi "hình bị màu đen" ở Figure 29, 30...).
- Một biểu đồ (vd sơ đồ thuật toán) thường bị lưu thành HÀNG CHỤC mảnh raster
  xếp chồng -> dump từng object sẽ làm VỠ một hình thành chục mảnh vụn.
- Nhiều hình khác lại là VECTOR thuần (vd sơ đồ tầng đất tô màu) -> hoàn toàn
  không có object ảnh, dump theo ảnh sẽ BỎ SÓT sạch.

Render vùng trang khắc phục cả ba: gom vùng đồ hoạ (ảnh raster ∪ nét vẽ vector),
tách theo khoảng trắng dọc thành từng hình, rồi chụp đúng vùng đó ở DPI cao ->
ảnh sạch, đúng màu, đúng như hiển thị, mỗi hình một file.

Nguyên tắc an toàn: mọi lỗi đều nuốt êm và trả về rỗng — tách hình là bước phụ
trợ, tuyệt đối không được làm hỏng luồng chuyển đổi chính.
"""

import os
import re
import unicodedata

try:
    import pymupdf as fitz  # PyMuPDF (API mới, tránh cảnh báo deprecated)
except Exception:  # pragma: no cover - môi trường thiếu thư viện
    try:
        import fitz  # bản cũ hơn vẫn dùng tên fitz
    except Exception:
        fitz = None

# Ngưỡng kích thước tối thiểu (điểm PDF, 1pt = 1/72 inch) để coi một vùng đồ hoạ
# là "hình" thực sự, nhằm loại nét kẻ/đường gạch/công thức nội tuyến lẻ tẻ.
_MIN_FIG_WIDTH = 130
_MIN_FIG_HEIGHT = 90
# Khoảng trắng dọc (pt) đủ lớn để coi là ranh giới giữa hai hình khác nhau trên
# cùng một trang. Đo thực nghiệm trên tài liệu: khe trong cùng một hình <= ~22pt,
# khe giữa hai hình tách biệt >= ~85pt. Ngưỡng 45pt tách rất sạch.
_SPLIT_GAP = 45.0
# Vùng phủ hơn ngưỡng này diện tích trang -> coi là nền/scan cả trang, bỏ qua.
_MAX_PAGE_COVER_RATIO = 0.9
# Đệm quanh vùng hình khi render để không cắt cụt nét ở mép (pt).
_PAD = 6.0
# Khoảng chừa tối thiểu (pt) giữa mép ảnh và dòng chữ (caption/thân bài) liền kề,
# để KHÔNG dính chữ hàng dưới (dòng "Figure N ...") hay chữ thân bài hàng trên.
_TEXT_MARGIN = 1.5
# Độ phân giải render (DPI). 200 cho nét chữ/đường sắc mà dung lượng vẫn nhẹ.
_DPI = 200

# Dòng caption thực sự bắt đầu bằng "Figure N" (không tính tham chiếu nội dòng
# kiểu "...(Figure 13)..."). Dùng làm RANH GIỚI CỨNG để tách hai hình xếp sát
# nhau mà giữa chúng chỉ cách nhau đúng một dòng caption (vd Figure 13/14).
_CAPTION_RE = re.compile(r"^\s*Figure\s*\d+", re.IGNORECASE)
# Bắt phần "Figure N" ở đầu caption để cắt bỏ, chỉ giữ phần mô tả làm tóm tắt.
_CAPTION_PREFIX_RE = re.compile(r"^\s*Figure\s*\d+\s*", re.IGNORECASE)
# Số từ tối đa trong phần tóm tắt tên hình (lấy từ caption).
_SUMMARY_MAX_WORDS = 8
# Caption thường nằm ngay DƯỚI hình (tài liệu đặt caption dưới). Khoảng dò caption
# cho một vùng hình: từ hơi trên đáy hình tới _CAPTION_LOOKAHEAD pt bên dưới.
_CAPTION_LOOKAHEAD = 70.0

ASSETS_DIRNAME = "assets"


def slugify(name):
    """Chuẩn hoá tên tài liệu thành chuỗi ASCII không dấu để đặt tên file."""
    name = name.replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    ascii_str = re.sub(r"[^A-Za-z0-9]+", "-", ascii_str).strip("-")
    return ascii_str or "image"


def _graphic_rects(page):
    """Gom toàn bộ hình chữ nhật đồ hoạ trên trang: ảnh raster ∪ nét vẽ vector.

    Bỏ các rect suy biến (mỏng như đường kẻ) và rect phủ gần kín trang (nền/scan).
    """
    page_area = page.rect.width * page.rect.height
    rects = []

    try:
        for img in page.get_images(full=True):
            try:
                rects.extend(page.get_image_rects(img[0]))
            except Exception:
                continue
    except Exception:
        pass

    try:
        for d in page.get_drawings():
            r = d.get("rect")
            if r is not None:
                rects.append(r)
    except Exception:
        pass

    out = []
    for r in rects:
        if r.width <= 1 or r.height <= 1:
            continue  # đường kẻ mảnh
        if page_area and r.width * r.height > _MAX_PAGE_COVER_RATIO * page_area:
            continue  # nền/scan cả trang
        out.append(r)
    return out


def _text_lines(page):
    """Trả về list (y0, y1, text) của mọi dòng chữ trên trang.

    Dùng cho hai việc: (1) tìm dòng caption "Figure N" làm ranh giới tách hình;
    (2) chặn mép ảnh không cho liếm sang dòng chữ liền kề.
    """
    lines = []
    try:
        data = page.get_text("dict")
    except Exception:
        return lines
    for blk in data.get("blocks", []):
        for ln in blk.get("lines", []):
            txt = "".join(s.get("text", "") for s in ln.get("spans", []))
            if txt.strip():
                bb = ln["bbox"]
                lines.append((bb[1], bb[3], txt.strip()))
    return lines


def _figure_regions(page, text_lines, split_gap, min_w, min_h):
    """Chia vùng đồ hoạ của trang thành từng HÌNH riêng.

    Tách khi GẶP một trong hai tín hiệu:
    - khoảng trắng dọc giữa hai cụm đồ hoạ > split_gap, HOẶC
    - có một dòng caption "Figure N" nằm lọt trong khe giữa hai cụm (dấu hiệu
      chắc chắn của hai hình khác nhau, vd Figure 13 và Figure 14 xếp sát nhau).

    Trả về list[Rect] đã lọc theo kích thước tối thiểu, thứ tự từ trên xuống.
    """
    rects = _graphic_rects(page)
    if not rects:
        return []

    caption_ys = [y0 for (y0, y1, t) in text_lines if _CAPTION_RE.match(t)]

    rects.sort(key=lambda r: r.y0)
    bands = []
    current = [rects[0]]
    band_y1 = rects[0].y1

    for r in rects[1:]:
        gap = r.y0 - band_y1
        caption_between = any(band_y1 - 1.0 <= cy <= r.y0 + 1.0 for cy in caption_ys)
        if gap > split_gap or caption_between:
            bands.append(current)
            current = [r]
            band_y1 = r.y1
        else:
            current.append(r)
            band_y1 = max(band_y1, r.y1)
    bands.append(current)

    regions = []
    page_area = page.rect.width * page.rect.height
    for band in bands:
        u = fitz.Rect(band[0])
        for r in band[1:]:
            u |= r
        if u.width < min_w or u.height < min_h:
            continue
        if page_area and u.width * u.height > _MAX_PAGE_COVER_RATIO * page_area:
            continue
        regions.append(u)
    return regions


def _clip_for_region(page, region, text_lines):
    """Tính khung cắt (clip) cho một hình: đệm _PAD nhưng KHÔNG liếm sang dòng chữ.

    Mép dưới bị chặn trên đỉnh dòng chữ gần nhất nằm dưới hình (thường là chính
    caption "Figure N") -> không dính chữ hàng dưới. Mép trên tương tự với dòng
    thân bài phía trên. Chữ NẰM TRONG hình (nhãn trục, chữ trong ảnh chụp) không
    tính vì nó không nằm hẳn trên/dưới vùng hình.
    """
    top = region.y0 - _PAD
    bot = region.y1 + _PAD

    for (ty0, ty1, _t) in text_lines:
        # Dòng chữ nằm hẳn PHÍA TRÊN hình -> chặn mép trên.
        if ty1 <= region.y0 + 2.0:
            top = max(top, ty1 + _TEXT_MARGIN)
        # Dòng chữ nằm hẳn PHÍA DƯỚI hình -> chặn mép dưới.
        if ty0 >= region.y1 - 2.0:
            bot = min(bot, ty0 - _TEXT_MARGIN)

    # Phòng trường hợp chặn quá tay làm khung âm/rỗng: quay về đúng vùng hình.
    if bot <= top:
        top, bot = region.y0, region.y1

    return fitz.Rect(region.x0 - _PAD, top, region.x1 + _PAD, bot) & page.rect


def _caption_for_region(region, text_lines):
    """Tìm dòng caption 'Figure N ...' gắn với một vùng hình (nằm ngay dưới hình).

    Trả về text caption gần nhất bên dưới đáy hình, hoặc None nếu không có.
    """
    best = None
    best_gap = None
    for (y0, _y1, txt) in text_lines:
        if not _CAPTION_RE.match(txt):
            continue
        gap = y0 - region.y1          # >0: caption nằm dưới đáy hình
        if -8.0 <= gap <= _CAPTION_LOOKAHEAD:
            if best_gap is None or abs(gap) < abs(best_gap):
                best_gap = gap
                best = txt
    return best


def _summary_from_caption(caption, max_words=_SUMMARY_MAX_WORDS):
    """Rút tóm tắt không dấu (<= max_words từ) từ caption, bỏ tiền tố 'Figure N'.

    Trả về chuỗi slug (vd 'values-of-coefficients-ac-and-as') hoặc None.
    """
    if not caption:
        return None
    body = _CAPTION_PREFIX_RE.sub("", caption)
    slug = slugify(body)
    if not slug:
        return None
    words = [w for w in slug.split("-") if w]
    return "-".join(words[:max_words]) or None


def _clear_subdir_pngs(subdir):
    """Xoá các PNG cũ trong thư mục con của một tài liệu để chạy lại cho sạch."""
    try:
        for name in os.listdir(subdir):
            if name.lower().endswith(".png"):
                try:
                    os.remove(os.path.join(subdir, name))
                except Exception:
                    pass
    except Exception:
        pass


def extract_images(pdf_path, assets_dir, base_name=None,
                   min_width=_MIN_FIG_WIDTH, min_height=_MIN_FIG_HEIGHT,
                   split_gap=_SPLIT_GAP, dpi=_DPI):
    """Tách hình trong PDF bằng cách RENDER vùng trang, lưu vào thư mục riêng.

    Ảnh của mỗi tài liệu nằm trong thư mục con `<assets_dir>/<ten-tai-lieu>/`,
    đánh số thứ tự toàn tài liệu 1,2,3... kèm tóm tắt lấy từ caption 'Figure N':
    `<so>-<tom-tat>.png` (không có caption thì `<so>-figure-p<trang>.png`).

    Trả về dict: {so_trang_1based: [duong_dan_tuong_doi_1, ...]} trong đó đường
    dẫn tương đối tính từ assets_dir (vd '<ten-tai-lieu>/1-tom-tat.png') để thẻ
    ảnh Markdown thành `![](assets/<ten-tai-lieu>/1-tom-tat.png)`. Trả về {} nếu
    không có hình đạt chuẩn hoặc thiếu thư viện.
    """
    if fitz is None:
        return {}

    base = slugify(base_name or os.path.splitext(os.path.basename(pdf_path))[0])
    subdir = os.path.join(assets_dir, base)

    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return {}

    # Dọn ảnh cũ của chính tài liệu này để lần chạy lại không lẫn file thừa.
    _clear_subdir_pngs(subdir)

    saved = {}
    seq = 0
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    try:
        for pno in range(len(doc)):
            page = doc[pno]
            try:
                text_lines = _text_lines(page)
                regions = _figure_regions(page, text_lines, split_gap,
                                          min_width, min_height)
            except Exception:
                continue
            if not regions:
                continue

            for region in regions:
                clip = _clip_for_region(page, region, text_lines)
                caption = _caption_for_region(region, text_lines)
                summary = _summary_from_caption(caption)
                seq += 1
                if summary:
                    local_name = f"{seq}-{summary}.png"
                else:
                    local_name = f"{seq}-figure-p{pno + 1}.png"
                rel_path = f"{base}/{local_name}"
                try:
                    pix = page.get_pixmap(matrix=matrix, clip=clip)
                    os.makedirs(subdir, exist_ok=True)
                    pix.save(os.path.join(subdir, local_name))
                except Exception:
                    seq -= 1
                    continue
                saved.setdefault(pno + 1, []).append(rel_path)
    finally:
        try:
            doc.close()
        except Exception:
            pass

    return saved


def build_prompt_manifest(saved, assets_dirname=ASSETS_DIRNAME):
    """Sinh đoạn phụ lục để gắn vào prompt Gemini, liệt kê hình theo từng trang.

    Trả về chuỗi rỗng nếu không có hình nào -> khi đó không thêm gì vào prompt.
    """
    if not saved:
        return ""

    lines = [
        "",
        "PHỤ LỤC HÌNH ẢNH ĐÃ TÁCH SẴN (BẮT BUỘC SỬ DỤNG):",
        "Các file hình/biểu đồ dưới đây đã được tách từ chính tài liệu này và lưu "
        f"trong thư mục '{assets_dirname}/'. Khi tới vị trí biểu đồ/sơ đồ tương ứng "
        "trong nội dung, HÃY chèn thẻ ảnh Markdown `![mô tả ngắn](" + assets_dirname +
        "/TÊN-FILE)` dùng ĐÚNG tên file liệt kê bên dưới. TUYỆT ĐỐI không được bịa "
        "tên file khác và không được bỏ sót biểu đồ đã có file.",
    ]
    for page in sorted(saved):
        files = ", ".join(saved[page])
        lines.append(f"- Trang {page}: {files}")
    lines.append("")
    return "\n".join(lines)
