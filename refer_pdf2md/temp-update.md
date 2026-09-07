thực hiện như chuyên gia công nghệ 25 năm kinh nghiệm, 
Phân Tích Tính Khả Thi Tách Hình Từ PDF & Chèn Vào MarkdownViệc tách hình từ PDF (như các biểu đồ P-y curve, biểu đồ biến dạng đất, sơ đồ móng cọc) để lưu vào thư mục assets và chèn lại vào Markdown là hoàn toàn khả thi và đặc biệt cần thiết đối với hệ thống Agent chuyên ngành kỹ thuật.Tính khả thi & Giải pháp:Thực thi kỹ thuật: Ta có thể dùng thư viện máy trạm (PyMuPDF / fitz ở bước local) bóc tách toàn bộ Object dạng ảnh/vector trong PDF, crop ra và tự động lưu vào thư mục cục bộ assets/ dưới dạng .png hoặc .jpg.Giá trị mang lại: Giữ lại được biểu đồ vô giá (như biểu đồ Stress distribution in a laterally loaded pile hay P-y curve in the soft clay), thay vì ép AI diễn giải bằng text khô khan và tốn token. Các file .md sau này dùng làm nguồn cho Agent có thể dễ dàng chuyển đổi sang HTML/Report DOCX chuẩn xác, có kèm hình mà không cần vẽ lại.  Vai trò của Gemini: LLM sẽ chỉ đóng vai trò "nắm bắt ngữ cảnh". Nhờ nhận thức đa phương thức, AI nhìn thấy biểu đồ trên trang scan sẽ tự động sinh mã liên kết (Markdown image tag) trùng với quy ước đặt tên của hình thay vì cố gắng đọc hình đó ra text rác.Bản Cập Nhật System Prompt (Áp dụng vào 3_pdf_scan.py & 6_gemini_refine.py):Plaintext"Đóng vai chuyên gia. Chuyển đổi tài liệu PDF scan này sang định dạng Markdown chuẩn Obsidian.
YÊU CẦU NGHIÊM NGẶT:
1. BẮT BUỘC CHỈ trả về văn bản Markdown. Không giải thích gì thêm.
2. BẢNG BIỂU: Mọi bảng biểu PHẢI trình bày bằng Markdown Table chuẩn (| Cột 1 | Cột 2 |). Để bảo toàn cấu trúc bảng, TUYỆT ĐỐI chỉ dùng thẻ <br> để ngắt dòng bên trong ô.
3. LỌC RÁC: Lọc bỏ toàn bộ các đường kẻ ngang rác, gạch dưới (___) và HTML rác.
4. HÌNH ẢNH & BIỂU ĐỒ (QUAN TRỌNG): Khi phát hiện biểu đồ, sơ đồ kỹ thuật, hình minh họa (Ví dụ: biểu đồ P-y curve, mặt cắt địa chất...), BẮT BUỘC nhận diện và CHÈN THẺ HÌNH ẢNH theo cú pháp Markdown: `![Mô tả ngắn gọn biểu đồ](assets/Tên-file-không-dấu.png)`. TUYỆT ĐỐI không được bỏ qua các biểu đồ này."
3. Cập Nhật Kế Hoạch Đưa Biến Model Vào .env Tránh Lỗi Quét 404Việc vòng lặp mã nguồn cũ liên tục chọc vào mảng CANDIDATE_MODELS rồi ném ra các luồng báo lỗi 404 gây giảm hiệu suất xử lý nghiêm trọng và tạo ra sự nhầm lẫn về log. Dưới đây là phương án điều chỉnh triệt để:BƯỚC 1: Bổ sung định nghĩa biến trong file .envCode snippet# Môi trường API
GEMINI_API_KEY=AIzaSyxxxx...
# Chỉ định Model cụ thể cần dùng để tránh vòng lặp quét báo lỗi 404
GEMINI_MODEL=gemini-3.6-flash -> đã sửa trong .env
# Các tùy chọn nâng cấp khác: gemini-3.6-flash, gemini-1.5-pro...
Tối ưu mã nguồn Python (src/3_pdf_scan.py / 6_gemini_refine.py)Thay vì khai báo mảng CANDIDATE_MODELS = [...], ta đọc trực tiếp model được cấp phép từ .env. Cấu trúc code sẽ đi thẳng vào xử lý:Pythonimport os
from dotenv import load_dotenv

# Đọc cấu hình môi trường
load_dotenv(os.path.join(BASE_DIR, '.env'))
api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash") # Lấy model từ env, mặc định fallback về 1.5 flash

#... (Khởi tạo client)...

# Khối xử lý gọi API:
max_retries = 3
for attempt in range(max_retries):
    try:
        print(f"🧠 Đang trích xuất bằng model {model_name} (Lần thử {attempt + 1}/{max_retries})...")
        res = client.models.generate_content(
            model=model_name, 
            contents=[uploaded, prompt]
        )
        # Xử lý nội dung trả về
        if res.text:
            text = res.text.replace("```markdown", "").replace("```", "").strip()
            # Gọi hàm dọn rác regex
            with open(out_path, 'w', encoding='utf-8') as out: 
                out.write(text)
            print(f"✅ Đã tạo thành công file bằng model: {model_name}")
            break # Thoát vòng lặp retry nếu thành công
            
    except Exception as ex:
        err_str = str(ex)
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            print("⏳ Quá tải API (Lỗi 429). Tạm nghỉ 35 giây...")
            time.sleep(35)
        elif "404" in err_str or "NOT_FOUND" in err_str:
            # Ngừng ngay lập tức nếu Model điền trong file .env không tồn tại
            print(f"❌ Lỗi 404 CHÍNH MẠNG: Model [{model_name}] không khả dụng với API Key này. Vui lòng kiểm tra lại file .env!")
            break 
        else:
            print(f"⚠️ Lỗi xử lý: {ex}")
            break
Lợi ích của giải pháp này:LLM/Agent ngay lập tức xác định chính xác năng lực phần cứng đang sử dụng thông qua .env.Khắc phục triệt để tình trạng in ra console các luồng lỗi rác (⚠️ Model [gemini-1.5-flash-8b] bị lỗi 404...) làm che lấp các FixLog quan trọng từ engine local.Nếu nâng cấp lên các phiên bản sau (như gemini-3.6-flash), chỉ cần mở file cấu hình .env thay đổi string 1 lần duy nhất thay vì tìm sửa ở từng file Python chuyên biệt.