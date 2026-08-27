# Kế Hoạch Dự Án audio2md (Tối Ưu Tư Duy MVP)

## I. Cập Nhật Tư Duy Xử Lý (MVP - Chi phí thấp, Tốc độ cao)
Hệ thống ưu tiên việc lấy **phụ đề (subtitles/transcript) có sẵn** bằng `yt-dlp` đối với các link mxh (Youtube...).
- Nếu `yt-dlp` tìm thấy phụ đề, hệ thống sẽ tự động bóc văn bản ra, chuyển thẳng thành bản Nguyên tác (`_raw.md`) và **bỏ qua hoàn toàn việc tải âm thanh cũng như việc gọi API Gemini Audio**, tiết kiệm tối đa thời gian và chi phí API.
- Chỉ khi `yt-dlp` KHÔNG lấy được phụ đề (hoặc đó là file cục bộ có sẵn), hệ thống mới tải file `.mp3` và đẩy qua **Gemini Flash** để "nghe" và bóc băng.

## II. Nguyên Tắc Bảo Toàn Dữ Liệu
- Bước "Raw": Bắt buộc giữ nguyên tác 100% (file lưu với tên `[Tên]_raw.md`).
- Bước "Refine": Chỉ file tinh luyện mới bị cắt gọt theo format 4 phần (Tiêu đề, Tóm tắt, Bài học, Trích dẫn), lưu với tên `[Tên]_refine.md`.

## III. Chuẩn Bị & Cài Đặt
- Chạy `build-audio2md.bat`. Chọn Menu [1] để tự động tạo `.venv` và cài thư viện.
- Nhập API Key Gemini vào file `.env`.
- Tận hưởng quy trình xử lý 4 Menu (Video, Audio, Link).
