# Kế hoạch lưu media khi xử lý link

## Mục tiêu

- Khi vào Menu 4 và chọn `A` (toàn bộ danh sách) hoặc `O` (nhập link mới), cho phép chọn lưu MP4 và MP3.
- File được lưu lần lượt tại `data\mp4` và `data\mp3`.
- Nếu không có cấu hình hoặc cấu hình khác `Yes`, mặc định không lưu.
- Có thể lưu lựa chọn lâu dài trong `.env` bằng:

```dotenv
save-mp4: Yes
save-mp3: Yes
```

## Thiết kế

1. Batch file đọc hai khóa `save-mp4` và `save-mp3` không phân biệt hoa thường.
2. Nếu khóa chưa có giá trị `Yes`, batch hỏi `Y/N` cho lần chạy hiện tại; Enter/giá trị khác `Y` là `No`.
3. Batch truyền kết quả lần chạy qua biến môi trường `SAVE_MP4` và `SAVE_MP3` cho Python.
4. Python chỉ lưu khi biến môi trường chính xác là `Yes`; mọi giá trị thiếu/khác `Yes` đều là `No`.
5. MP3 tải để bóc băng sẽ được di chuyển sang `data\mp3` khi cần lưu; nếu không lưu thì vẫn dọn file tạm như hiện tại.
6. Khi cần lưu MP4, yt-dlp tải thêm bản video và đặt trực tiếp vào `data\mp4`.

## Kiểm tra

- Rà soát các nhánh `A`, `O`, chọn link số và các lần chạy không có `.env`.
- Xác nhận không tạo thư mục/file media nếu cấu hình không phải `Yes`.
- Xác nhận file `.env` hiện có không bị ghi đè.

## Sửa lỗi `This video is not available` (STT 50 - `tUCyf4jvwWs`)

### Kết quả kiểm chứng ngày 23/09/2026

Đã thử lại link STT 50 bằng `.venv` của dự án, yt-dlp `2026.08.19`, lần lượt qua từng `player_client` của YouTube:

| player_client | Kết quả |
| --- | --- |
| `default` (web) | ERR `This video is not available` |
| `android` | **OK** - tiêu đề `CLIP 01   Dap dat`, 5 format |
| `ios` / `mweb` / `web_safari` / `web_embedded` | Lấy được metadata, chỉ báo `Requested format is not available` |
| `tv` | ERR `The page needs to be reloaded` |
| `tv_embedded` | ERR `This video is not available` |

Đã tải thử thật bằng client `android`: yt-dlp lấy 8.74 MiB, FFmpeg chuyển thành `tUCyf4jvwWs.mp3` (4.65 MB, 194 giây) thành công. File thử đã xóa, không đụng vào dữ liệu dự án.

**Kết luận:** Video **không** bị xoá hay riêng tư. Lỗi chỉ đến từ client `web` mặc định bị YouTube từ chối. Nhận định cũ trong bản kế hoạch trước - coi `This video is not available` là lỗi vĩnh viễn và bỏ qua link - là **sai** và phải được gỡ, vì nó làm mất vĩnh viễn những link thực ra tải được.

### Liên hệ với STT 51

Video STT 51 hướng dẫn sửa lỗi này ở phía trình duyệt: giảm chất lượng phát, tắt gia tốc phần cứng, xóa cache/cookie. Ba biện pháp này không áp dụng cho yt-dlp, nhưng ánh xạ được sang hai ý dùng được:

- "Giảm chất lượng / đổi cách phát" tương đương đổi `player_client` và nới lỏng chuỗi `format`.
- "Xóa cache và cookie" tương đương làm mới cookie đưa cho yt-dlp - giữ làm phương án cuối.

### Thiết kế bản sửa

1. Thêm hằng `YOUTUBE_CLIENT_FALLBACKS = ['default', 'android', 'ios', 'mweb', 'tv']`, thứ tự dựa trên bảng kiểm chứng ở trên.
2. Thêm hàm `thu_tung_client(base_opts, url, action)` chạy lần lượt các client, trả về `(ket_qua, client_thanh_cong)`; client `default` không gắn `extractor_args`, các client còn lại gắn `{'youtube': {'player_client': [client]}}`.
3. Chỉ áp dụng vòng lặp này cho URL YouTube; link Facebook, Substack, Aeon giữ nguyên luồng cũ.
4. `main()` - bước lấy metadata gọi `thu_tung_client`; ghi nhớ client thành công và truyền xuống `download_media()` để ba bước sau không phải dò lại.
5. `download_media()` - cả ba nhánh MP4, phụ đề và audio dùng client đã chọn. Nếu nhánh audio vẫn hỏng thì dò lại toàn bộ danh sách client một lần nữa trước khi bỏ cuộc.
6. Nới `format` cho nhánh audio thành `bestaudio/bestaudio*/best` và cho nhánh MP4 thành `bestvideo+bestaudio/best/worst`, để tránh `Requested format is not available` ở các client chỉ trả về ít format.
7. Chỉ gọi `ghi_loi_md()` và bỏ qua link khi **mọi** client đều thất bại. Thông điệp ghi vào bảng đổi thành `Tai that bai (da thu N client)` thay vì `Link khong kha dung`.
8. Gỡ nhánh thoát sớm theo `loi_vinh_vien()` ở bước metadata. Giữ lại `PERMANENT_ERROR_PATTERNS` nhưng thu hẹp phạm vi: chỉ dùng cho các mẫu thật sự tuyệt đối (`private video`, `removed by the uploader`, `account ... has been terminated`), bỏ `video is not available` và `video unavailable` khỏi danh sách.
9. Bổ sung tùy chọn cuối trong `.env`:

```dotenv
yt-cookies-from-browser: chrome
```

   Khi có khóa này và mọi client đều hỏng, thử thêm một lượt với `cookiesfrombrowser`. Không có khóa thì bỏ qua, không tự ý đọc cookie của người dùng.

10. Log rõ client đang dùng, ví dụ `[INFO] Thu client: android` và `[SUCCESS] Lay duoc thong tin qua client: android`, để lần sau đọc log biết ngay client nào còn sống.

### Giữ nguyên các sửa đã đúng

Hai điểm sau trong bản trước vẫn giữ, vì độc lập với chẩn đoán sai ở trên:

- Tách nhánh tải MP4 ra khỏi khối `try` của phụ đề (trước đây lỗi MP4 bị in nhầm nhãn `[WARN] Loi tai phu de` và làm bỏ luôn bước tải phụ đề).
- Cắt thông điệp lỗi còn một dòng, tối đa 160 ký tự.

### Kiểm tra

- Chạy lại đúng link STT 50, kỳ vọng ra tiêu đề `CLIP 01   Dap dat` và sinh được `_raw.md` cùng `_refine.md`; sau đó sửa dòng 50 trong `build-audio2md.md` từ `Failed` thành `Done`.
- Chạy lại một link YouTube đang `Done` (ví dụ STT 49) để chắc client `default` vẫn được ưu tiên và không tăng số lần gọi mạng cho link bình thường.
- Chạy một link Facebook để xác nhận luồng không-YouTube không bị ảnh hưởng.
- Chạy với `save-mp4: Yes` để kiểm tra nhánh MP4 dùng đúng client đã chọn.
- Kiểm tra một link thật sự đã bị xoá, kỳ vọng thử hết client rồi mới ghi `Tai that bai (da thu N client)`.

### Trạng thái triển khai - 23/09/2026

Đã code xong toàn bộ 10 mục trên trong `src/main_audio2md.py`. Bản gốc trước khi sửa được giữ tại `src/main_audio2md.py.bak-20260923-140541` để hoàn tác nếu cần.

Kết quả chạy thật:

| Trường hợp | Kết quả |
| --- | --- |
| STT 50 `tUCyf4jvwWs` | `default` hỏng → `android` OK → tải 8.74 MiB → `CLIP 01 Dap dat_raw.md` + `_refine.md`, dòng 50 chuyển `Done` |
| STT 49 `kcNa2l6_Z1k` | Thành công ngay ở `default`, không phát sinh thêm lần gọi mạng |
| Link không phải YouTube | Chỉ chạy 1 lượt, luồng cũ giữ nguyên |
| Video thật sự đã xoá | Thử hết 5 client rồi mới báo thất bại |

Khoá `.env` tuỳ chọn cho phương án cuối:

```dotenv
yt-cookies-from-browser: chrome
```

## Phân tích chất lượng MP4 và đề xuất biến `quality`

### Đo đạc ngày 23/09/2026

Số format mỗi `player_client` trả về:

| client | STT 50 `tUCyf4jvwWs` | STT 49 `kcNa2l6_Z1k` |
| --- | --- | --- |
| `default` (web) | lỗi, không dùng được | 36 format, 25 video, tối đa **1080p** |
| `android` | 5 format, 1 video muxed **360p** | 5 format, 1 video muxed **360p** |
| `ios` / `mweb` / `web_safari` | 4 format, **0 video, 0 audio** | 4 format, **0 video, 0 audio** |
| `tv` | lỗi | lỗi |

So sánh kích thước khi đổi chuỗi `format` (STT 49, client `default`):

| Chuỗi format | Chọn ra | Dung lượng |
| --- | --- | --- |
| `bestvideo+bestaudio/best/worst` (đang dùng) | 248 (1080p) + 251 | 39.1 MiB |
| `bestvideo*+bestaudio/best` (tức "quality tối đa") | 248 (1080p) + 251 | **39.1 MiB - y hệt** |
| Giới hạn `<=1080` | 248 (1080p) + 251 | 39.1 MiB |
| Giới hạn `<=720` | 247 (720p) + 251 | 34.7 MiB |
| `best` (chỉ muxed) | lỗi - client `default` không có format muxed nào |

### Kết luận

1. **MP4 360p không phải do chuỗi `format`.** Nó do client: `android` chỉ trả về đúng một format muxed 360p. Trần chất lượng nằm ở client, không nằm ở bộ chọn format.
2. **Luồng hiện tại đã luôn lấy chất lượng cao nhất** mà client cho phép. `bestvideo+bestaudio` đã là tối đa; thêm `quality: Yes` để "lấy max" là **no-op**, không đổi được một byte nào.
3. Với riêng STT 50, không có cấu hình nào cứu được độ phân giải: `default` bị chặn, `android` chỉ có 360p, `ios`/`mweb` không có format tải được. 360p là tất cả những gì YouTube trả về cho link này.
4. Chênh lệch 1080p với 720p chỉ 39.1 so với 34.7 MiB, tức **11%**. Đổi lấy một biến cấu hình mới thì không đáng.

### So sánh hai phương án

| | Giữ nguyên (không thêm biến) | Thêm `quality: Yes` |
| --- | --- | --- |
| Chất lượng khi client tốt | Đã tối đa (1080p) | Vẫn 1080p, không hơn |
| Chất lượng khi phải fallback | 360p (trần của client) | Vẫn 360p |
| Giải quyết được STT 50 | Không | Không |
| Ý nghĩa thực tế | Không cần | Chỉ có ý nghĩa nếu **đảo chiều**: mặc định giới hạn `<=720` cho nhẹ, `Yes` mới mở khoá tối đa |
| Chi phí | 0 | Thêm khoá `.env`, thêm nhánh batch, thêm đường code cần kiểm thử |

**Quyết định cập nhật 26/09/2026:** không thêm `quality: Yes`; dùng `MP4_MAX_HEIGHT` để đặt trần độ phân giải 720p hoặc 1080p.

### Hai sửa đổi đã áp dụng kèm theo

1. Nhánh phụ đề chỉ còn thử đúng client mà bước metadata đã chọn. Kiểm chứng: STT 50 giờ chỉ 1 lần thử thay vì 5.
2. Bỏ `/worst` khỏi chuỗi format MP4 (`bestvideo*+bestaudio/best`). `/worst` là bẫy chất lượng: khi nhánh đầu hỏng, nó sẽ chọn đúng format tệ nhất thay vì format tốt nhất còn lại.
3. Thêm cảnh báo khi MP4 phải tải qua client thay thế, nói rõ trần 360p.

## Bổ sung: Menu 4 > O nhận link kênh YouTube

### Mục tiêu

Khi ở Menu 4 chọn `O` và dán một link kênh thay vì link video, ví dụ:

```
https://www.youtube.com/@dungnguyenquoc8200/videos
```

thì hiển thị danh sách video của kênh, đánh số để chọn một hoặc nhiều, hoặc chọn `A` để xử lý toàn bộ.

### Khảo sát thực tế ngày 23/09/2026

Đã thử chính link kênh trên bằng `.venv` của dự án:

- yt-dlp trả về `_type = playlist`, tiêu đề `Dũng Nguyễn Quốc - Videos`, **34 video**.
- Với `extract_flat='in_playlist'`, toàn bộ danh sách lấy xong trong **1.3 giây** và đã có sẵn `id`, `title`, `duration` cho từng video. Không phải gọi mạng cho từng video một.
- Video `tUCyf4jvwWs` ở STT 50 chính là `CLIP 01 Dap dat` của kênh này.

Kết luận: chỉ cần **một** lần gọi `extract_info(..., download=False)` với `extract_flat` là dựng được menu. Chi phí không đáng kể.

### Quyết định đã chốt với người dùng

| Vấn đề | Lựa chọn |
| --- | --- |
| Kênh nhiều video | Phân trang **20 video/trang**, gõ `N`/`P` để sang trang sau/trước |
| Thời điểm ghi vào `build-audio2md.md` | Ghi **dần sau mỗi video xong**, không ghi trước hàng loạt |
| Video đã có trong danh sách | **Tự bỏ qua**, báo số lượng đã bỏ |
| Chọn `A` cho cả kênh | **Hỏi xác nhận** kèm số video và ước tính lượt gọi Gemini |

### Thiết kế

#### 1. Đặt phần chọn kênh trong Python, không trong batch

Viết mới `src/chon_video_kenh.py`. Batch chỉ gọi một lệnh và nhận lại file danh sách link; toàn bộ phân trang, phân tích cú pháp lựa chọn và lọc trùng nằm trong Python. Lý do: vòng lặp phân trang với `setlocal enabledelayedexpansion` trong cmd rất dễ vỡ khi tiêu đề video chứa `!`, `%`, `&` hoặc dấu tiếng Việt - đúng loại ký tự mà kênh ví dụ đang có.

#### 2. Batch chỉ thêm một bước, không phân nhánh

Trong `:ADD_NEW_LINK`, sau khi đọc `newlink` và trước khi kiểm tra trùng, gọi:

```bat
"%PYTHON%" "src\chon_video_kenh.py" "!newlink!" "%TEMP_LIST%"
```

Script tự quyết định:

- Link video đơn lẻ: ghi thẳng một dòng vào `%TEMP_LIST%` và thoát với mã `0`. Luồng `O` hiện tại giữ nguyên hành vi.
- Link kênh hoặc playlist: hiện menu chọn, ghi các link đã chọn vào `%TEMP_LIST%`.
- Người dùng chọn `0` để quay lại: thoát với mã `2`, batch quay về `MENU_LINK`.
- Lỗi mạng hoặc kênh rỗng: thoát với mã `1`, batch báo lỗi và `pause`.

Nhờ vậy cmd không cần tự nhận dạng URL kênh.

#### 3. Nhận dạng link kênh

Coi là kênh hoặc playlist khi host là YouTube và path khớp một trong các dạng:

- `/@<handle>` kèm hậu tố tuỳ chọn `/videos`, `/streams`, `/shorts`, `/playlists`
- `/channel/<id>`, `/c/<name>`, `/user/<name>`
- có tham số `list=`

Mọi dạng còn lại coi là video đơn lẻ. Link không phải YouTube cũng đi thẳng, không đổi hành vi.

Chuẩn hoá trước khi đưa cho yt-dlp: nếu là `/@handle` trần thì thêm `/videos`, để lấy tab video thay vì trang giới thiệu kênh.

#### 4. Lọc trùng

Đọc `data/input/build-audio2md.md`, dựng tập khoá bằng chính hàm `canonical_url()` sẵn có trong `main_audio2md.py` - dùng lại, không viết hàm so sánh mới. Video đã có khoá trùng thì loại khỏi danh sách hiển thị, và in một dòng tổng kết:

```
[INFO] Kenh co 34 video | 3 video da co trong danh sach, da bo qua | con 31 video
```

Nếu sau khi lọc không còn video nào thì báo và quay lại `MENU_LINK`.

#### 5. Giao diện chọn

Đánh số **toàn cục** từ 1 đến hết, không đánh lại theo từng trang, để gõ `25` từ trang 1 vẫn đúng video.

```
=== Dũng Nguyễn Quốc - Videos | 31 video | Trang 1/2 ===
  [ 1]  3:12  CLIP 02   Dap da do
  [ 2]  6:04  CLIP 32   Ung pho khan cap
  ...
  [20]  4:31  CLIP 13   Dam nen
-------------------------------------------------------
 Go so de chon (VD: 1 hoac 1,3,5 hoac 2-4)
 [N] Trang sau   [P] Trang truoc
 [A] Chon toan bo 31 video
 [0] Quay lai
```

Cú pháp chọn dùng lại đúng quy ước của Menu 4 hiện có: số đơn, danh sách ngăn bằng dấu phẩy, khoảng chạy bằng dấu gạch nối. Chấp nhận trộn lẫn, ví dụ `1,5,8-12`.

#### 6. Xác nhận khi chọn A

```
[?] Se xu ly 31 video, uoc tinh 31-62 luot goi Gemini. Tiep tuc (Y/N)?
```

Ước tính là một khoảng vì video có phụ đề chỉ tốn 1 lượt (refine), video phải bóc băng tốn 2 lượt (transcribe và refine). Enter hoặc giá trị khác `Y` là huỷ.

Chỉ hỏi khi chọn `A`. Chọn tay dưới 10 video thì không hỏi.

#### 7. Thay đổi bắt buộc trong `update_md_table()`

Đây là điểm chặn thật sự, cần làm trước khi tính năng chạy được.

Hiện tại `update_md_table()` chỉ **sửa dòng đã có**; không tìm thấy dòng khớp thì in `[WARN] Khong tim thay dong cho link` rồi bỏ qua. Vì thế luồng `O` hiện nay phải chèn sẵn một dòng `Pending` vào file md **trước** khi chạy Python.

Quyết định "ghi dần sau mỗi video xong" không đi được với cơ chế đó. Cần bổ sung nhánh chèn: khi không tìm thấy dòng khớp, tự thêm dòng mới ngay dưới header, với `STT` bằng số lớn nhất hiện có cộng một, và thời gian là lúc xử lý xong. Sau khi có nhánh này thì gỡ phần chèn dòng `Pending` trong `:ADD_NEW_LINK` của batch, vì đã thừa.

Lợi ích kèm theo: ngắt giữa chừng bằng Ctrl+C không để lại dòng `Pending` mồ côi - đúng lý do đã chọn phương án này.

#### 8. Thứ tự xử lý

Giữ nguyên thứ tự yt-dlp trả về, tức mới nhất trước. Ghi vào bảng thì video xử lý xong sau sẽ có STT lớn hơn, nhất quán với cách bảng đang hoạt động.

### Kiểm tra

- Dán đúng link `https://www.youtube.com/@dungnguyenquoc8200/videos`, kỳ vọng thấy 34 video trừ đi số đã có trong bảng, chia 2 trang.
- Chọn một số lẻ, ví dụ `3`, xác nhận chỉ một video được xử lý và bảng thêm đúng một dòng.
- Chọn hỗn hợp `1,5,8-10`, xác nhận ra đúng 6 video.
- Gõ `N`, `P` ở trang đầu và trang cuối, xác nhận không nhảy ra ngoài phạm vi.
- Chọn `A` rồi trả lời `N`, xác nhận không xử lý gì và quay lại menu.
- Dán link video đơn lẻ như `https://www.youtube.com/watch?v=tUCyf4jvwWs`, xác nhận luồng `O` cũ không đổi, không hiện menu chọn.
- Dán link không phải YouTube, ví dụ Facebook hoặc Aeon, xác nhận đi thẳng như cũ.
- Dán link kênh mà **mọi** video đều đã có trong bảng, kỳ vọng báo hết trùng và quay lại menu.
- Kiểm tra tiêu đề có dấu tiếng Việt và ký tự `!`, `&` hiển thị đúng trong cửa sổ cmd.
- Ctrl+C giữa chừng khi đang chạy `A`, xác nhận bảng chỉ có các dòng đã hoàn tất, không còn dòng `Pending`.

### Trạng thái triển khai - 23/09/2026

Đã code xong. File mới: `src/chon_video_kenh.py`. File sửa: `src/main_audio2md.py` (hàm `them_dong_moi()`), `audio2md.bat` (nhánh `:ADD_NEW_LINK`). Backup: `audio2md.bat.bak-20260923-142712` và `src/main_audio2md.py.bak2-20260923-142713`.

Kết quả kiểm tra trên kênh `@dungnguyenquoc8200`:

| Kịch bản | Kết quả |
| --- | --- |
| Liệt kê kênh | 34 video, bỏ qua 2 đã có, còn 32, chia 2 trang |
| Chọn `3` | 1 link, đúng `CLIP 30` |
| Chọn `1,5,8-10` | 5 link |
| Chọn `A` rồi `N` | Hiện "uoc tinh 32-64 luot goi Gemini", huỷ, mã thoát 2 |
| Chọn `A` rồi `Y` | 32 link |
| Chọn `0` hoặc nhập sai | Báo lỗi rồi quay lại, mã thoát 2 |
| `P` ở trang 1, `N` quá trang cuối | Dừng ở 1/2 và 2/2, không vượt biên |
| Link video đơn lẻ, Facebook, Aeon | Đi thẳng, luồng `O` cũ không đổi |
| Kênh mà mọi video đều đã có | Báo và thoát với mã 1 |
| Tiêu đề tiếng Việt có dấu | Hiển thị đúng `Dũng Nguyễn Quốc - Videos` |
| Chạy trọn vẹn 1 video | `CLIP 30` ra `_raw.md` + `_refine.md`, bảng tự thêm dòng STT 53 |

Điều chỉnh so với plan: `/watch?v=X&list=Y` được coi là **video đơn lẻ** chứ không phải playlist, vì dán link đó thường là muốn đúng video đang xem.

Ghi nhận thêm từ lần chạy thật: video `CLIP 30` tải MP4 qua client `default` nên ra 56 MB, trong khi `CLIP 01` phải dùng `android` nên chỉ 9 MB ở 360p. Đúng như phần phân tích chất lượng phía trên - trần chất lượng nằm ở client. Nhánh audio của cùng video này bị `403 Forbidden` ở `default` và được `android` cứu, cho thấy cơ chế fallback có giá trị thật ngay cả với video bình thường.

## Quyết định cuối ngày 26/09/2026: nhập nhiều link và độ phân giải MP4

### Menu 4 > O: nhiều link trong một lần nhập

Cho phép dán nhiều URL, phân cách bằng dấu phẩy `,` hoặc chấm phẩy `;`, ví dụ `https://youtu.be/AAA, https://youtu.be/BBB; https://youtu.be/CCC`. `audio2md.bat` chuyển chuỗi nhập cho `src/chon_video_kenh.py`; script tách URL, kiểm tra cú pháp, loại link trùng trong lần nhập, giữ đúng thứ tự rồi ghi `%TEMP_LIST%`. Link kênh/playlist vẫn mở menu chọn video. `src/main_audio2md.py` đọc danh sách và xử lý lần lượt từng link bằng chính cơ chế hiện có: kiểm tra file raw/refine đã tồn tại, chọn ghi đè nếu cần, thử client tải, dùng API free/paid theo cấu hình, tạo raw/refine và cập nhật bảng sau từng video hoàn tất. Không thêm luồng xử lý song song.

### `MP4_MAX_HEIGHT` trong `.env`

```dotenv
save-mp4: Yes
MP4_MAX_HEIGHT=1080
```

- Chỉ nhận `720` hoặc `1080`; mặc định `1080` nếu thiếu hoặc giá trị không hợp lệ (có cảnh báo). Bộ đọc `.env` cũng chấp nhận `mp4-max-height: 720` và chuẩn hóa tên biến thành `MP4_MAX_HEIGHT`. Biến môi trường hệ thống có trước được ưu tiên theo cơ chế `setdefault` hiện tại.
- Khi bật lưu MP4, yt-dlp chọn bản video tốt nhất với `height <= MP4_MAX_HEIGHT` cùng bản audio tốt nhất; nếu chỉ có format video kèm audio thì chọn bản đó với cùng giới hạn. Không tự mã hóa lại, không nâng độ phân giải. Giá trị 1080 có thể cho kết quả 720p/360p nếu nguồn hoặc client chỉ cung cấp mức đó.
- Giá trị này chỉ áp dụng cho nhánh tải MP4; tải phụ đề, audio, bóc băng và refine giữ nguyên. `merge_output_format='mp4'` chỉ gộp luồng; codec/container đầu ra còn phụ thuộc format nguồn và khả năng remux của FFmpeg.
- 720p và 1080p **không bảo đảm** kích thước file dưới 100 MiB. Người dùng sẽ lưu file lớn ở nơi khác, ngoài Git. Không triển khai nén, chia MP4, Git LFS hoặc giới hạn kích thước tự động trong luồng này.

### Đã gỡ lựa chọn nén

`install-ffmpeg.bat` trở lại nhiệm vụ cài FFmpeg; mục nén theo dung lượng và script `src/compress_mp4.py` đã được gỡ. Việc lưu MP4 trong `data/mp4` tiếp tục độc lập với Git; trước khi `git add` cần tự chọn file nào đưa vào repo.

## Báo cáo kiểm thử Menu 4 > O - Facebook (26/09/2026)

### Phạm vi và cách chạy

- Đưa cả 9 URL Facebook được cung cấp vào cùng một lần nhập, dùng lẫn dấu phẩy và chấm phẩy. `src/chon_video_kenh.py` trả mã `0`, ghi đủ **9/9** dòng vào danh sách tạm và giữ nguyên thứ tự. Facebook không bị nhận nhầm là kênh/playlist YouTube.
- Kiểm tra metadata từng URL bằng yt-dlp `2026.08.19`, `--no-playlist --skip-download`, retry 1 lần và timeout socket 20 giây. Không gọi Gemini, không tạo Raw/Refine, không sửa `build-audio2md.md`.
- Lần chạy trong sandbox bị chặn socket (`WinError 10013`), nên đã chạy lại kiểm tra chỉ-đọc với quyền mạng được cấp. Đây là hạn chế môi trường kiểm thử, không phải lỗi extractor hay lỗi URL.

### Kết quả metadata

| # | Dạng URL | Facebook ID yt-dlp trả về | Kết quả |
| --- | --- | --- | --- |
| 1 | `share/v` | `1098019352722484` | OK |
| 2 | `reel` | `28418718337757346` | OK |
| 3 | `share/v` | `1393744849563148` | OK |
| 4 | `reel` | `2055824531687843` | OK |
| 5 | `reel` | `1078823508147335` | OK |
| 6 | `share/r` | `2967710353598344` | OK |
| 7 | `share/v` | `8062875617070517` | OK |
| 8 | `share/r` | `1048530048012924` | OK |
| 9 | `share/r` | `3397896720372666` | OK |

### Kết luận và giới hạn

- Menu 4 > O nhận đúng danh sách hỗn hợp `share/v`, `share/r` và `reel`; nhánh Facebook chỉ chạy client mặc định, đúng thiết kế không ảnh hưởng fallback YouTube.
- Không tải toàn bộ MP4 trong lần kiểm tra này: thao tác đó có thể tạo nhiều file lớn trong `data/mp4`. Cấu hình lưu đã sẵn sàng: đặt `save-mp4: Yes` và tùy chọn `MP4_MAX_HEIGHT=720` hoặc `1080`, rồi chạy luồng bình thường để tải trực tiếp vào `data/mp4`.
- Không gọi pipeline Gemini để tránh phát sinh transcript/API không được yêu cầu cho kiểm thử kết nối và chọn link. Cần chạy Menu 4 > O hoàn chỉnh khi muốn tạo Raw/Refine cho các video này.

