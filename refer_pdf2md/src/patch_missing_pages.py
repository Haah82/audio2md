"""Dò các trang PDF bị thiếu trong file Markdown đã xuất, chạy lại đúng những
trang đó rồi vá vào đúng vị trí - KHÔNG dựng lại cả file.

Dùng khi một lần chuyển đổi cũ bị mất trang (cụm hỏng, model cắt cụt...) mà
phần còn lại vẫn tốt: chỉ tốn API cho phần thiếu thay vì chạy lại toàn bộ.

CÁCH DÙNG
    python src/patch_missing_pages.py <đường-dẫn> [tuỳ chọn]

<đường-dẫn> nhận một trong ba dạng, tự tìm nốt vế còn lại:
    - file .pdf trong data/input   -> tự tìm file _scan.md tương ứng
    - file _scan.md trong data/output -> tự tìm file .pdf gốc
    - một thư mục                  -> quét mọi cặp .md/.pdf bên trong

TUỲ CHỌN
    --dry-run       Chỉ báo cáo trang thiếu, không gọi API, không sửa file
    --yes           Vá luôn, không hỏi xác nhận (dùng khi chạy tự động)
    --only 1-40,158 Chỉ vá đúng những trang này (giao với phần dò được)
    --skip 469,472  Bỏ qua những trang này dù bị báo thiếu
    --no-annex      Không chụp ảnh nguyên trang cho phụ lục scan (nhanh, nhẹ đĩa)

VÍ DỤ
    # 1. Xem thử thiếu những trang nào (miễn phí, không gọi API)
    python src/patch_missing_pages.py "data/input/afd/AFD-Tuan Giao.pdf" --dry-run
    # 2. Vá đúng phần thiếu
    python src/patch_missing_pages.py "data/input/afd/AFD-Tuan Giao.pdf" --yes
    # 3. Quét vá cả thư mục
    python src/patch_missing_pages.py data/output/afd --yes

CÁCH DÒ: kết hợp ba bằng chứng độc lập - (1) tìm tự do toàn file, chắc chắn
nhưng bỏ sót trang có nội dung trùng lặp; (2) gióng chuỗi tối ưu bằng quy hoạch
động, bắt được cả cụm mất nhưng hay báo nhầm khi model đảo đoạn; (3) trang không
xếp được vào chuỗi mà mọi chỗ khớp đều đã bị trang khác chiếm. Những trang có
lớp text không đáng tin (scan phủ kín trang, font hỏng ligature hoặc thiếu bảng
ToUnicode) bị loại khỏi phép đối chiếu để không báo thiếu giả.
"""

import os
import sys
import glob
import importlib.util
import re

import pymupdf

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import image_extractor  # noqa: E402


def _load_scan_module():
    """3_pdf_scan.py bắt đầu bằng chữ số nên không import được bằng tên."""
    spec = importlib.util.spec_from_file_location(
        'pdf_scan', os.path.join(_HERE, '3_pdf_scan.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


scan = _load_scan_module()

# Số từ của một "câu mẫu" - phải khớp _page_probes trong 3_pdf_scan.py.
_PROBE_WORDS = 9
# Hai vị trí khớp cách nhau <= ngần này dòng thì coi là cùng một chỗ trong file.
_CLUSTER_LINES = 25
# Hai cụm thiếu cách nhau <= ngần này trang thì gộp làm một lượt gọi API.
_MERGE_GAP = 2


def _shingle_index(md_lines, words=_PROBE_WORDS):
    """Đánh chỉ mục mọi cụm `words` từ liên tiếp của file Markdown -> số dòng.

    Chỉ mục chạy trên DÒNG TỪ liên tục của cả file (không cắt theo dòng) nên câu
    mẫu vắt qua hai dòng markdown vẫn khớp; tra cứu bằng dict nên nhanh.
    """
    tokens, tok_line = [], []
    for li, line in enumerate(md_lines):
        for w in scan._norm(line).split():
            tokens.append(w)
            tok_line.append(li)
    index = {}
    for i in range(len(tokens) - words + 1):
        index.setdefault(' '.join(tokens[i:i + words]), []).append(tok_line[i])
    return index


def _page_candidates(probes, index, cluster=_CLUSTER_LINES):
    """Gom các vị trí khớp của một trang thành vài "chỗ ứng viên".

    Trả về [(dong_dai_dien, so_cau_mau_khop), ...]. Nội dung lặp lại ở nơi khác
    sinh thêm ứng viên chứ không làm sai lệch - bước gióng sau sẽ chọn chỗ nào
    hợp thứ tự trang nhất.
    """
    hits = {}
    for pi, probe in enumerate(probes):
        for line in index.get(probe, ()):
            hits.setdefault(line, set()).add(pi)
    if not hits:
        return []
    cands = []
    cur_start = cur_end = None
    cur_probes = set()
    for line in sorted(hits):
        if cur_start is not None and line - cur_end <= cluster:
            cur_end = line
            cur_probes |= hits[line]
        else:
            if cur_start is not None:
                cands.append((cur_start, len(cur_probes)))
            cur_start = cur_end = line
            cur_probes = set(hits[line])
    cands.append((cur_start, len(cur_probes)))
    return cands


def align_pages(doc, md_lines):
    """Gióng trang PDF vào dòng markdown bằng phép gióng chuỗi tối ưu.

    Mỗi trang có thể khớp ở nhiều chỗ (tài liệu này lặp nguyên bảng dự án giữa
    các công ty thành viên). Ta chọn dãy vị trí KHÔNG GIẢM theo số trang sao cho
    tổng số câu mẫu khớp là lớn nhất - trang nào không nằm trong dãy đó mới thực
    sự là trang thiếu. Cách này không bị trôi khi tài liệu có đoạn dài toàn
    trang scan (không đối chiếu được), khác hẳn kiểu dò cửa sổ trượt.

    Trả về (vi_tri, khong_kiem_tra_duoc, cac_cho_ung_vien).
    """
    index = _shingle_index(md_lines)
    items = []  # (trang, dong, trong_so)
    unverifiable = set()
    for p0 in range(doc.page_count):
        probes = scan.cau_mau_cua(doc, p0)
        if not probes:
            unverifiable.add(p0 + 1)
            continue
        for line, weight in _page_candidates(probes, index):
            items.append((p0 + 1, line, weight))

    if not items:
        return {}, unverifiable, {}

    # Quy hoạch động: chuỗi con tăng dần theo (trang, dòng) có tổng trọng số lớn
    # nhất. Bản đầu duyệt đôi O(n^2) chạy ổn với tài liệu 475 trang (~16s) nhưng
    # tắc nghẽn với tài liệu lớn có nhiều đoạn lặp (số ứng viên phình theo). Đây
    # là "weighted LIS", giải được bằng cây Fenwick tra max tiền tố -> O(n log n).
    items.sort(key=lambda t: (t[0], t[1]))
    n = len(items)
    best = [0.0] * n
    prev = [-1] * n

    dong_sx = sorted({t[1] for t in items})
    chi_so = {d: i + 1 for i, d in enumerate(dong_sx)}   # Fenwick đánh số từ 1
    m = len(dong_sx)
    cay_gt = [0.0] * (m + 1)      # giá trị lớn nhất
    cay_vt = [-1] * (m + 1)       # chỉ số item đạt giá trị đó

    def tra_max(i):
        """Max của mọi item đã nạp có dòng <= dong_sx[i-1]."""
        gt, vt = 0.0, -1
        while i > 0:
            if cay_gt[i] > gt:
                gt, vt = cay_gt[i], cay_vt[i]
            i -= i & (-i)
        return gt, vt

    def nap(i, gt, vt):
        while i <= m:
            if gt > cay_gt[i]:
                cay_gt[i], cay_vt[i] = gt, vt
            i += i & (-i)

    # Nạp theo TỪNG TRANG: item của cùng một trang không được nối vào nhau
    # (một trang chỉ chiếm đúng một chỗ), nên chỉ nạp sau khi tính xong cả trang.
    i = 0
    while i < n:
        j = i
        while j < n and items[j][0] == items[i][0]:
            j += 1
        for k2 in range(i, j):
            _, li, wi = items[k2]
            gt, vt = tra_max(chi_so[li])
            best[k2] = gt + wi
            prev[k2] = vt
        for k2 in range(i, j):
            nap(chi_so[items[k2][1]], best[k2], k2)
        i = j

    k = max(range(n), key=lambda i: best[i])
    pos = {}
    while k != -1:
        page, line, _ = items[k]
        pos[page] = line
        k = prev[k]

    cands = {}
    for page, line, weight in items:
        cands.setdefault(page, []).append(line)
    return pos, unverifiable, cands


def lac_cho_dung(doc, pos, unverifiable, cands, cluster=_CLUSTER_LINES):
    """Trang không xếp được vào chuỗi VÀ mọi chỗ khớp của nó đều ĐÃ BỊ TRANG KHÁC
    CHIẾM -> trang đó thật sự mất, cái ta thấy chỉ là bản sao nội dung ở nơi khác.

    Phân biệt hai kiểu "không xếp được vào chuỗi":
      - model đảo/gộp đoạn: trang vẫn có chỗ khớp RIÊNG, chưa trang nào chiếm,
        chỉ là phép quy hoạch động chọn đường khác -> KHÔNG thiếu.
      - trang mất mà nội dung trùng lặp: chỗ duy nhất khớp lại chính là chỗ của
        trang sinh đôi với nó -> ĐÚNG là thiếu.
    """
    da_chiem = sorted(pos.values())
    ket_qua = set()
    for p in range(1, doc.page_count + 1):
        if p in pos or p in unverifiable:
            continue
        cho = cands.get(p, ())
        if cho and all(any(abs(line - c) <= cluster for c in da_chiem)
                       for line in cho):
            ket_qua.add(p)
    return ket_qua


def free_missing_pages(doc, md):
    """Trang mà HẦU HẾT câu mẫu không xuất hiện Ở BẤT KỲ ĐÂU trong markdown.

    Đây là bằng chứng chắc chắn nhất về trang bị mất (không thể do model sắp xếp
    lại nội dung). Ngược lại nó bỏ sót những trang bị mất mà nội dung tình cờ
    trùng với chỗ khác trong tài liệu - phần đó để phép gióng chuỗi lo.
    """
    return set(scan._pages_missing(doc, 0, doc.page_count - 1, md))


def collect_missing(doc, md, pos, unverifiable, cands=None):
    """Kết hợp ba bằng chứng để chốt danh sách trang thiếu.

    - `free`: trang không tìm thấy ở bất kỳ đâu -> chắc chắn thiếu.
    - `lac_cho_dung`: trang không xếp được vào chuỗi và cũng không khớp ở đúng
      khoảng của nó -> bắt được trang mất mà nội dung trùng lặp chỗ khác.
    - phép gióng chuỗi: những trang còn lại không xếp được. Một mình nó hay báo
      nhầm (model gộp/đảo đoạn), nên chỉ lấy những DẢI liền nhau có chứa ít nhất
      một trang thuộc hai nhóm trên - đủ để kéo về cả cụm 40 trang đầu của AFD.
    Các trang scan thuần ảnh chỉ dùng để NỐI phần giữa của một dải, không bao giờ
    làm đầu hay cuối dải, để tránh nuốt cả chục trang phụ lục vốn vẫn còn nguyên.
    """
    free = set(free_missing_pages(doc, md))
    # `lac_cho_dung` bat duoc ca hiem (trang mat ma noi dung trung lap o cho
    # khac) NHUNG do tren tai lieu P-y no bao nham trang 43 dang con nguyen ven
    # 10/10 cau mau. Duong tinh gia vua ton tien goi API vua chen noi dung trung
    # vao file dang tot, nen mac dinh TAT; bat lai bang PDF2MD_DO_TRUNG_LAP=1
    # khi that su nghi ngo tai lieu bi mat trang co ban sao o noi khac.
    if cands is not None and os.environ.get('PDF2MD_DO_TRUNG_LAP') == '1':
        free |= lac_cho_dung(doc, pos, unverifiable, cands)
    chain_missing = [p for p in range(1, doc.page_count + 1)
                     if p not in pos and p not in unverifiable]
    chain_set = set(chain_missing)

    missing = set(free)
    i = 0
    while i < len(chain_missing):
        start = chain_missing[i]
        end = start
        j = i + 1
        while j < len(chain_missing):
            # Cho phép nối qua các trang scan thuần ảnh nằm xen giữa.
            if all(p in chain_set or p in unverifiable
                   for p in range(end + 1, chain_missing[j])):
                end = chain_missing[j]
                j += 1
            else:
                break
        if any(p in free for p in range(start, end + 1)):
            missing.update(range(start, end + 1))
        i = j
    return missing


def find_gaps(doc, missing_pages, merge_gap=_MERGE_GAP):
    """Gom các trang thiếu thành những dải liền nhau để gọi API theo cụm."""
    missing = sorted(missing_pages)
    if not missing:
        return []
    gaps = []
    start = prev = missing[0]
    for p in missing[1:]:
        if p - prev <= merge_gap + 1:
            prev = p
        else:
            gaps.append((start, prev))
            start = prev = p
    gaps.append((start, prev))
    return gaps


def insert_line_for(gap_start, gap_end, pos, n_lines):
    """Chọn dòng markdown để chèn phần vá: ngay trước chỗ của trang liền sau dải
    thiếu; nếu không có trang nào sau thì chèn xuống cuối file."""
    for p in range(gap_end + 1, max(pos) + 1 if pos else gap_end + 1):
        if p in pos:
            return pos[p]
    return n_lines


def manifest_from_assets(assets_dir, base_name):
    """Dựng lại manifest hình từ các file đã tách sẵn trên đĩa, để KHÔNG phải
    chạy lại extract_images (hàm đó xoá sạch thư mục ảnh cũ trước khi tách)."""
    slug = image_extractor.slugify(base_name)
    subdir = os.path.join(assets_dir, slug)
    saved = {}
    if not os.path.isdir(subdir):
        return saved
    pat = re.compile(r'-p(\d+)\.png$', re.IGNORECASE)
    for name in sorted(os.listdir(subdir)):
        if not name.lower().endswith('.png') or name.startswith('page-'):
            continue
        m = pat.search(name)
        if not m:
            continue
        saved.setdefault(int(m.group(1)), []).append(f"{slug}/{name}")
    return saved


def liet_ke_ung_vien(goc=None):
    """Liệt kê mọi file .md trong data/output có PDF gốc đi kèm để chọn nhanh."""
    goc = goc or os.path.join(os.path.dirname(_HERE), 'data', 'output')
    ket_qua = []
    for md in sorted(glob.glob(os.path.join(goc, '**', '*.md'), recursive=True)):
        if md.endswith('.bak') or '_summary' in os.path.basename(md):
            continue
        pdf = _tim_pdf_cho_md(md)
        if pdf:
            ket_qua.append((pdf, md))
    return ket_qua


def chon_tuong_tac():
    """Hiện danh sách file đã xuất và cho người dùng chọn theo số thứ tự.

    Dùng cho menu trong pdf-2-md.bat: gõ số nhanh hơn nhiều so với kéo thả hoặc
    dán đường dẫn dài có dấu tiếng Việt.
    """
    cap = liet_ke_ung_vien()
    if not cap:
        print("❌ Không thấy file .md nào trong data/output có PDF gốc đi kèm.")
        return []
    print(f"\n📂 Có {len(cap)} tài liệu đã xuất:\n")
    for i, (pdf, md) in enumerate(cap, 1):
        try:
            kb = os.path.getsize(md) / 1024
        except OSError:
            kb = 0
        ten = os.path.relpath(md, os.path.join(os.path.dirname(_HERE), 'data', 'output'))
        print(f"  [{i:2d}] {ten}  ({kb:,.0f} KB)")
    print(f"\n  [0]  Quay lại")
    try:
        tra_loi = input("\nChọn số thứ tự (hoặc 'a' để quét tất cả): ").strip().lower()
    except EOFError:
        return []
    if tra_loi in ('a', 'all', 'tat ca'):
        return cap
    if not tra_loi.isdigit() or not (1 <= int(tra_loi) <= len(cap)):
        return []
    return [cap[int(tra_loi) - 1]]


def parse_ranges(text):
    """Đọc chuỗi kiểu '1-40,158,419-429' thành set số trang."""
    out = set()
    for phan in (text or '').split(','):
        phan = phan.strip()
        if not phan:
            continue
        if '-' in phan:
            a, _, b = phan.partition('-')
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(phan))
    return out


def _tim_md_cho_pdf(pdf_path):
    """data/input/afd/X.pdf -> data/output/afd/X_scan.md (thử cả _native.md)."""
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    thu_muc = os.path.dirname(os.path.abspath(pdf_path))
    ung_vien = []
    # Giữ nguyên cấu trúc thư mục con: .../input/<con>/ -> .../output/<con>/
    doi = re.sub(r'([\\/])input([\\/]|$)', r'\1output\2', thu_muc)
    for d in (doi, thu_muc):
        for hau_to in ('_scan', '_native', ''):
            ung_vien.append(os.path.join(d, f"{base}{hau_to}.md"))
    for p in ung_vien:
        if os.path.exists(p):
            return p
    return None


def _tim_pdf_cho_md(md_path):
    """data/output/afd/X_scan.md -> data/input/afd/X.pdf (tìm đệ quy nếu cần)."""
    base = re.sub(r'_(scan|native)$', '',
                  os.path.splitext(os.path.basename(md_path))[0])
    thu_muc = os.path.dirname(os.path.abspath(md_path))
    doi = re.sub(r'([\\/])output([\\/]|$)', r'\1input\2', thu_muc)
    for d in (doi, thu_muc):
        p = os.path.join(d, base + '.pdf')
        if os.path.exists(p):
            return p
    goc_input = os.path.join(os.path.dirname(_HERE), 'data', 'input')
    for p in glob.glob(os.path.join(goc_input, '**', base + '.pdf'), recursive=True):
        return p
    return None


def ghep_cap(duong_dan):
    """Từ một đường dẫn bất kỳ, trả về danh sách [(pdf, md), ...] để xử lý."""
    duong_dan = os.path.abspath(duong_dan)
    if os.path.isdir(duong_dan):
        cap = []
        for md in sorted(glob.glob(os.path.join(duong_dan, '**', '*.md'),
                                   recursive=True)):
            if md.endswith('.bak') or '_summary' in md:
                continue
            pdf = _tim_pdf_cho_md(md)
            if pdf:
                cap.append((pdf, md))
        return cap
    if duong_dan.lower().endswith('.pdf'):
        md = _tim_md_cho_pdf(duong_dan)
        return [(duong_dan, md)] if md else []
    if duong_dan.lower().endswith('.md'):
        pdf = _tim_pdf_cho_md(duong_dan)
        return [(pdf, duong_dan)] if pdf else []
    return []


def do_thieu(pdf_path, md_path, only=None, skip=None):
    """Dò trang thiếu của một cặp file. Trả về (doc, md, md_lines, pos, gaps, ...)."""
    doc = pymupdf.open(pdf_path)
    with open(md_path, encoding='utf-8') as fh:
        md = fh.read()
    md_lines = md.split('\n')
    pos, unverifiable, cands = align_pages(doc, md_lines)
    missing = collect_missing(doc, md, pos, unverifiable, cands)
    if only:
        missing &= only
    if skip:
        missing -= skip
    return doc, md, md_lines, pos, unverifiable, find_gaps(doc, missing)


def va_mot_file(pdf_path, md_path, opts):
    """Dò rồi vá một cặp PDF/Markdown. Trả về mã thoát."""
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    out_dir = os.path.dirname(os.path.abspath(md_path))
    assets_dir = os.path.join(out_dir, image_extractor.ASSETS_DIRNAME)

    doc, md, md_lines, pos, unverifiable, gaps = do_thieu(
        pdf_path, md_path, opts.get('only'), opts.get('skip'))

    print(f"\n📄 {os.path.basename(md_path)}")
    print(f"   PDF {doc.page_count} trang | Markdown {len(md_lines)} dòng")
    print(f"   Đã có {len(pos)} trang | {len(unverifiable)} trang scan thuần ảnh "
          f"(không đối chiếu được bằng chữ)")
    if not gaps:
        print("   ✅ Không phát hiện trang nào bị thiếu.")
        return 0
    tong = sum(e - s + 1 for s, e in gaps)
    print(f"   ⚠️ Thiếu {tong} trang, {len(gaps)} dải: "
          + ', '.join(f"{s}-{e}" if s != e else str(s) for s, e in gaps))
    if opts.get('dry'):
        return 0

    if not opts.get('yes'):
        try:
            tra_loi = input(f"   Vá {tong} trang này (tốn ~{len(gaps)}+ lượt API)? [y/N] ")
        except EOFError:
            tra_loi = ''
        if tra_loi.strip().lower() not in ('y', 'yes'):
            print("   ⏭️  Bỏ qua.")
            return 0

    be_key = scan.gemini_pool.pool()
    if not be_key.keys:
        print("❌ Chưa khai báo API key nào trong .env "
              "(GEMINI_API_KEY hoặc GEMINI_API_KEY_FREE_1/_PAID).")
        return 1
    model_name = (os.getenv("GEMINI_MODEL") or scan.DEFAULT_MODEL).strip()
    so_free = sum(1 for k in be_key.keys if not k.tra_phi)
    print(f"⚙️  Model: {model_name} | Bể key: {so_free} free + "
          f"{len(be_key.keys) - so_free} trả phí")

    saved_imgs = manifest_from_assets(assets_dir, base)
    print(f"🖼️  Dùng lại {sum(len(v) for v in saved_imgs.values())} hình đã tách sẵn.")
    annex_imgs = {}
    if not opts.get('no_annex'):
        # Chỉ chụp ảnh nguyên trang cho những trang SẮP VÁ, tránh sinh cả trăm
        # file ảnh cho phần tài liệu vốn đã tốt.
        can_va = {p for s, e in gaps for p in range(s, e + 1)}
        annex_imgs = {p: f for p, f in
                      scan.render_annex_pages(doc, assets_dir, base).items()
                      if p in can_va}
        if annex_imgs:
            print(f"📑 {len(annex_imgs)} trang phụ lục scan sẽ được tóm tắt + chèn ảnh.")

    ctx = scan._Ctx(be_key, model_name, pdf_path, base, doc, saved_imgs,
                    annex_imgs, scan.PROMPT)

    # Vá từ DƯỚI LÊN để chỉ số dòng của các dải phía trên không bị xê dịch.
    con_thieu = []
    for start, end in sorted(gaps, reverse=True):
        print(f"\n── Vá trang {start}-{end}")
        text, missing = scan.convert_range(ctx, start - 1, end - 1)
        if not (text or '').strip():
            print(f"❌ Không lấy được nội dung trang {start}-{end}, bỏ qua.")
            con_thieu.extend(range(start, end + 1))
            continue
        con_thieu.extend(missing)
        at = insert_line_for(start, end, pos, len(md_lines))
        block = ["", f"<!-- ▼ VÁ BỔ SUNG TRANG {start}-{end} -->", ""]
        block += text.strip().split('\n')
        block += ["", f"<!-- ▲ HẾT PHẦN VÁ TRANG {start}-{end} -->", ""]
        md_lines[at:at] = block
        print(f"   ↳ Đã chèn {len(block)} dòng tại dòng {at+1}")

    # Bỏ dấu cảnh báo cũ của lần chạy hỏng trước, giờ đã có nội dung thay thế.
    md_lines = [l for l in md_lines if 'THẤT BẠI, THIẾU NỘI DUNG' not in l]

    backup = md_path + '.bak'
    if not os.path.exists(backup):
        with open(backup, 'w', encoding='utf-8') as fh:
            fh.write(md)
        print(f"\n💾 Đã lưu bản gốc: {os.path.basename(backup)}")
    with open(md_path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(md_lines))
    doc.close()

    print()
    print(be_key.tong_ket())
    if con_thieu:
        print(f"\n⚠️ Vẫn còn thiếu: {scan._fmt_ranges(con_thieu)}")
        return scan.EXIT_THIEU_TRANG
    print(f"\n✅ Đã vá xong {tong} trang vào {os.path.basename(md_path)}")
    return 0


def _lay_gia_tri(co, mac_dinh=None):
    """Đọc giá trị của tuỳ chọn dạng '--only 1-40' hoặc '--only=1-40'."""
    for i, a in enumerate(sys.argv):
        if a == co and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith(co + '='):
            return a.split('=', 1)[1]
    return mac_dinh


def main():
    co_gia_tri = {'--only', '--skip'}
    args = []
    bo_qua = False
    for i, a in enumerate(sys.argv[1:]):
        if bo_qua:
            bo_qua = False
            continue
        if a in co_gia_tri:
            bo_qua = True
            continue
        if not a.startswith('--'):
            args.append(a)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(_HERE), '.env'))

    opts = {
        'dry': '--dry-run' in sys.argv,
        'yes': '--yes' in sys.argv,
        'no_annex': '--no-annex' in sys.argv,
        'only': parse_ranges(_lay_gia_tri('--only')) or None,
        'skip': parse_ranges(_lay_gia_tri('--skip')) or None,
    }

    # Không đưa đường dẫn (hoặc '--chon') thì hiện danh sách cho bấm số - gõ số
    # nhanh hơn hẳn việc dán đường dẫn dài có dấu tiếng Việt từ menu .bat.
    if not args or '--chon' in sys.argv:
        cap = chon_tuong_tac()
        if not cap:
            return 0
    else:
        cap = []
        for duong_dan in args:
            if not os.path.exists(duong_dan):
                print(f"❌ Không thấy: {duong_dan}")
                return 2
            tim = ghep_cap(duong_dan)
            if not tim:
                print(f"❌ Không ghép được cặp PDF/Markdown cho: {duong_dan}")
                print("   Hãy chỉ rõ cả hai: <file.pdf> <file.md>")
                return 2
            cap.extend(tim)

        # Người dùng đưa thẳng cả hai file thì gộp lại thành một cặp.
        if len(args) == 2 and len(cap) == 2 and cap[0][0] == cap[1][0]:
            cap = [cap[0]]

    print(f"🔎 Có {len(cap)} tài liệu để kiểm tra.")
    ma = 0
    for pdf_path, md_path in cap:
        try:
            ma = va_mot_file(pdf_path, md_path, opts) or ma
        except Exception as e:  # noqa: BLE001
            print(f"❌ Lỗi khi xử lý {os.path.basename(md_path)}: {e}")
            ma = 1
    return ma


if __name__ == "__main__":
    sys.exit(main() or 0)
