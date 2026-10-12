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

## IV. Lỗi liên kết trong build-audio2md.md (phát hiện 12/10/2026)

### IV.1. Các lỗi đã rà soát
Rà toàn bộ `data/input/build-audio2md.md` bằng cách đếm cột (`|`) và đối chiếu từng wikilink `[[...]]` với tên file thật trong `data/output/`.

| # | Dòng (STT) | Lỗi | Nguyên nhân | Trạng thái |
|---|---|---|---|---|
| 1 | STT 107, 106 (`Nobel Economist...`, `Can Vietnam be the new Singapore?`) | Cột Refine trống, chỉ có Raw | Hai link mới nhất lấy được phụ đề qua yt-dlp (đúng thiết kế mục I), nhưng bước gọi Gemini tinh luyện (`refine_content`) sau đó không trả về nội dung — không có log nào trong `history/` ghi lại nguyên nhân (file log gần nhất là 09/2026, từ máy khác). Khả năng cao là lỗi tạm thời của API (hết quota Free, 503) tại thời điểm chạy | **Chưa sửa** — cần chạy lại Menu 4 cho 2 link này để thử refine lại; không tự chạy vì tốn API và cần `.env` của người dùng |
| 2 | STT 2 (`First Taste of Vietnam!...`) | Dòng bị lệch cột: cột "Tên file" dính luôn phần `_raw]]` (mất dấu `!` và dấu `[[` mở), cột "Thời gian" bị thế bằng link Refine, cột "Raw" bị thế bằng chữ "Done" | Lỗi thao tác tay từ rất lâu (xuất hiện xuyên suốt lịch sử git, không phải lỗi mới) — có khả năng một lần sửa tay làm mất một dấu `|` | **Đã sửa**: khôi phục đúng 6 cột theo tên file thật trên đĩa, lấy mốc thời gian từ ngày tạo file (`git log`: 28/08/26 02:34:05) |
| 3 | STT 90 (`20K views · 1.3K reactions...`) | Link Raw trỏ tới file không còn tồn tại | File `20K views · 1.3K reactions_raw.md` bị xóa tay ở commit `357a1b8` (27/09/2026), chỉ còn file Refine — vi phạm "Nguyên Tắc Bảo Toàn Dữ Liệu" ở mục II (Raw phải giữ 100%) | **Đã sửa**: thay link Raw bằng chú thích "(Raw đã bị xóa ..., xem lịch sử git)", đổi Status thành "Refine only" để không còn hiện link đỏ trong Obsidian |
| 4 | Nhiều file trong `data/output/` | File mồ côi: tồn tại trên đĩa nhưng không dòng nào trong bảng trỏ tới (ví dụ `How to study English as a busy person _ The English Podcast_*.md`, `66M views · 781K reactions_*.md`, `vo cuc- am duong_*.md`, `NÂNG CẤP_ GIỌNG NÓI...`, `Sự Kiện Ngày 11.9_*.md`, `12 chữ giúp nhìn thấu...`) | Tiêu đề lấy từ yt-dlp/Facebook đổi nhẹ giữa các lần chạy lại (số lượt xem/reaction tăng lên, hoặc kênh trả về caption khác) khiến `sanitize_filename` sinh ra tên file mới, để lại bản cũ làm rác | **Chưa xóa** — chờ áp dụng quy ước đặt tên NNN ở mục IV.2 rồi xử lý theo lô, giống cách `rename-management.md` xử lý "bản trùng MD5" ở `C:\Addins` (không tự xóa khi chưa duyệt) |

### IV.2. Quy ước đặt tên mới: `NNN_Ten_raw.md` / `NNN_Ten_refine.md`
Tham khảo logic của `C:\Addins\rename-management.md` (C5: tên không dấu, độ dài giới hạn; C6: số đứng trước để sắp xếp và tránh trùng tên) để áp cho `data/output/`. Mục tiêu: số `NNN` neo file vào đúng dòng trong bảng, nên khi `sanitize_filename` sinh ra tên khác đi giữa các lần chạy (mục IV.1.4), file không còn bị "mồ côi".

- **`NNN`**: chính là STT của dòng trong `build-audio2md.md`, đệm 3 số (`007`, `090`, `107`...) vì danh sách đã vượt mốc 100. Giữ `NNN` cố định một khi đã gán — không gán lại nếu dòng bị sửa sau này.
- **`Ten`**: tên đại diện, **dài 10-40 ký tự, chỉ ký tự ASCII** (tiếng Anh, hoặc tiếng Việt đã bỏ dấu) — cách lấy khác nhau theo nguồn:
  - **YouTube**: dùng nguyên tiêu đề video (`info['title']` qua yt-dlp) như hiện tại — tiêu đề YouTube luôn là tên đại diện mô tả đúng nội dung, không cần đổi logic trước khi làm sạch.
  - **Facebook / Instagram / LinkedIn**: tiêu đề `yt-dlp` trả về cho các nền tảng này thường là số liệu tương tác ghép với caption, dạng `"{N}K views · {M}K reactions - {caption} - {Tên trang}"` (ví dụ dòng STT 90, 86, 88). Số liệu (`views`, `reactions`) đổi mỗi lần chạy lại nên không dùng làm tên được — đây chính là nguyên nhân sinh file mồ côi ở mục IV.1.4. Quy tắc:
    1. Cắt bỏ tiền tố số liệu (khớp mẫu `^[\d.,]+[KM]?\s*views?\s*[·-]\s*[\d.,]+[KM]?\s*reactions?\s*-\s*`) và cắt bỏ hậu tố `" - {Tên trang}"` cuối cùng, giữ lại đoạn caption ở giữa làm `Ten`.
    2. Nếu cắt xong `Ten` rỗng (reel/video không có caption, chỉ có số liệu) — lấy vài từ đầu của **nội dung file Raw** (transcript vừa bóc băng) làm `Ten`, đúng như yêu cầu "tên đại diện lấy từ nội dung file" khi nền tảng không cho tên đại diện dùng được.
  - **Làm sạch chung** (hàm `sanitize_filename`, áp dụng sau khi đã rút `Ten` ở trên): bỏ phần sau `|`/`#` (tên kênh/hashtag) → bỏ dấu tiếng Việt và dấu phụ Latin khác (hàm `bo_dau`: thay `đ/Đ` tay, rồi NFD + lọc ký tự tổ hợp, vd `"Hướng dẫn"` → `"Huong dan"`, `"contención"` → `"contencion"`) → bỏ emoji/ký hiệu trang trí (cùng mẫu regex dùng cho nội dung) → đổi gạch ngang dài (–, —) thành gạch ngắn `-` → bỏ ký tự cấm Windows (`\/*?:"<>|`) → cắt về tối đa 40 ký tự, ưu tiên cắt tại khoảng trắng gần nhất để không đứt giữa từ (hàm `rut_gon_ten`). Không ép tối thiểu 10 ký tự bằng cách độn thêm chữ — chỉ đạt được khi nội dung gốc đủ dài, thực tế luôn đúng vì tiêu đề/caption luôn dài hơn ngưỡng này.

### IV.3. Việc cần làm theo lô (mô hình giống rename-management.md: duyệt → script → chạy từng lô) — HOÀN THÀNH 12/10/2026 (2 vòng)
1. **Duyệt**: đã kiểm tra công thức tách `Ten` trên các dòng Facebook mẫu (STT 90, 86, 88, 84, 92...) qua `--dry-run`, kết quả đúng như kỳ vọng (ví dụ STT 90 và 92 cùng nội dung "Con gái không nên trực tiếp quá..." nhưng khác STT nên không trùng tên).
2. **Sửa `src/main_audio2md.py`**: thêm `ten_dai_dien()` (cắt tiền tố số liệu tương tác + hậu tố tên trang cho link Facebook/Instagram/LinkedIn, có fallback lấy từ nội dung Raw khi caption rỗng), `doc_stt_hien_co()` (đọc STT lớn nhất và STT đã gán theo URL trong `build-audio2md.md`), `bo_dau()` (bỏ dấu tiếng Việt/Latin khác) và `rut_gon_ten()` (cắt về tối đa 40 ký tự tại khoảng trắng gần nhất). `main()` gán `stt_gan` cho mỗi link **trước** khi tạo file, dùng `f"{stt_gan:03d}_{sanitize_filename(ten_dai_dien(...))}"` làm `file_title` (đã làm sạch dấu/emoji/độ dài qua `sanitize_filename`); `update_md_table`/`them_dong_moi` nhận thêm `stt_moi` để STT của dòng khớp đúng tiền tố NNN của file. Chỉ áp dụng cho link (`is_url(item)`), không đổi tên file cục bộ. Đã chạy `tests/test_audio2md.py` (12/12 đạt) sau cả hai lần sửa. **Đã kiểm chứng trên dữ liệu thật**: trong lúc sửa code, các lần chạy Menu 4 song song của người dùng (STT 108, 109) tự ra đúng file `108_...`/`109_...` theo quy ước mới.
3. **Viết script đổi tên hồi tố**: `src/rename_output_files.py` — đọc `build-audio2md.md`, tính `NNN_Ten` cho từng dòng bằng đúng `ten_dai_dien()`/`sanitize_filename()` import từ `main_audio2md.py` (bảo đảm nhất quán giữa file mới và file đổi tên hồi tố), đổi tên vật lý bằng `os.replace` (không dùng `git mv` thuần vì vài file mới tạo chưa được `git add`) rồi `git add -A data/output/` một lần ở cuối để git tự nhận diện rename. Có `--dry-run`; dòng nào wikilink không khớp file nào trên đĩa thì báo `[WARN]` và bỏ qua, không đoán tên.
4. **Đã chạy 2 vòng**: Vòng 1 (tên chỉ thêm `NNN_`, chưa bỏ dấu): 211 file. Vòng 2 (sau khi thêm bỏ dấu + giới hạn 40 ký tự vào `sanitize_filename`): `--dry-run` báo thêm 132 file cần đổi (tên vòng 1 còn dấu hoặc dài hơn 40), chạy thật khớp dry-run, 0 bị bỏ qua. Kiểm tra cuối: đối chiếu toàn bộ wikilink với file trên đĩa — **0 link gãy**; đối chiếu STT trong bảng với tiền tố `NNN` của cả 2 file Raw/Refine mỗi dòng — **0 lệch, 0 thiếu tiền tố**; quét toàn bộ tên file trong `data/output/` (trừ file mồ côi) — không còn tên nào có dấu hoặc dài hơn 40 ký tự (phần `Ten`, không tính tiền tố `NNN_` và hậu tố `_raw`/`_refine`).
5. **File mồ côi đã xử lý xong 12/10/2026** (TS. Hà đã duyệt):
   - 3 nội dung chưa từng có dòng trong bảng (đọc dòng `> **Reference:**` đầu mỗi file Raw để lấy lại URL): `12 chữ giúp nhìn thấu kẻ giả nhân giả nghĩa bên cạnh bạn` (STT 110), `Sự Kiện Ngày 11.9` (STT 111), `NÂNG CẤP_ GIỌNG NÓI - GIAO TIẾP - THUYẾT TRÌNH - NGÔN TỪ` (STT 112) — đã thêm dòng mới vào bảng rồi chạy `rename_output_files.py` để ra tên `NNN_Ten` chuẩn.
   - 3 nội dung là bản trùng của dòng đã có sẵn (cùng URL, đối chiếu `> **Reference:**`): `66M views · 781K reactions` trùng STT 86, `How to study English as a busy person _ The English Podcast` trùng STT 15, `The Powerful Speech...-cce91ef8` trùng STT 28 (chỉ có Raw) — đã `git rm` cả 5 file sau khi TS. Hà duyệt xóa.
   - `vo cuc- am duong` (nguồn file cục bộ `.mp4`, không phải link — theo thiết kế không ghi vào bảng, xem `main()`): giữ nguyên, tên đã sẵn 16 ký tự không dấu, không cần đổi.
   - Kiểm tra cuối: 0 link gãy, 0 tên file sai quy ước (dấu/quá 40 ký tự) trong các file có dòng trong bảng, 0 lệch STT, chỉ còn `vo cuc- am duong` là "mồ côi" đúng thiết kế (file cục bộ).
