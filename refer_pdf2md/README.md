# 📄 pdf2md - Document to Obsidian Markdown Pipeline

Công cụ tự động hóa chuyển đổi các định dạng tài liệu phổ biến (PDF, Word, Excel) thành file Markdown chuẩn, tối ưu hóa cho hệ thống quản lý kiến thức Obsidian. Dự án kết hợp sức mạnh xử lý cục bộ (Local) và trí tuệ nhân tạo (Gemini API) để đem lại kết quả trích xuất văn bản chính xác nhất.

---

## ✨ Tính năng nổi bật

*   **Xử lý đa định dạng:** Hỗ trợ Native PDF, Scanned PDF (dạng ảnh), MS Word (`.docx`), và MS Excel (`.xlsx`).
*   **Tích hợp AI (Gemini):** OCR nhận diện chữ trên PDF scan và hiệu đính (refine) các bảng biểu phức tạp trong Excel/Word.
*   **Giao diện dòng lệnh thông minh:** Quản lý quy trình qua file `.bat` với menu trực quan.
*   **Chọn file linh hoạt:** Cho phép chọn file cần xử lý theo số thứ tự (vd: `1`, `1,3,5`), theo khoảng (vd: `2-4`), chọn tất cả (`A`), hoặc quét theo tên (`T`).
*   **Tự động hóa toàn trình (Auto):** Chạy tuần tự tất cả các kịch bản chuyển đổi chỉ với một phím bấm.

---

## 📁 Cấu trúc thư mục

Để công cụ hoạt động chính xác, hãy đảm bảo cấu trúc thư mục của bạn được tổ chức như sau:

```text
pdf2md/
│
├── data/
│   └── input/              <-- Đặt các file cần chuyển đổi vào đây
├── src/
│   ├── 2_pdf_native.py     <-- Xử lý PDF gốc (Local)
│   ├── 3_pdf_scan.py       <-- Xử lý PDF scan bằng Vision AI
│   ├── 4_word.py           <-- Xử lý file Word
│   ├── 5_excel.py          <-- Xử lý file Excel
│   └── 6_gemini_refine.py  <-- Hiệu đính cấu trúc bằng AI
│
├── requirements.txt        <-- Danh sách thư viện Python
├── .env                    <-- (Tự tạo) Chứa cấu hình GEMINI_API_KEY
└── pdf-2-md.bat            <-- Script khởi chạy bảng điều khiển chính