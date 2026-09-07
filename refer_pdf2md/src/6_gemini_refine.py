import os, sys, glob, time, re
import logging, warnings
from google import genai
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import image_extractor
import gemini_pool

# Tắt cảnh báo hệ thống rác
logging.getLogger("google").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(BASE_DIR, 'data', 'input')
# GUI dat PDF2MD_OUTPUT_DIR de giu cau truc thu muc con cua input trong output.
# ASSETS_DIR duoi day dua theo OUTPUT_DIR nen anh di theo dung thu muc Markdown.
OUTPUT_DIR = os.environ.get('PDF2MD_OUTPUT_DIR') or os.path.join(BASE_DIR, 'data', 'output')
ASSETS_DIR = os.path.join(OUTPUT_DIR, image_extractor.ASSETS_DIRNAME)

# Model đọc thẳng từ .env (biến GEMINI_MODEL) để tránh vòng lặp quét 404 qua
# một mảng ứng viên. Muốn nâng cấp model chỉ cần sửa 1 dòng trong .env.
DEFAULT_MODEL = 'gemini-1.5-flash'

# Bang trich ra ngan hon nguong nay thi khong bo cong doi duong: do thuc te
# cho thay file nho gan nhu khong chenh token, ma pandas lai co the doc hut
# nhung sheet co cau truc la.
NGUONG_TRICH_EXCEL = int(os.environ.get('PDF2MD_NGUONG_TRICH_EXCEL') or 2000)


def trich_excel_cuc_bo(duong_dan):
    """Đọc .xlsx tại máy rồi trả về CSV gọn, thay vì upload nguyên workbook.

    Workbook chứa rất nhiều thứ model không cần: ô trống, định dạng, công thức,
    XML bao quanh. Dọn tại máy bằng pandas (miễn phí) rồi chỉ gửi phần chữ thật.

    Đo thực tế trên hai file trong data/input:
        BOQ phức tạp (23 KB): 15.626 -> 10.152 token, giảm 35%
        Bảng nhỏ            :  3.720 ->  3.740 token, không đáng kể
    Nên chỉ dùng đường này khi phần chữ trích ra đủ lớn để bõ công; file nhỏ giữ
    nguyên cách upload cũ cho chắc, vì pandas có thể đọc hụt sheet lạ.
    """
    import pandas as pd
    phan = []
    for ten_sheet, df in pd.read_excel(duong_dan, sheet_name=None, header=None).items():
        df = df.dropna(how='all').dropna(axis=1, how='all')
        if df.empty:
            continue
        df = df.fillna("").map(lambda x: re.sub(r'\s+', ' ', str(x)).strip())
        phan.append(f"### Sheet: {ten_sheet}\n" + df.to_csv(index=False, header=False))
    return "\n\n".join(phan)

def refine():
    mode = sys.argv[1] if len(sys.argv) > 1 else "0"
    target = sys.argv[2] if len(sys.argv) > 2 else "ALL"
    
    ext_map = {"1": "*.pdf", "2": "*.xlsx", "3": "*.docx"}
    
    # TỐI ƯU PROMPT: Ép bảng Markdown siêu chuẩn bằng thẻ <br>
    prompt_map = {
        "1": (
            "Đóng vai chuyên gia. Hiệu đính tài liệu PDF scan này sang định dạng Markdown chuẩn Obsidian.\n"
            "YÊU CẦU NGHIÊM NGẶT:\n"
            "1. Sửa các lỗi OCR. BẮT BUỘC CHỈ trả về Markdown.\n"
            "2. Mọi bảng biểu PHẢI trình bày bằng Markdown Table chuẩn (| Cột 1 | Cột 2 |). Nếu văn bản trong một ô bị xuống dòng, HÃY dùng thẻ <br> thay cho dấu xuống dòng để không phá vỡ cấu trúc bảng.\n"
            "3. TUYỆT ĐỐI KHÔNG dùng bất kỳ thẻ HTML nào khác ngoài thẻ <br>.\n"
            "4. HÌNH ẢNH & BIỂU ĐỒ: Khi phát hiện biểu đồ, sơ đồ kỹ thuật hay hình minh hoạ (ví dụ: đường cong P-y, mặt cắt địa chất, sơ đồ móng cọc...), BẮT BUỘC chèn thẻ hình `![Mô tả ngắn gọn](assets/Ten-file-khong-dau.png)` tại đúng vị trí hình xuất hiện. Nếu có phần PHỤ LỤC HÌNH ẢNH liệt kê tên file bên dưới, PHẢI dùng đúng tên file đó, không được bịa tên khác.\n"
            "5. Không giải thích gì thêm."
        ),
        "2": (
            "Đóng vai chuyên gia. Trích xuất và hiệu đính các bảng phức tạp trong file Excel này sang định dạng Markdown chuẩn Obsidian.\n"
            "YÊU CẦU NGHIÊM NGẶT:\n"
            "1. BẮT BUỘC CHỈ trả về Markdown.\n"
            "2. Mọi bảng biểu PHẢI dùng Pipe tables (|---|---|). Dùng thẻ <br> nếu cần xuống dòng trong ô.\n"
            "3. Không giải thích gì thêm."
        ),
        "3": (
            "Đóng vai chuyên gia. Trích xuất và hiệu đính các bảng biểu, văn bản trong file Word này sang định dạng Markdown chuẩn Obsidian.\n"
            "YÊU CẦU NGHIÊM NGẶT:\n"
            "1. Giữ nguyên cấu trúc văn bản gốc. BẮT BUỘC CHỈ trả về Markdown.\n"
            "2. Mọi bảng biểu PHẢI dùng Pipe tables (|---|---|). Dùng thẻ <br> nếu cần xuống dòng trong ô.\n"
            "3. Không giải thích gì thêm."
        )
    }
    
    if mode not in ext_map: return
    
    load_dotenv(os.path.join(BASE_DIR, '.env'))
    be_key = gemini_pool.pool()
    if not be_key.keys:
        print("❌ Chưa khai báo API key nào trong .env "
              "(GEMINI_API_KEY hoặc GEMINI_API_KEY_FREE_1/_PAID).")
        return
    model_name = os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    so_free = sum(1 for k in be_key.keys if not k.tra_phi)
    print(f"⚙️  Model: {model_name} | Bể key: {so_free} free + "
          f"{len(be_key.keys) - so_free} trả phí (ưu tiên free trước)")

    if target == "ALL":
        files = glob.glob(os.path.join(INPUT_DIR, ext_map[mode]))
    else:
        file_path = os.path.join(INPUT_DIR, target)
        if not os.path.exists(file_path):
            print(f"❌ Khong tim thay file: {target}")
            return
        files = [file_path]
    
    for f in files:
        base = os.path.splitext(os.path.basename(f))[0]
        out_path = os.path.join(OUTPUT_DIR, f"{base}_refined.md")

        print(f"\n✨ [Gemini Refine Mode {mode}] Dang upload: {base}...")

        # Chỉ PDF (Mode 1) mới bóc tách hình/biểu đồ ra assets/ và liệt kê vào prompt.
        file_prompt = prompt_map[mode]
        if mode == "1":
            saved_imgs = image_extractor.extract_images(f, ASSETS_DIR, base_name=base)
            if saved_imgs:
                total = sum(len(v) for v in saved_imgs.values())
                print(f"🖼️  Đã tách {total} hình/biểu đồ vào assets/")
            file_prompt = prompt_map[mode] + image_extractor.build_prompt_manifest(saved_imgs)

        # Excel: dọn tại máy rồi gửi chữ, rẻ hơn upload nguyên workbook (đo được
        # 35% ít token hơn với BOQ phức tạp). File nhỏ thì không bõ, giữ cách cũ.
        van_ban_thay_the = None
        if mode == "2":
            try:
                bang = trich_excel_cuc_bo(f)
                if len(bang) >= NGUONG_TRICH_EXCEL:
                    van_ban_thay_the = bang
                    print(f"📊 Đã dọn bảng tại máy: {len(bang):,} ký tự "
                          f"(gửi chữ thay vì upload workbook)")
            except Exception as loi:  # noqa: BLE001
                print(f"⚠️ Không đọc được Excel tại máy ({loi}), quay lại cách upload.")

        def mot_luot(client, ten_key, _f=f, _mode=mode, _prompt=file_prompt,
                     _van_ban=van_ban_thay_the):
            """Trọn gói upload + gọi model + xoá file trên CÙNG một client.

            File đã upload chỉ tồn tại trong project của key đó, nên khi bể key
            đổi sang key khác thì phải upload lại từ đầu - vì vậy cả ba bước phải
            nằm gọn trong một hàm để bể key gọi lại nguyên khối.
            """
            if _van_ban is not None:      # đường Excel: không đụng tới Files API
                print(f"🧠 Đang trích xuất bằng {model_name} [{ten_key}]...")
                return client.models.generate_content(
                    model=model_name, contents=_prompt + "\n\n" + _van_ban)

            uploaded = gemini_pool.upload_an_toan(client, _f)
            try:
                if _mode == "1":
                    print(f"⏳ Đang chờ Google xử lý file PDF [{ten_key}]", end="")
                    while "PROCESSING" in str(uploaded.state):
                        print(".", end="", flush=True)
                        time.sleep(2)
                        uploaded = client.files.get(name=uploaded.name)
                    print()
                if "FAILED" in str(uploaded.state):
                    raise RuntimeError("Server Gemini xử lý file thất bại.")
                print(f"🧠 Đang trích xuất bằng {model_name} [{ten_key}]...")
                return client.models.generate_content(
                    model=model_name, contents=[uploaded, _prompt])
            finally:
                try:
                    client.files.delete(name=uploaded.name)
                except Exception:
                    pass

        try:
            res, _key = be_key.goi(mot_luot, nhan=f" ({base})")
        except gemini_pool.LoiHetPool as e:
            print(f"❌ {e}")
            break
        except Exception as e:  # noqa: BLE001
            if "404" in str(e) or "not found" in str(e).lower():
                print(f"❌ Lỗi 404: Model [{model_name}] không khả dụng với key này.")
                print("   👉 Vui lòng kiểm tra lại biến GEMINI_MODEL trong file .env!")
            else:
                print(f"❌ Lỗi tổng thể khi xử lý file {base}: {e}")
            continue

        if not getattr(res, 'text', None):
            print(f"❌ Không xử lý được file {base} (model không trả về nội dung).")
            continue

        text = res.text.replace("```markdown", "").replace("```", "").strip()

        # --- BỘ LỌC RÁC CHUYÊN SÂU ---
        text = re.sub(r'</?a[^>]*>', '', text)                # Diệt thẻ <a>
        text = re.sub(r'_{3,}', '', text)                     # Diệt đường gạch dưới rác
        text = re.sub(r'\\([.\-\+\(\)\[\]*_])', r'\1', text)  # Diệt dấu gạch chéo (\) thừa
        text = re.sub(r'\n{3,}', '\n\n', text)                # Tối ưu khoảng trắng

        with open(out_path, 'w', encoding='utf-8') as out:
            out.write(text)
        print(f"✅ Đã tạo thành công: {base}_refined.md (Model: {model_name})")

    print()
    print(be_key.tong_ket())

if __name__ == "__main__": refine()