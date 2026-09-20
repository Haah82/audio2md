
# Kế hoạch khắc phục tải YouTube: cookie, JavaScript runtime và subtitle-first

## Kết luận từ kiểm tra URL `ST_1LjQYdCg`

Kiểm tra ngày 2026-09-21 bằng môi trường `.venv` của dự án cho thấy:

- `yt-dlp` đang là `2026.08.19`, nên đây **không** phải trường hợp thư viện quá cũ.
- `extract_info(..., download=False)` lấy được metadata và 12 định dạng audio. URL không bị private, deleted hay bị chặn hoàn toàn ở thời điểm kiểm tra.
- Video không có phụ đề hoặc auto-subtitle cho `vi`/`en`; vì vậy pipeline buộc phải tải audio rồi gọi Gemini để bóc băng.
- `C:\FFmpeg\bin\ffmpeg.exe` tồn tại. FFmpeg không phải nguyên nhân ở bước lấy metadata; chỉ có thể là nguyên nhân nếu log lỗi tại hậu xử lý/chuyển đổi MP3.
- yt-dlp cảnh báo: không có JavaScript runtime được kích hoạt. Máy có Node.js trong `PATH`, nhưng yt-dlp chỉ bật Deno mặc định; Node phải được bật tường minh và cần EJS solver tương ứng.

### Kết quả thử tải MP3 bằng thuật toán hiện tại

Đã gọi trực tiếp chính hàm `download_media()` hiện có, giữ nguyên các `ydl_opts` của mã nguồn và chỉ thay `INPUT_DIR` sang thư mục tạm. Không dùng cookie, không sửa cấu hình dự án. Kết quả:

- yt-dlp chọn audio format `251` (`webm`) và tải thành công 4.08 MiB.
- FFmpeg `ExtractAudio` chuyển đổi thành công sang `ST_1LjQYdCg.mp3`.
- Hàm đi vào nhánh `Khong co phu de, da tai am thanh` và trả về đường dẫn MP3, đúng như thiết kế.
- Thư mục tạm cùng MP3 đã được xóa sau kiểm tra; dữ liệu dự án không bị thay đổi.

**Quyết định:** Với URL và mạng hiện tại, thuật toán đang chạy **có khả năng tải MP3**; không cần cookie để xử lý riêng URL này ở thời điểm kiểm tra. Vẫn nên thực hiện các cải tiến bên dưới để bền vững trước thay đổi của YouTube và các URL/mạng khác. Lỗi `UnicodeEncodeError` xuất hiện sau khi thử nghiệm in toàn bộ tuple kết quả trong console Windows (tiêu đề có ký tự không thuộc code page), không xảy ra khi yt-dlp tải/chuyển đổi MP3 và không phải lỗi của `download_media()`.

Vì vậy, nhận định cũ “thiếu cookie là nguyên nhân chính” chưa có đủ bằng chứng. Cookie vẫn là fallback cần thiết khi log thực tế có `Sign in to confirm you’re not a bot`, CAPTCHA, 403, age/login restriction, hoặc YouTube từ chối client/IP. Tham khảo: [yt-dlp EJS](https://github.com/yt-dlp/yt-dlp/wiki/EJS), [yt-dlp FAQ về cookies](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp).

## Phạm vi đã chốt

Chỉ thực hiện **mục 4 — chuyển luồng sang subtitle-first đúng nghĩa**. Không thay đổi preflight trong `main()`, cookie, JavaScript runtime/EJS, dependency, retry hiện hữu, định dạng log, `.env`, `.gitignore` hay các luồng local audio. Đây là tối ưu chi phí/tốc độ, không phải giải pháp cho URL bị YouTube xác thực hoặc chặn.

## 4. Chuyển luồng sang subtitle-first đúng nghĩa

### Đánh giá khả thi

Khả thi ở mức trung bình. Phần tải subtitle thay đổi cục bộ trong `download_media()`, nhưng chính sách `title_only` cần một nhánh kết thúc nhỏ trong `main()` và cập nhật hàng của `build-audio2md.md`:

- Các thành phần cần dùng đã có: `yt_dlp`, `clean_subtitle()`, `glob`, `INPUT_DIR`, `GeminiPool` và các hàm cập nhật bảng.
- Cần bổ sung kết quả có trạng thái rõ ràng (ví dụ `title_only` cùng tiêu đề đã chuẩn hóa), vì hợp đồng hiện tại `(raw_text, mp3_file, title)` không phân biệt được `title_only` với lỗi tải.
- URL `ST_1LjQYdCg` không có phụ đề vi/en. Theo quyết định mới, luồng này không tải MP3; nó chỉ chuẩn hóa tiêu đề ngoại ngữ sang tiếng Anh và đánh dấu item là không có transcript.
- Với video có subtitle hợp lệ, luồng mới không tải audio và không chạy FFmpeg; đây là lợi ích chính.

Giới hạn được chấp nhận của phạm vi này:

- Preflight `extract_info(..., download=False)` trong `main()` vẫn chạy như hiện tại. Nếu nó bị YouTube chặn, chương trình vẫn dừng trước `download_media()`; không xử lý trong thay đổi này.
- Không có cookie/EJS mới, nên không cam kết xử lý được video cần đăng nhập hoặc bot challenge.
- Không thay đổi retry hiện tại; nhánh không có subtitle kết thúc trước khi vào retry audio cũ.

### Thiết kế thay đổi

1. Giữ nguyên bước preflight hiện tại để lấy title/kiểm tra file đã tồn tại.
2. Trong `download_media()`, tạo **options subtitle** chỉ gồm output template, `writesubtitles=True`, `writeautomaticsub=True`, `subtitleslangs=['vi', 'en']`, `skip_download=True` và các option hiện hữu không liên quan audio. Không đặt `format`, `postprocessors` hoặc `ffmpeg_location` ở pha này.
3. Gọi yt-dlp tải subtitle. Dựa vào `video_id` trả về để tìm `.vtt`/`.srt` vừa tạo, đọc bằng `clean_subtitle()` và xóa các subtitle tạm sau khi đọc.
4. Nếu `raw_text` không rỗng, trả về `(raw_text, None, title)` ngay. Phần `main()` hiện tại sẽ ghi Raw và gọi refine như trước; Gemini không nhận audio.
5. Nếu không có hoặc subtitle rỗng (nhánh của `ST_1LjQYdCg`), **không tải bestaudio và không gọi FFmpeg hoặc Gemini Audio**. Xác định ngôn ngữ tiêu đề; nếu tiêu đề không phải tiếng Việt hoặc tiếng Anh, dùng một request text-only qua `GeminiPool` để dịch riêng tiêu đề sang tiếng Anh. Tiêu đề tiếng Việt/tiếng Anh được giữ nguyên.
6. Trả về kết quả có trạng thái `title_only` thay vì tuple lỗi mơ hồ. Trong `main()`, xử lý trạng thái này trước điều kiện “không Raw và không audio là thất bại”: cập nhật tiêu đề và trạng thái `No transcript (title only)` vào `build-audio2md.md`, rồi kết thúc item thành công có giới hạn.
7. Không tạo `_raw.md` hoặc `_refine.md` từ riêng tiêu đề, vì điều đó không phải transcript và sẽ làm sai dữ liệu đầu ra.
8. Không quét/xóa MP3 ở nhánh subtitle, vì nhánh này không từng tải audio. Chỉ xóa file subtitle có ID tương ứng để tránh đụng dữ liệu của URL khác.

### Rủi ro và cách kiểm soát

- **Không có transcript cho video không subtitle:** đây là đánh đổi chủ đích để loại bỏ tải audio/Gemini. Bản dịch tiêu đề chỉ giúp nhận diện/navigating nội dung, không thay thế transcript.
- **Dịch title phụ thuộc Gemini text:** nếu thiếu key, hết quota hoặc dịch lỗi, vẫn lưu tiêu đề gốc và `No transcript`; không được làm item chuyển thành lỗi tải subtitle. Không cần gọi Gemini Audio.
- **Nhận diện ngôn ngữ không chắc chắn:** chỉ bỏ qua dịch khi yt-dlp báo rõ `vi`/`en` hoặc bộ nhận diện có độ tin cậy cao; các trường hợp khác gửi prompt dịch idempotent, yêu cầu giữ nguyên title nếu nó đã là tiếng Anh/Việt.
- **Tăng một lượt gọi yt-dlp khi không có subtitle:** chấp nhận được cho URL này; đổi lại video có transcript không phải tải/chuyển audio.
- **Subtitle cũ bị nhận nhầm:** chỉ xử lý file đúng `video_id` được pha subtitle tạo ra; cần dọn file tạm của đúng ID trước/sau pha này, không dùng glob toàn thư mục để xóa rộng.
- **Subtitle tải được nhưng rỗng/lỗi đọc:** coi như không có subtitle và chuyển sang audio; không ghi Raw rỗng.
- **Lỗi pha subtitle:** phải phân biệt “không có subtitle” và “không lấy được subtitle”. Chỉ trường hợp xác nhận không có subtitle mới đi vào `title_only`; lỗi kỹ thuật vẫn báo thất bại, không được giả là không có transcript.

### Tiêu chí hoàn tất

- Test mock: subtitle hợp lệ trả về Raw, không tạo `FFmpegExtractAudio`, không tải audio và xóa file subtitle tạm đúng ID.
- Test mock: không có subtitle hoặc subtitle rỗng không tạo postprocessor MP3, không gọi Gemini audio; title ngoài vi/en được dịch sang tiếng Anh.
- Test mock: thiếu Gemini key/quota khi dịch title vẫn ghi `title_only` với tiêu đề gốc, không tạo Raw/Refine.
- Test regression: `main()` không còn ghi nhầm `title_only` là `Failed`, local audio không bị sửa.
- Test tích hợp thủ công với `ST_1LjQYdCg`: log pha subtitle không tìm thấy transcript, không tạo MP3 và item được đánh dấu `title_only`.
- Test tích hợp thủ công với một video công khai có subtitle vi/en: tạo Raw mà không tạo MP3.

### Quyết định triển khai

Chỉ nên triển khai theo hướng này khi chấp nhận rằng các video không có subtitle sẽ **không có transcript**. Nó giảm chi phí/tốc độ xử lý và vẫn giúp chuẩn hóa tiêu đề để quản lý link, nhưng làm thay đổi đáng kể giá trị đầu ra so với luồng MP3 + Gemini trước đây. Việc tăng độ bền trước xác thực YouTube sẽ được xem xét ở một thay đổi khác sau khi có log lỗi tương ứng.
