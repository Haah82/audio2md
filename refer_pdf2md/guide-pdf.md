# 📖 Hướng Dẫn Vận Hành Hệ Thống Chuyển Đổi Tài Liệu (Obsidian)

## 1. Yêu Cầu Đầu Vào
*   Chỗ trợ các định dạng: `.pdf`, `.docx`, `.xlsx`.
*   Chép toàn bộ file vào `data\input\`.

## 2. Quy Trình 
1. Chạy `pdf-2-md.bat`.
2. Chọn `[1]` cài đặt môi trường.
3. Chọn `[2]` để quét nội dung bằng sức mạnh máy tính (Local). 
   * *XLSX sẽ được chuyển thẳng thành bảng Obsidian hoàn hảo.*
   * *PDF text sẽ được xử lý cực nhanh.*

## 3. Phím [2] - PDF Native

Logic nằm trong `src/pdf_native_core.py` (bản sao giống hệt với repo SecondBrain_Vault, sửa một lần dùng được cả hai). Ngoài việc trích xuất, nó còn tự hiệu đính:

*   Chặn số trang / header / footer chen vào giữa câu ngay từ engine.
*   Gỡ tiêu đề cột lề bị vỡ vụn ra khỏi giữa câu (tài liệu Word 2 cột), dựa trên tọa độ thật trong PDF.
*   Nối lại câu bị ngắt ngang qua ranh giới trang, kể cả từ bị gạch nối cuối trang.
*   Giữ nguyên thẻ `<br>` bên trong ô bảng, chỉ bỏ ở văn bản thường.
*   Tách từ bị dính (`requiredin` thành `required in`) nhưng **chỉ khi cả hai nửa đều có thật trong PDF**, tránh sửa bừa.

Mỗi file sinh thêm `data/output/<tên>_native.fixlog.md` liệt kê mọi chỗ đã tự sửa. Nên đọc file này trước khi dùng bản Markdown cho việc quan trọng.

Chạy tay ngoài menu:

```bat
python src\2_pdf_native.py "data\input\tai-lieu.pdf"
python src\2_pdf_native.py ALL --jobs 4
python src\2_pdf_native.py ALL --force
```
4. Chọn `[3]` để gọi Gemini AI xử lý các file DOCX (chứa bảng), PDF Scan, hoặc các file bị lỗi font.
