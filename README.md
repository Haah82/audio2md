# Audio2MD

Hệ thống trích xuất và tóm tắt văn bản từ Audio, Video và Link Youtube/Facebook/LinkedIn.

## Tổng quan
Audio2MD là một pipeline được thiết kế với tư duy MVP (chi phí thấp, tốc độ cao). Hệ thống tự động chuyển đổi nội dung âm thanh và video thành các tài liệu Markdown có cấu trúc rõ ràng.

## Tính năng nổi bật
* **Tối ưu chi phí và tốc độ:** Tự động ưu tiên tải subtitles/transcript có sẵn thông qua `yt-dlp` đối với các link mxh (Youtube, Facebook, LinkedIn). Khi có sẵn phụ đề, hệ thống bỏ qua bước tải audio và gọi API, chuyển thẳng thành bản nguyên tác [cite: 1, 2].
* **Nhận diện giọng nói (STT):** Sử dụng Gemini Flash để bóc băng đối với các file cục bộ hoặc link không có sẵn phụ đề.
* **Bảo toàn dữ liệu kép:** 
    * **Raw:** Giữ nguyên 100% transcript gốc, lưu dưới dạng `[Tên]_raw.md`.
    * **Refine:** Phiên bản tinh luyện được định dạng cấu trúc 4 phần (Tiêu đề, Tóm tắt, Bài học, Trích dẫn), lưu dưới dạng `[Tên]_refine.md`.
* **Hỗ trợ đa định dạng:** 
    * Video: mp4, avi, mov, mkv, wmv, flv.
    * Audio: mp3, wav, m4a, aac, ogg, flac.

## Cài đặt và Sử dụng
1. Clone repository về máy.
2. Tạo file `.env` tại thư mục gốc và cấu hình API Key Gemini.
3. Chạy file `build-audio2md.bat`.
4. Tại giao diện Menu, chọn **[1] Cai dat he thong** để hệ thống tự động tạo môi trường ảo `.venv`, cài đặt thư viện (`google-genai`, `python-dotenv`, `yt-dlp`) và tự động cấu hình FFmpeg.
5. Sau khi cài đặt hoàn tất, sử dụng các Menu từ [2] đến [4] để xử lý Video, Audio hoặc Link tương ứng.

## Quản lý Link
Đối với tính năng convert từ URL (Menu 4), hệ thống sử dụng file `data/input/build-audio2md.md` để quản lý danh sách các link cần xử lý, cho phép thêm mới hoặc chọn xử lý hàng loạt.
