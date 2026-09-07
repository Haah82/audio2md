"""Loi chuyen doi PDF native (co lop text) sang Markdown chat luong cao.

Dung chung cho SecondBrain_Vault va pdf2md. File nay KHONG phu thuoc style_guard
hay cau truc thu muc cua bat ky repo nao, de hai ben giu duoc ban sao giong het.

Boi canh ky thuat (do thuc te tren pymupdf4llm 1.28.2):

1. pymupdf4llm da doi sang "layout engine" moi. Cac tham so cua engine cu
   (margins, table_strategy, fontsize_limit) bi NUOT IM LANG qua **kwargs,
   khong bao loi, khong co tac dung. Module nay tu do engine dang chay va chi
   truyen dung bo tham so ma engine do hieu.

2. Engine moi co header/footer. Dat header=False, footer=False chan duoc so
   trang va tieu de chay chen vao giua van ban ngay tu goc. Tren mot ho so thau
   204 trang, viec nay loai bo 194 cho so trang lac giua cau.

3. Loi nang nhat con lai la "margin heading": tai lieu Word 2 cot (cot trai hep
   chua so muc, cot phai la than bai) bi engine tron lan, lam tieu de vo thanh
   nhieu manh in dam chen giua cau. Khong tham so nao chua duoc. Module nay doc
   toa do that tu PyMuPDF de lay nguyen van tieu de roi dat lai dung cho.

Nguyen tac an toan: moi thao tac tu sua deu duoc ghi vao FixLog de nguoi dung
ra soat lai. Khong bao gio bia noi dung, khong sua so lieu hay dieu khoan.
"""

import os
import re
import time
from dataclasses import dataclass, field

import pymupdf
import pymupdf4llm

import font_viet

VERSION = "2.0"

# Nguong hinh hoc cho viec do cot le trai (ty le tren chieu rong trang).
_MARGIN_MAX_X0_RATIO = 0.35   # khoi le phai bat dau trong 35% ben trai trang
_MARGIN_MIN_GAP = 6.0         # khoi le phai ket thuc truoc than bai it nhat 6pt
_MARGIN_MAX_CHARS = 160       # tieu de le dai hon nguong nay thi coi la than bai
_BODY_MIN_WIDTH_RATIO = 0.40  # khoi than bai phai rong it nhat 40% trang


# --------------------------------------------------------------------- LOG

@dataclass
class FixLog:
    """Ghi lai moi thao tac tu dong sua noi dung de nguoi dung ra soat."""
    entries: list = field(default_factory=list)

    def add(self, kind, detail, page=None):
        self.entries.append({"kind": kind, "detail": detail, "page": page})

    def count(self, kind):
        return sum(1 for e in self.entries if e["kind"] == kind)

    def summary(self):
        kinds = {}
        for e in self.entries:
            kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
        return kinds

    def to_markdown(self, source_name):
        lines = [
            f"# Nhat ky tu dong sua: {source_name}",
            "",
            f"Sinh boi pdf_native_core {VERSION}. Moi muc duoi day la mot cho script da",
            "tu sua. Hay ra soat cac muc CONG THUC va MARGIN HEADING truoc tien.",
            "",
        ]
        s = self.summary()
        if s:
            lines += ["| Loai | So lan |", "|---|---|"]
            for k in sorted(s):
                lines.append(f"| {k} | {s[k]} |")
            lines.append("")
        else:
            lines += ["Khong co thao tac tu sua nao.", ""]
            return "\n".join(lines)

        current = None
        for e in self.entries:
            if e["kind"] != current:
                current = e["kind"]
                lines += ["", f"## {current}", ""]
            loc = f"trang {e['page']}: " if e["page"] else ""
            lines.append(f"- {loc}{e['detail']}")
        lines.append("")
        return "\n".join(lines)


@dataclass
class Result:
    markdown: str
    fixlog: FixLog
    stats: dict


# ------------------------------------------------------- TRICH XUAT (ENGINE)

def _layout_engine_active():
    """Tra ve True neu pymupdf4llm dang dung layout engine moi.

    Khong dua hoan toan vao co private _use_layout: neu co thi tin, neu khong
    thi do bang chu ky ham layout.
    """
    flag = getattr(pymupdf4llm, "_use_layout", None)
    if flag is not None:
        return bool(flag)
    return hasattr(pymupdf4llm, "_layout_to_markdown")


def _engine_kwargs(ocr, ocr_language, show_progress):
    """Chi truyen tham so ma engine dang chay thuc su hieu."""
    kw = {"page_chunks": True, "show_progress": show_progress}
    if _layout_engine_active():
        # Engine moi: chan header/footer ngay tu goc.
        kw.update(header=False, footer=False, use_ocr=bool(ocr))
        if ocr and ocr_language:
            kw["ocr_language"] = ocr_language
    else:
        # Engine cu: khong co header/footer, dung margins de cat vung le.
        kw.update(margins=(0, 56, 0, 56), table_strategy="lines_strict")
    return kw


def _extract_pages(doc, ocr, ocr_language, show_progress, log):
    """Trich xuat markdown theo tung trang, co ha cap dan khi gap loi.

    Tra ve list[str] theo thu tu trang. Moi buoc ha cap deu duoc ghi log de
    nguoi dung biet ban chuyen doi da chay o che do nao.
    """
    attempts = [
        ("day du", _engine_kwargs(ocr, ocr_language, show_progress)),
    ]
    # Ha cap 1: bo ngon ngu OCR tuy chon (tesseract co the thieu goi 'vie').
    if ocr and ocr_language:
        kw = _engine_kwargs(ocr, None, show_progress)
        attempts.append(("bo ocr_language", kw))
    # Ha cap 2: tat han OCR (nhanh hon, van xu ly duoc PDF co lop text).
    attempts.append(("tat OCR", _engine_kwargs(False, None, show_progress)))
    # Ha cap 3: toi thieu, chi page_chunks.
    attempts.append(("toi thieu", {"page_chunks": True}))

    last_err = None
    for label, kw in attempts:
        try:
            chunks = pymupdf4llm.to_markdown(doc, **kw)
        except Exception as e:
            last_err = e
            log.add("ENGINE", f"Che do '{label}' that bai ({type(e).__name__}: {e}), thu che do ke tiep")
            continue
        if label != "day du":
            log.add("ENGINE", f"Da phai ha cap sang che do '{label}'")
        if isinstance(chunks, list):
            return [c.get("text", "") for c in chunks]
        # Phong truong hop page_chunks khong duoc ho tro: coi ca tai lieu la 1 trang.
        log.add("ENGINE", "Engine khong tra ve page_chunks, mat kha nang noi cau qua trang")
        return [str(chunks)]

    raise RuntimeError(f"Khong trich xuat duoc PDF bang bat ky che do nao: {last_err}")


# ------------------------------------------------- HINH HOC: TIEU DE COT LE

def _page_margin_headings(page):
    """Do toa do that de lay tieu de nam o cot le trai cua trang.

    Tai lieu Word 2 cot (so muc ben trai, than bai ben phai) la nguyen nhan
    khien engine chen tieu de vo vun vao giua cau. Doc truc tiep hinh hoc cho
    ta nguyen van tieu de, chinh xac hon moi phong doan tren text.

    Tra ve list[str] theo thu tu doc tren trang.
    """
    try:
        blocks = page.get_text("blocks")
    except Exception:
        return []

    W = page.rect.width
    if not W:
        return []

    items = []
    for b in blocks:
        if len(b) < 5:
            continue
        x0, y0, x1, y1, txt = b[0], b[1], b[2], b[3], b[4]
        txt = " ".join(str(txt).split())
        if txt:
            items.append((x0, y0, x1, y1, txt))
    if len(items) < 2:
        return []

    # Xac dinh moc cot than bai: x0 pho bien nhat trong cac khoi rong.
    wide = [it for it in items if (it[2] - it[0]) >= _BODY_MIN_WIDTH_RATIO * W]
    if not wide:
        return []
    counts = {}
    for x0, _, _, _, _ in wide:
        key = round(x0, 0)
        counts[key] = counts.get(key, 0) + 1
    body_x0 = max(counts, key=lambda k: counts[k])

    # Chi coi la bo cuc 2 cot khi than bai bi day sang phai ro rang.
    if body_x0 < 0.20 * W:
        return []

    headings = []
    for x0, y0, x1, y1, txt in sorted(items, key=lambda it: it[1]):
        if x0 >= body_x0 - _MARGIN_MIN_GAP:
            continue                      # nam trong cot than bai
        if x1 > body_x0 - _MARGIN_MIN_GAP:
            continue                      # tran sang cot than bai -> la than bai
        if x0 > _MARGIN_MAX_X0_RATIO * W:
            continue                      # khong phai le trai (vd so trang o giua)
        if len(txt) > _MARGIN_MAX_CHARS:
            continue
        if txt.startswith("|"):
            continue
        headings.append(txt)
    return headings


def _norm(s):
    """Chuan hoa de so khop: bo dinh dang, gop khoang trang, ha chu thuong."""
    s = re.sub(r"[*_`]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def _unwrap_margin_headings(text, headings, page_no, log):
    """Go tieu de cot le ra khoi giua cau va dat lai dung vi tri.

    Voi moi tieu de H lay tu hinh hoc, tim cac doan in dam trong markdown ma
    noi dung la mot phan cua H, xoa chung khoi cau, roi chen H thanh mot dong
    tieu de rieng ngay truoc doan van chua manh dau tien.
    """
    if not headings or not text.strip():
        return text

    lines = text.split("\n")

    for h in headings:
        h_norm = _norm(h)
        if len(h_norm) < 4:
            continue

        # Truong hop 1: tieu de da nam rieng mot dong -> chi chuan hoa, khong chen lai.
        standalone = None
        for i, ln in enumerate(lines):
            if _norm(ln) == h_norm and not ln.lstrip().startswith("|"):
                standalone = i
                break
        if standalone is not None:
            if not lines[standalone].lstrip().startswith("#"):
                lines[standalone] = f"### **{h}**"
                log.add("MARGIN HEADING", f"chuan hoa tieu de roi: {h!r}", page_no)
            continue

        # Truong hop 2: tieu de bi vo thanh nhieu manh in dam chen giua cau.
        first_hit = None
        removed_any = False
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith("|"):
                continue                      # khong dung vao bang
            if "**" not in ln:
                continue

            def _drop(m):
                nonlocal removed_any, first_hit
                inner = m.group(1)
                inner_norm = _norm(inner)
                if len(inner_norm) < 3:
                    return m.group(0)
                if inner_norm not in h_norm:
                    return m.group(0)
                removed_any = True
                if first_hit is None:
                    first_hit = i
                return "\x00"                  # danh dau de don khoang trang sau

            new_ln = re.sub(r"\*\*(.+?)\*\*", _drop, ln)
            if new_ln != ln:
                new_ln = re.sub(r"\s*\x00\s*", " ", new_ln)
                new_ln = re.sub(r"[ \t]{2,}", " ", new_ln).rstrip()
                # Neu tieu de bi go nam ngay dau dong thi se de lai khoang trang
                # thua. Chi cat khi dong goc von khong thut le, de giu nguyen
                # thut le cua danh sach long nhau.
                if not ln[:1].isspace():
                    new_ln = new_ln.lstrip()
                lines[i] = new_ln

        if removed_any and first_hit is not None:
            lines.insert(first_hit, f"### **{h}**")
            lines.insert(first_hit + 1, "")
            log.add("MARGIN HEADING", f"go khoi giua cau va dat lai: {h!r}", page_no)

    return "\n".join(lines)


# ----------------------------------------------------- NOI TRANG, DON DEP

_SENT_END = tuple(".!?:;")


def _looks_structural(line):
    s = line.lstrip()
    return (not s) or s.startswith(("#", "|", ">", "-", "*", "+", "```")) or bool(re.match(r"^\d+[.)]\s", s))


def _join_pages(pages, log):
    """Noi cac trang lai, han gan cau bi ngat ngang qua ranh gioi trang.

    Vi du that trong ho so thau: '...(for time-' o cuoi trang 28 va
    'based Contracts)...' o dau trang 29 phai thanh '(for time-based Contracts)'.
    """
    out = []
    for idx, ptext in enumerate(pages):
        ptext = (ptext or "").strip("\n")
        if not ptext.strip():
            continue
        if not out:
            out.append(ptext)
            continue

        prev = out[-1]
        prev_lines = prev.rstrip().split("\n")
        next_lines = ptext.lstrip().split("\n")
        if not prev_lines or not next_lines:
            out.append(ptext)
            continue

        tail = prev_lines[-1].rstrip()
        head = next_lines[0].lstrip()
        page_no = idx + 1

        joinable = (
            tail
            and head
            and not tail.endswith(_SENT_END)
            and not _looks_structural(tail)
            and not _looks_structural(head)
            and head[:1].islower()
        )

        if joinable:
            if tail.endswith("-"):
                merged = tail[:-1] + head          # tu bi gach noi cuoi dong
                how = "noi lien tu bi ngat gach noi"
            else:
                merged = tail + " " + head
                how = "noi lien cau bi ngat"
            prev_lines[-1] = merged
            next_lines = next_lines[1:]
            out[-1] = "\n".join(prev_lines)
            rest = "\n".join(next_lines).lstrip("\n")
            if rest.strip():
                out.append(rest)
            log.add("NOI TRANG", f"{how}: ...{tail[-45:]!r} + {head[:45]!r}...", page_no)
        else:
            out.append(ptext)

    return "\n\n".join(out)


def _clean_artifacts(text, keep_table_br, log):
    """Don rac dinh dang do trich xuat PDF sinh ra.

    Diem quan trong: engine moi sinh <br> DUNG CHUAN trong o bang, dung voi
    STYLE RULE cua vault. Vi vay chi doi <br> thanh khoang trang o van ban
    thuong, tuyet doi giu nguyen <br> ben trong dong bang.
    """
    before = text

    text = re.sub(r"</?mark[^>]*>", "", text)
    text = re.sub(r"</?a\b[^>]*>", "", text)

    # <br> tuy vi tri
    def _br_by_line(t):
        outl = []
        kept = 0
        for ln in t.split("\n"):
            if keep_table_br and ln.lstrip().startswith("|"):
                outl.append(ln)
                kept += ln.count("<br")
            else:
                outl.append(re.sub(r"<br\s*/?>", " ", ln))
        if kept:
            log.add("BANG BIEU", f"giu nguyen {kept} the <br> ben trong o bang theo STYLE RULE")
        return "\n".join(outl)

    text = _br_by_line(text)

    # Gach duoi dien cho trong bieu mau
    n_us = len(re.findall(r"_{3,}", text))
    if n_us:
        text = re.sub(r"_{3,}", "", text)
        log.add("DON RAC", f"xoa {n_us} cum gach duoi dien cho trong bieu mau")

    # In dam rong / in dam bi vo lam dut chu
    text = re.sub(r"([0-9A-Za-zÀ-ỹ])\*\*\s*\*\*([0-9A-Za-zÀ-ỹ])", r"\1\2", text)
    n_empty = len(re.findall(r"\*\*\s*\*\*", text))
    if n_empty:
        text = re.sub(r"\*\*\s*\*\*", "", text)
        log.add("DON RAC", f"xoa {n_empty} cap in dam rong")

    # Dau escape thua: (NĐ\-CP) -> (NĐ-CP)
    text = re.sub(r"\\([.\-+()\[\]*_])", r"\1", text)

    # Khoang trang lot giua ket thuc in dam va dau cau: '**Data Sheet** .' -> '**Data Sheet**.'
    text = re.sub(r"\*\*[ \t]+([.,;:)])", r"**\1", text)

    # Khoang trang thua
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    if text != before:
        log.add("DON RAC", "hoan tat don rac dinh dang chung")
    return text


_WORD_RE = re.compile(r"[0-9A-Za-zÀ-ỹ]{6,}")


def _pdf_word_set(doc):
    """Tap tu that ma PDF chua, dung lam bang chung khi tach tu bi dinh."""
    words = set()
    try:
        for page in doc:
            for w in page.get_text("words"):
                token = str(w[4]).strip(".,;:()[]{}\"'`").lower()
                if token:
                    words.add(token)
    except Exception:
        return set()
    return words


def _fix_split_words(text, wordset, log):
    """Tach cac tu bi dinh lien, CHI khi co bang chung tu chinh PDF.

    Dieu kien tach: tu ghep khong ton tai trong PDF, nhung ca hai nua deu ton
    tai. Vi du 'requiredin' -> 'required in'.

    Gioi han da biet: cac cum tieng Viet dinh chi so duoi nhu 'giáđang' THUC SU
    ton tai trong PDF nen se khong bi dung toi. Do la chu y, khong phai thieu
    sot: khong co bang chung thi khong sua.
    """
    if not wordset:
        return text

    cache = {}

    def _try_split(tok):
        low = tok.lower()
        if low in cache:
            return cache[low]
        result = None
        if low not in wordset and len(low) >= 6:
            for i in range(3, len(low) - 2):
                a, b = low[:i], low[i:]
                if a in wordset and b in wordset:
                    result = (a, b)
                    break
        cache[low] = result
        return result

    fixed = []
    changed = 0

    for ln in text.split("\n"):
        if ln.lstrip().startswith(("|", "```", ">")):
            fixed.append(ln)
            continue

        def _repl(m):
            nonlocal changed
            tok = m.group(0)
            sp = _try_split(tok)
            if not sp:
                return tok
            a, b = sp
            # Giu nguyen kieu chu hoa cua tu goc
            out = tok[: len(a)] + " " + tok[len(a) :]
            changed += 1
            if changed <= 200:
                log.add("TACH TU DINH", f"{tok!r} -> {out!r} (ca hai nua deu co trong PDF)")
            return out

        fixed.append(_WORD_RE.sub(_repl, ln))

    if changed > 200:
        log.add("TACH TU DINH", f"... va {changed - 200} truong hop tuong tu khac")
    return "\n".join(fixed)


_FORMULA_MARK = "<!-- CAN KIEM TRA: CONG THUC -->"


def _mark_formulas(text, log):
    """Don gach phan so rac va danh dau vung nghi la cong thuc de ra soat tay.

    Engine tra ve gach phan so duoi dang <sup>______</sup>, lam cong thuc mat
    nghia hoan toan. Script khong tu bia lai cong thuc (rui ro sai cach tinh
    diem), chi don rac va danh dau de nguoi dung dung lai bang tay.
    """
    lines = text.split("\n")
    out = []
    marked = 0

    # Gach phan so co the con nguyen dang gach duoi, hoac da bi buoc don rac
    # lam rong thanh <sup></sup>. Bat ca hai de khong phu thuoc thu tu pipeline.
    pat_bar = re.compile(r"<sup>\s*[_\-–—]*\s*</sup>")
    for ln in lines:
        if pat_bar.search(ln):
            cleaned = pat_bar.sub(" / ", ln)
            cleaned = re.sub(r"\s{2,}", " ", cleaned).rstrip()
            out.append(cleaned)
            out.append(_FORMULA_MARK)
            marked += 1
            log.add("CONG THUC", f"gach phan so bi vo, da danh dau de ra soat: {cleaned[:90]!r}")
        else:
            out.append(ln)

    if marked:
        log.add("CONG THUC", f"tong cong {marked} vung nghi la cong thuc can dung lai bang tay")
    return "\n".join(out)


# ------------------------------------------------------------------ PUBLIC

def convert(
    pdf_path,
    *,
    unwrap_margin_headings=True,
    join_pages=True,
    fix_split_words=True,
    mark_formulas=True,
    keep_table_br=True,
    ocr=True,
    ocr_language="vie+eng",
    show_progress=False,
):
    """Chuyen mot file PDF native sang Markdown.

    Moi giai doan hau xu ly duoc bao rieng: neu mot giai doan hong thi ket qua
    cua giai doan truoc van duoc giu, thay vi mat trang toan bo ban chuyen doi.
    """
    t0 = time.time()
    log = FixLog()
    stats = {"pages": 0, "seconds": 0.0, "engine": "layout" if _layout_engine_active() else "legacy"}

    doc = None
    try:
        doc = pymupdf.open(pdf_path)
        stats["pages"] = doc.page_count

        pages = _extract_pages(doc, ocr, ocr_language, show_progress, log)

        # Font tieng Viet doi cu (VNI-Times, TCVN3/.VnTime): lop text la ma cua
        # font chu khong phai Unicode, nen markdown trich ra se la rac kieu
        # 'khaùi nieäm ñaøm phaùn'. Sua ngay tai may, khong ton token - nho vay
        # nhung tai lieu nay khong con phai day sang duong scan (258 token/trang).
        try:
            # Dung bang thay the DUNG MOT LAN cho ca tai lieu roi ap cho tung
            # trang. Quet lai span theo tung trang se thanh O(so trang binh
            # phuong) - tai lieu 500 trang se treo.
            tong_ky_tu, ky_tu_cu, cac_span = font_viet.quet_span_doi_cu(doc)
            if cac_span:
                bang = font_viet.bang_thay_the(cac_span)
                tong_thay = 0
                for i, ptext in enumerate(pages):
                    moi, so_lan = font_viet.ap_bang(ptext, bang)
                    moi, them = font_viet._vet_tu_con_sot(moi)
                    if so_lan or them:
                        pages[i] = moi
                        tong_thay += so_lan + them
                if tong_thay:
                    ti_le = ky_tu_cu / tong_ky_tu if tong_ky_tu else 0
                    log.add("FONT", f"Da chuyen {tong_thay} doan tu font doi cu "
                                    f"(VNI/TCVN3, {ti_le*100:.0f}% tai lieu) sang Unicode")
        except Exception as e:
            log.add("CANH BAO", f"bo qua chuyen font doi cu: {type(e).__name__}: {e}")

        # Hinh hoc: tieu de cot le, lam theo tung trang.
        if unwrap_margin_headings:
            for i, ptext in enumerate(pages):
                try:
                    if i >= doc.page_count:
                        break
                    heads = _page_margin_headings(doc[i])
                    if heads:
                        pages[i] = _unwrap_margin_headings(ptext, heads, i + 1, log)
                except Exception as e:
                    log.add("CANH BAO", f"bo qua xu ly tieu de le trang {i+1}: {type(e).__name__}: {e}")

        wordset = _pdf_word_set(doc) if fix_split_words else set()
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass

    # Noi trang
    if join_pages:
        try:
            text = _join_pages(pages, log)
        except Exception as e:
            log.add("CANH BAO", f"noi trang that bai, giu nguyen ranh gioi trang: {type(e).__name__}: {e}")
            text = "\n\n".join(p for p in pages if p and p.strip())
    else:
        text = "\n\n".join(p for p in pages if p and p.strip())

    # Danh dau cong thuc TRUOC khi don rac: gach phan so cua engine la mot cum
    # gach duoi, neu don rac chay truoc thi dau vet cong thuc bi xoa mat.
    if mark_formulas:
        try:
            text = _mark_formulas(text, log)
        except Exception as e:
            log.add("CANH BAO", f"danh dau cong thuc that bai, bo qua: {type(e).__name__}: {e}")

    # Don rac
    try:
        text = _clean_artifacts(text, keep_table_br, log)
    except Exception as e:
        log.add("CANH BAO", f"don rac that bai, giu ban chua don: {type(e).__name__}: {e}")

    # Tach tu dinh
    if fix_split_words and wordset:
        try:
            text = _fix_split_words(text, wordset, log)
        except Exception as e:
            log.add("CANH BAO", f"tach tu dinh that bai, bo qua: {type(e).__name__}: {e}")

    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"

    stats["seconds"] = round(time.time() - t0, 2)
    stats["fixes"] = log.summary()
    return Result(markdown=text, fixlog=log, stats=stats)
