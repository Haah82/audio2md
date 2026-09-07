---
title: "Kế hoạch Tkinter cho PDF2MD"
date: 2026-09-05
status: "Chờ triển khai"
tags: [pdf2md, tkinter, mvp]
aliases: [Kế hoạch giao diện PDF2MD]
---

# Kế hoạch Tkinter cho PDF2MD

Bản cập nhật này thay các quy định cũ về quét một tầng, bảng phẳng, hậu tố output và tự bỏ qua file đã tồn tại. Phạm vi hiện tại là sửa kế hoạch và ảnh; chưa triển khai ứng dụng.

## 1. Yêu cầu đã thống nhất

- BAT có ba tác vụ: `[1] Cài đặt`, `[2] Mở GUI`, `[3] Git Sync`; `[0] Thoát`.
- GUI có ba mục `Xuất Markdown`, `Chuyển file Office`, `Tóm tắt file md`. Mục Markdown giữ tác vụ cũ 2 đến 6, thêm PPTX Native, PPTX Scan và PPTX Refine. Summary đọc Markdown và tạo `<stem>_summary.md` qua Gemini Flash API.
- Khi mở GUI, tự quét `data/input` cùng toàn bộ thư mục con theo phần mở rộng của tác vụ. Không cần bấm Browse trước.
- Nút `Duyệt (Browse)` cho chọn file hoặc thư mục ở nơi khác. Hiển thị cây thư mục kiểu Explorer cho cả nguồn mặc định và nguồn ngoài.
- Mục Markdown xuất vào `data/output`, giữ tên gốc, đổi phần mở rộng thành `.md`, giữ cấu trúc thư mục con tương đối với gốc nguồn. Mục Chuyển file Office xuất cạnh từng file nguồn, không dùng `data/output`.
- Chuyển file Office hỗ trợ `.doc` sang `.docx`, `.ppt` sang `.pptx`, `.xls` sang `.xlsx`; có tùy chọn hỏi tên mới từng file và xóa file gốc sau khi kiểm tra kết quả.
- Nếu đường dẫn output đã tồn tại, hỏi `Thay thế (Replace)` hoặc `Bỏ qua`. Bỏ qua không chạy conversion, không gọi API.
- Lịch sử lưu `ROOT/history/yyyy-mm.log`, bản ghi mới nhất ở trên, tự chuyển file khi sang tháng mới.
- Phần chọn nguồn, quét, cây, đường dẫn, kiểm tra trùng, ghi lịch sử và điều phối dùng thư viện chuẩn Python. Giữ thư viện chuyển đổi hiện có; không thể đọc PDF/Office và gọi Gemini chỉ bằng thư viện chuẩn mà vẫn giữ engine hiện tại.

### Quy tắc ngôn ngữ

Plan, nhãn GUI, thông báo, log, comment và docstring mới dùng tiếng Việt có dấu; giữ thuật ngữ tiếng Anh như Browse, Replace, Local, API, Treeview. Trong `.bat`, chữ hiển thị và comment dùng tiếng Việt không dấu. Tên biến/hàm mới do dự án tự định nghĩa dùng tiếng Việt không dấu dạng `snake_case`; tên API, tham số CLI và khóa dữ liệu kỹ thuật giữ nguyên khi cần tương thích.

Không dùng gạch ngang dài, emoji, icon AI, logo hay icon trang trí. Chỉ giữ điều khiển hệ thống như nút đóng cửa sổ, scrollbar và tam giác mở cây. Viết mô tả cụ thể; phân biệt điều đã kiểm tra, thiết kế dự kiến và tính năng đã chạy. Không ghi số đo hiệu năng hoặc khả năng API chưa được kiểm chứng thành kết luận.

## 2. Cơ sở từ mã hiện có

Nguồn: [[pdf-2-md.bat]], `refer-2-convert_font/gui_app.py`, `ui_state.py`, `batch_io.py` và các script trong `src`.

| Tác vụ cũ | Script | Hành vi hiện tại cần giữ hoặc điều chỉnh |
|---|---|---|
| 2, PDF Native | `2_pdf_native.py` | Nhận nhiều file, `--list`, `--jobs`, `--force`; ProcessPoolExecutor tối đa 4 worker theo mặc định; có exit code tổng hợp |
| 3, PDF Scan | `3_pdf_scan.py` | Gemini, chunk 40 trang, tách ảnh; có thể xuất kết quả thiếu chunk |
| 4, Word | `4_word.py` | Mammoth, markdownify; nhận một file hoặc ALL |
| 5, Excel | `5_excel.py` | pandas/openpyxl; nhận một file hoặc ALL |
| 6, Refine | `6_gemini_refine.py` | Mode 1 PDF, 2 Excel, 3 Word; gửi tài liệu gốc, không sửa Markdown đã sinh |
| 7, Git Sync | `git_sync.py` | Giữ pull, kiểm tra secret và xác nhận commit/push hiện có |

BAT hiện quét một tầng bằng picker và dùng file tạm cố định. GUI mới thay toàn bộ picker này bằng Python. Native hiện xuất `_native.md`, Scan `_scan.md`, Refine `_refined.md`; tên mới trong luồng GUI sẽ là `<tên gốc>.md`. Đây là thay đổi có chủ đích theo yêu cầu giữ tên gốc, không di chuyển hoặc đổi tên output cũ tự động.

Script 3 đến 6 có đường đi chỉ print lỗi rồi return, nên exit code 0 chưa đủ để báo thành công. Scan có thể ghi Markdown thiếu chunk rồi lần sau bỏ qua vì file tồn tại. Refine hiện có thể ghi đè mà không hỏi. Các điểm này phải sửa cùng hợp đồng output.

### Kế thừa convert-font

| Thành phần | Kế thừa | Điều chỉnh |
|---|---|---|
| `tao_ung_dung()` | Một Tk, ttk, theme Windows | Một màn hình chung, không cần hai tab File/Thư mục vì Browse đã cung cấp hai lựa chọn |
| `TabXuLyFile` | File dialog và kiểm tra lựa chọn | Không chạy conversion trong callback Tk |
| `TabXuLyThuMuc` | Treeview, progress, snapshot danh sách, cờ đang chạy | Treeview phân cấp; quét đệ quy nền; khóa mọi điều khiển nguồn khi chạy |
| `ui_state.py` | Tách trạng thái khỏi widget | Trạng thái nguồn, tác vụ, xung đột output và job |
| `batch_io.py` | Gom kết quả, xử lý lỗi từng file | Registry theo tác vụ, mapping output, giữ batch Native |

Không import nguyên thư mục tham khảo: mã đang dùng `convert_font.*`, không khớp tên `refer-2-convert_font`. Không mang engine chuyển font hoặc Clipboard vào PDF2MD. Module PPTX chuyển font cũng không phải bộ trích xuất Markdown; chỉ tham khảo cách duyệt shape/đoạn văn, không dùng thay engine PPTX mới.

Đã kiểm tra import Tk trong venv: Python 3.12.10, Tk 8.6. Chưa thử cửa sổ ở các mức DPI, chưa benchmark conversion và chưa gọi Gemini trong quá trình lập kế hoạch.

## 3. Menu và nguồn dữ liệu

### Menu BAT

```text
CHUYEN TAI LIEU SANG OBSIDIAN MARKDOWN
[1] Cai dat moi truong (Setup)
[2] Mo giao dien xu ly (Tkinter)
[3] Dong bo GitHub (Git Sync)
[0] Thoat
Chon tac vu (0-3):
```

Bỏ mục A khỏi menu mới; giữ CLI cũ để dùng riêng. Không tự chạy Local rồi Scan/Refine nối tiếp.

### Combo tác vụ và bộ lọc

| Nhãn GUI | Bộ lọc |
|---|---|
| PDF gốc (Native PDF), Local | `.pdf` |
| PDF ảnh/scan (Scanned PDF), Gemini | `.pdf` |
| Microsoft Word (.docx), Local | `.docx` |
| Microsoft Excel (.xlsx), Local | `.xlsx` |
| Microsoft PowerPoint (.pptx), Native Local | `.pptx` |
| PowerPoint ảnh/scan (.pptx), Gemini API | `.pptx` |
| Hiệu đính (Refine), Gemini API | Theo combo phụ: PDF Scan `.pdf`, Bảng Excel `.xlsx`, Bảng Word `.docx`, PowerPoint `.pptx` |

Thanh chọn chức năng trên GUI có `Xuất Markdown`, `Chuyển file Office`, `Tóm tắt file md`. Ba mục dùng chung nguồn Browse, cây Explorer, lựa chọn từng file/toàn bộ nhánh, kiểm tra trùng, runner và history. Đổi mục sẽ cập nhật combo, suffix và đích xuất, xóa selection cũ; không tự chuyển Office cũ rồi gọi API tiếp. Summary có bộ lọc `.md` và chính sách nguồn output/đích summary tại mục 4.

Nút `Xem Markdown` mở file `.md` đang chọn trong cửa sổ riêng. Đây là công cụ đọc và soạn thảo nhẹ, tách khỏi các lượt conversion. Mỗi lần mở hoặc tạo file mới tạo một cửa sổ mới, có thể resize, thu nhỏ/phóng to và đóng độc lập; đóng menu chính không tự ghi các cửa sổ còn thay đổi chưa lưu.

Nguồn mặc định là `ROOT/data/input`, tức `input` trong yêu cầu, không tạo thêm thư mục input song song ở gốc dự án. Mẫu `input/*.xxx` gồm cả `input/**/*.xxx`. Không suy đoán Native/Scan từ nội dung PDF.

### Nút Browse và gốc nguồn

- `Duyệt (Browse)` mở menu `Chọn file...` và `Chọn thư mục...`.
- Chọn thư mục: thư mục được chọn là gốc nguồn; quét nó và mọi thư mục con hợp lệ.
- Chọn file: dùng dialog chọn một hoặc nhiều file trong cùng thư mục. Thư mục cha của các file được chọn là gốc nguồn, quét đệ quy thư mục đó và chọn sẵn đúng các file vừa duyệt. File khác chỉ hiển thị, không tự chọn để chuyển đổi. MVP không cộng dồn nhiều gốc hoặc nhiều ổ đĩa trong một lượt.
- Hủy dialog giữ nguyên nguồn và selection hiện tại. Nút `Về input` đặt lại nguồn mặc định rồi quét theo tác vụ đang chọn.
- Đổi combo giữ gốc nguồn hiện tại, lọc/quét lại, bỏ selection cũ. Khi chưa Browse, luôn dùng input. Khởi động lần sau trở lại input, chưa lưu cấu hình nguồn gần nhất.
- Hàng nguồn hiện absolute path, bộ lọc và dòng `Bao gồm thư mục con`.
- Thiếu input: tạo thư mục rỗng; không có file phù hợp: hiện `Không tìm thấy file .xxx`, khóa Bắt đầu.

### Cây Explorer

Dùng `ttk.Treeview(show='tree headings', selectmode='extended')`: cột cây là tên thư mục/file; các cột còn lại là Trạng thái và Kết quả. Giữ thứ bậc tên thư mục con; chỉ hiển thị nhánh có file phù hợp. Thư mục trước file, sắp xếp ổn định không phân biệt hoa/thường.

Chọn nhiều file bằng Ctrl/Shift. Khi chọn dòng thư mục và bấm Bắt đầu, lấy các file phù hợp trong nhánh đó, bỏ trùng với file đã chọn riêng. `Chọn tất cả` áp dụng các file đang hiển thị sau tìm kiếm; thông báo tổng số file thực sự sẽ chạy trước Start. Tìm tên giữ các nút cha để không mất ngữ cảnh đường dẫn.

Quét nền bằng `os.scandir`, không đọc nội dung tài liệu. Bỏ file `~$`, không đi theo symlink/junction/reparse point trên Windows; bỏ các đường dẫn thực thuộc history/vùng tạm của dự án. Mục Xuất Markdown và Chuyển file Office loại output để không quét lại kết quả; mục Tóm tắt file md được phép đọc output nhưng loại `_summary.md`, assets và fixlog. Lỗi quyền truy cập một thư mục được báo trong nhật ký, các nhánh khác vẫn quét. Không cho chọn nguồn nằm trong history. Gắn mã phiên quét để bỏ kết quả cũ nếu người dùng đổi tác vụ khi đang quét.

## 4. Quy tắc output và trùng tên

### Mapping đường dẫn

```python
# Gốc nguồn là thư mục input hoặc thư mục đã chọn bằng Browse.
duong_dan_tuong_doi = tep_nguon.relative_to(goc_nguon)
tep_dich = goc_output / duong_dan_tuong_doi.with_suffix('.md')
```

| Gốc nguồn | File nguồn | File xuất |
|---|---|---|
| `data/input` | `data/input/quy-chuan/a.pdf` | `data/output/quy-chuan/a.md` |
| `data/input` | `data/input/du-an/b/c.docx` | `data/output/du-an/b/c.md` |
| `D:/Tai-lieu` | `D:/Tai-lieu/du-an/a.xlsx` | `data/output/Tai-lieu/du-an/a.md` |
| Browse file, gốc `D:/Tai-lieu/du-an` | `D:/Tai-lieu/du-an/a.pdf` | `data/output/du-an/a.md` |

Giữ dấu tiếng Việt, chữ hoa/thường và tên thư mục; chỉ đổi extension.

Gốc nguồn nằm ngoài thư mục mặc định thì thêm tên thư mục gốc đó làm một cấp thư mục trong đích. Quyết định này thay quy định cũ "gốc ngoài không được thêm thành một thư mục output nữa", chốt ngày 2026-09-05 sau khi thấy nguồn ngoài đổ thẳng vào gốc `data/output` gây lẫn kết quả giữa các đợt và dễ đụng tên. Nguồn nằm trong thư mục mặc định giữ nguyên cách tính cũ, không thêm cấp nào.

Quy tắc này dùng chung cho cả `data/output` của Xuất Markdown và `data/summary` của Tóm tắt file md; thư mục mặc định tương ứng là `data/input` và `data/output`.

Kiểm tra path chuẩn hóa còn nằm trong gốc nguồn/gốc output; không cho `..` hoặc symlink đưa output ra ngoài. Tạo thư mục đích khi thực sự có file cần xử lý, không tạo cho file đã Bỏ qua.

### Thay thế hoặc bỏ qua

1. Bấm Bắt đầu: chụp snapshot file, tác vụ, gốc nguồn và output; tính đường dẫn đích trước conversion.
2. Nếu nhiều input trong cùng lượt cùng ánh xạ tới một đích, yêu cầu bỏ bớt hoặc đổi tên trước khi chạy. Không cho hai worker ghi một output. File cùng basename ở hai thư mục khác nhau không xung đột.
3. Với mỗi output đã tồn tại, hiện dialog có path nguồn/đích và ba nút: `Thay thế (Replace)`, `Bỏ qua`, `Hủy lượt chạy`. Focus mặc định Bỏ qua; đóng dialog tương đương Hủy lượt chạy, không hiểu là Replace.
4. Thay thế: cho phép chạy lại file đó. Bỏ qua: giữ output, không khởi tạo converter, không tách ảnh, không upload và không gọi Gemini; vẫn ghi lịch sử Bỏ qua.
5. Thu đủ lựa chọn trước khi chạy, chưa thêm tùy chọn áp dụng hàng loạt trong MVP. Output không tồn tại được xếp hàng bình thường.
6. Kiểm tra lại output trước khi công bố kết quả. Nếu file xuất hiện/thay đổi sau khi đã hỏi, hỏi lại; không sử dụng sự đồng ý cũ để ghi đè một bản khác.

Native/Scan/Refine cùng nguồn nay có thể cùng đích `a.md`; đây cũng là xung đột phải hỏi, không tự đổi tên để né lựa chọn của người dùng. Không dùng quy tắc tồn tại output để bỏ qua âm thầm.

### Ghi kết quả an toàn

Convert vào vùng tạm cùng filesystem với output. Chỉ khi thành công và nội dung đã kiểm tra mới dùng `os.replace` công bố Markdown; không xóa bản cũ trước conversion. Nếu lỗi hoặc partial, giữ nguyên bản cũ, ghi trạng thái và lỗi vào history. Kết quả partial lưu riêng trong `history/partial/<ma_luot>/<duong_dan_tuong_doi>.md` để kiểm tra, không công bố dưới tên output chính.

Ảnh và fixlog phải theo thư mục của Markdown mới. Mỗi lượt dùng thư mục assets riêng, ví dụ `output/quy-chuan/assets/a/<ma_luot>/`; link trong `a.md` trỏ tương đối tới assets đó. Chỉ công bố Markdown sau khi assets sẵn sàng; lỗi thì dọn riêng tài nguyên của lượt đó, không đụng assets của bản cũ. Partial có assets riêng bên cạnh bản partial. Chưa tự dọn assets cũ không còn dùng trong MVP. Fixlog kỹ thuật lưu theo mã lượt trong history để không nhầm với Markdown kết quả.

`os.replace` bảo vệ một file, không phải transaction nhiều file. Dùng thứ tự assets trước, Markdown sau để bản cũ vẫn đọc được nếu quá trình dừng giữa chừng. Dùng khóa ứng dụng một phiên cho pipeline, kiểm tra lại đích và thử tình huống lỗi ghi/đầy ổ đĩa. Không hứa bảo vệ hoàn toàn khỏi phần mềm ngoài cùng ghi đích đúng thời điểm công bố.

### PPTX sang Markdown

Ba lựa chọn có cùng mapping `<thư mục con>/<tên gốc>.md` và cùng dialog Replace/Bỏ qua. Không upload trực tiếp PPTX rồi giả định API đọc được toàn bộ slide. “Agent API” trong phạm vi này là backend Gemini hiện có, không thêm vòng lặp nhiều agent hoặc tự đổi nhà cung cấp.

| Chế độ | Luồng xử lý dự kiến | Điều kiện và giới hạn |
|---|---|---|
| Native Local | Đọc Open XML bằng `zipfile` và `xml.etree.ElementTree`; trích text, bullet, bảng, ảnh theo slide | Không cần Office hoặc API; không OCR ảnh; không cam kết tái dựng animation, SmartArt hay bố cục đồ họa phức tạp |
| Scan | PowerPoint xuất PDF tạm bằng COM, sau đó dùng pipeline PDF Scan/Gemini | Cần PowerPoint desktop khả dụng và cấu hình API; giữ thứ tự slide qua trang PDF |
| Refine | PowerPoint xuất PDF tạm, gửi pipeline Refine với yêu cầu giữ số slide, text và bảng | Cần PowerPoint và API; không phải tự động sửa Markdown đã có; không chạy sau Native nếu người dùng chưa chọn |

Native đọc thứ tự từ `ppt/presentation.xml` và relationships, không sort tên `slide1.xml`, `slide10.xml`. Duyệt text trong shape/group, bảng và ảnh nhúng theo relationship; tạo `## Slide N` và tiêu đề nếu có. Ảnh đưa vào assets theo quy tắc mục 4. Không tải external relationship. Thứ tự đọc trong slide phức tạp chỉ là gần đúng; nếu slide chỉ có ảnh, ghi thiếu text và gợi ý chọn Scan, không tự gọi API.

MVP trích các slide theo thứ tự gốc, kể cả slide ẩn và đánh dấu ẩn; PDF export cũng cấu hình cùng phạm vi. Chưa đưa speaker notes, audio/video và animation vào Markdown. Phải có mẫu kiểm thử slide có group, bảng, ảnh và slide ẩn. Native không tự diễn giải biểu đồ không có text trích được.

PDF tạm có mã lượt, output cuối vẫn tính từ path PPTX gốc, không từ tên PDF tạm. Chia chunk và report theo slide/trang; giữ nguồn `.pptx` trong history. Bỏ qua output phải được quyết định trước khi mở PowerPoint hoặc render. Thiếu PowerPoint chỉ khóa PPTX Scan/Refine, Native vẫn hoạt động. Không tự cài Office hoặc đổi sang dịch vụ khác.

### Chuyển file Office

Mục này chỉ chuyển định dạng Office cũ sang Open XML, không gọi Gemini và không xuất Markdown.

```text
[Xuất Markdown] [Chuyển file Office]
Kiểu chuyển: [Word: .doc sang .docx]
Nguồn: [đường dẫn] [Duyệt (Browse)] [Về input] [Quét lại]
Office: [kết quả kiểm tra ứng dụng tương ứng]
Đích xuất: Cùng thư mục với từng file nguồn
[ ] Đổi tên file xuất ra
[ ] Xóa file gốc sau khi chuyển xong
[cây thư mục và danh sách file]
[Chọn tất cả] [Bỏ chọn] [Chuyển] [Dừng sau lượt hiện tại]
```

Combo có `Word: .doc sang .docx`, `PowerPoint: .ppt sang .pptx`, `Excel: .xls sang .xlsx`. Chọn một file, nhiều file hoặc cả nhánh giống mục Markdown; quét đệ quy theo extension nguồn. Output mới `.docx/.pptx/.xlsx` không nằm trong bộ lọc nguồn nên không bị chuyển lại trong cùng lượt. Chưa có chế độ trộn ba loại trong một lượt.

#### Phát hiện Office và trạng thái nút

Ưu tiên Microsoft 365 desktop. Nếu không có, chấp nhận Office 2021/LTSC 2021 hoặc Office 2024/LTSC 2024. Microsoft không có sản phẩm thương mại tên Office 2020; đây là cách áp dụng yêu cầu “2020 trở lên” vào các phiên bản có thật. Không coi `Application.Version = 16.0` là bằng chứng phiên bản đủ mới vì nhiều đời Office dùng chung major version. [Các bản Office](https://learn.microsoft.com/en-us/officeupdates/)

Khảo sát read-only trên máy: ClickToRun ghi `O365HomePremRetail`, `VersionToReport=16.0.20326.20112`, thư mục `C:/Program Files/Microsoft Office`. Đây là dấu hiệu cài Microsoft 365; chưa mở ứng dụng COM, chưa xác minh license hoặc chuyển file. Lần đọc ProgID qua PowerShell chưa thu được CLSID, không suy ra cả ba ứng dụng đều có hoặc đều thiếu.

Kiểm tra bằng `winreg` cả registry view 32/64-bit: thông tin sản phẩm, đường cài đặt và ProgID của từng ứng dụng. Tiếp theo probe COM trong worker riêng có timeout, tạo/mở đối tượng ứng dụng cần dùng, kiểm tra khả năng automation và đóng đối tượng do mình sở hữu. Không sửa registry để ép đăng ký Office khác. Nếu nhiều bản cài nhưng ProgID đang trỏ một bản khác, chỉ dùng bản thực sự kích hoạt được và báo đúng tên, không hứa chọn được mọi bản song song.

Nút `Chuyển` chỉ bật khi có file hợp lệ, ứng dụng tương ứng đạt kiểm tra, nguồn có quyền đọc, đích/history có quyền ghi và không có job đang chạy. Thiếu Word chỉ khóa DOC; thiếu Excel chỉ khóa XLS; thiếu PowerPoint khóa PPT và PPTX Scan/Refine. Có nút `Kiểm tra lại Office`; trạng thái `Chưa kiểm tra`, `Khả dụng`, `Không khả dụng` kèm nguyên nhân tiếng Việt. Office web không đáp ứng COM. Bản không xác định được hoặc Office 2019 trở xuống không tự coi là đạt yêu cầu.

#### Python và COM

Để giữ yêu cầu chỉ thêm Python chuẩn, phương án trong plan dùng `ctypes` gọi COM Windows qua `IDispatch`, `winreg` để phát hiện. Office vẫn là engine thực sự chuyển định dạng nhị phân; đây không phải converter tự viết chỉ bằng Python. Không dùng PowerShell, VBScript hoặc điều khiển click chuột để Save As. [IDispatch](https://learn.microsoft.com/en-us/windows/win32/api/oaidl/nn-oaidl-idispatch)

Adapter chỉ hỗ trợ các lời gọi cần thiết: khởi tạo COM STA, tạo application, property get/put, Open, SaveAs/SaveAs2, ExportAsFixedFormat, Close và Quit. Phải xử lý `VARIANT`, `BSTR`, đối số tùy chọn/named arguments, HRESULT/EXCEPINFO và giải phóng reference, thử cả kiến trúc Python/Office được triển khai. Đây là phần có chi phí và rủi ro cao hơn các tác vụ Python thông thường, không mô tả là vài dòng code.

Thực hiện spike nhỏ cho Open/SaveAs/Close của ba ứng dụng trước khi làm GUI. Nếu adapter ctypes không đạt kiểm thử, dừng phần Office ở trạng thái chưa khả dụng và báo kết quả; phương án giảm code là dependency `pywin32`, nhưng không tự thêm vì không còn đúng giới hạn thư viện chuẩn đã thống nhất. Không viết một thư viện COM tổng quát trong MVP.

| Chuyển | Ứng dụng và định dạng lưu |
|---|---|
| DOC sang DOCX | Word `SaveAs2`, `wdFormatXMLDocument` (12) |
| PPT sang PPTX | PowerPoint `SaveAs`, `ppSaveAsOpenXMLPresentation` (24) |
| XLS sang XLSX | Excel `SaveAs`, `xlOpenXMLWorkbook` (51) |

Nguồn định dạng: [Word](https://learn.microsoft.com/en-us/office/vba/api/word.wdsaveformat), [PowerPoint SaveAs](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.presentation.saveas), [Excel](https://learn.microsoft.com/en-us/office/vba/api/excel.xlfileformat). Kiểm tra lại các hằng số trong spike, không dùng định dạng mặc định theo phiên Office.

Một worker process chạy tuần tự các file, COM cùng một STA thread, tái sử dụng instance do worker tạo nếu an toàn. Không lấy tài liệu người dùng đang mở để SaveAs, không đóng phiên Office người dùng và không `taskkill` theo tên ứng dụng. PowerPoint có thể có hành vi chia sẻ instance; nếu không chứng minh được quyền sở hữu thì không gọi Quit hoặc cưỡng bức kill instance đó. Timeout báo file lỗi và ngừng lượt Office nếu không cleanup được an toàn.

Mở read-only khi API cho phép, tắt cập nhật external link và macro qua thiết lập của từng ứng dụng, không bấm chấp nhận hộp thoại tự động. File có password, Protected View, hỏng hoặc yêu cầu tương tác báo lỗi rõ ràng, không tự vượt bảo vệ. [AutomationSecurity](https://learn.microsoft.com/en-us/office/vba/api/office.msoautomationsecurity)

#### Tên file và đích xuất

Mặc định `D:/Tai-lieu/du-an/a.doc` thành `D:/Tai-lieu/du-an/a.docx`; tương tự PPT/XLS, kể cả thư mục con. Quy tắc `data/output` chỉ áp dụng mục Markdown.

Checkbox `Đổi tên file xuất ra` mặc định bỏ tích. Khi tích, trước conversion hỏi tên mới cho từng file trong snapshot, chỉ nhập basename không extension; GUI hiển thị extension cố định. Enter với tên hợp lệ để tiếp tục; hủy dialog cho chọn Bỏ qua file hoặc Hủy lượt chạy. Không chấp nhận tên rỗng, tên thiết bị Windows, ký tự cấm, dấu chấm/khoảng trắng cuối, path separator hoặc `..` để đổi thư mục. Thu xong tên và lựa chọn xung đột mới bắt đầu chuyển.

Output tồn tại dùng dialog Replace/Bỏ qua hiện có. Bỏ qua không mở Office và không xóa file nguồn. Hai input đổi tên tới cùng output bị chặn trước worker. Khi đổi tên không tích, tuyệt đối không sửa basename. Không tự đổi `.doc` thành `.docx` bằng rename extension mà không SaveAs.

SaveAs vào file tạm đúng extension cạnh output, đóng tài liệu, kiểm tra Open XML ZIP/CRC và các part bắt buộc, rồi mở lại bằng ứng dụng tương ứng ở chế độ không sửa. So số slide hoặc sheet với nguồn; với Word kiểm tra mở được và nội dung chính, không dùng số trang như phép so tuyệt đối. Các kiểm tra này không bảo đảm mọi chi tiết bố cục tương đương; cần smoke test mẫu thực tế. Công bố bằng `os.replace` sau khi kiểm tra và đóng mọi handle.

#### Xóa file gốc sau khi chuyển xong

Checkbox mặc định bỏ tích, áp dụng riêng mục Office; chuyển sang Markdown phải ẩn và đặt lại, không mang trạng thái xóa sang tác vụ khác. Nhãn ghi rõ `Xóa file gốc sau khi chuyển xong`; phần mô tả nói file nguồn sẽ được xóa khỏi ổ đĩa, không vào Recycle Bin. Tích checkbox và bấm Chuyển là lựa chọn cho snapshot hiện tại, không phải quyền xóa cả thư mục.

Chỉ xóa từng nguồn bằng `Path.unlink()` khi: conversion thành công, file mới đã kiểm tra và công bố, Office đã đóng nguồn, log thành công đã ghi bền vững, nguồn vẫn đúng file ban đầu. Khi tùy chọn xóa bật, lưu fingerprint SHA-256 và stat lúc bắt đầu, kiểm tra lại trước xóa; nguồn thay đổi thì giữ lại và báo. Không xóa thư mục, không xóa nguồn của job skipped/failed/partial, không xóa file sau timeout hoặc kiểm tra thất bại.

DOC/PPT/XLS có thể chứa macro trong khi DOCX/PPTX/XLSX không giữ VBA. Nếu phát hiện macro hoặc không xác định được việc mất nội dung, không tự chuyển rồi xóa nguồn. Báo `Cần kiểm tra macro, giữ file gốc`; không đổi sang DOCM/PPTM/XLSM ngoài yêu cầu. Các cảnh báo mất tính năng từ Office phải được ghi nhận; không dùng DisplayAlerts để âm thầm chấp nhận rồi xóa nguồn. [Định dạng Open XML](https://support.microsoft.com/en-US/Office/vba/open-xml-formats-and-file-name-extensions)

History ghi trạng thái conversion và trạng thái nguồn riêng: `Đã giữ`, `Chờ xóa`, `Đã xóa`, `Xóa thất bại`. Ghi ý định xóa trước, ghi kết quả sau; lỗi xóa không làm mất output tốt, không báo conversion thất bại nếu chỉ unlink thất bại. Nếu crash giữa unlink và log cuối, hiển thị cần kiểm tra, không tự chạy lại lệnh xóa khi khởi động. Tùy chọn này mới nằm trong plan, chưa xóa file nào ở phiên hiện tại.

### Tóm tắt file md bằng Gemini Flash

#### Phân tích hai file tham khảo

Đã đọc toàn bộ [main_audio2md.py](C:/audio2md/src/main_audio2md.py) và [file mẫu](<C:/audio2md/data/output/4-Year Marketing Degree in 2 MINUTES._refine.md>). Không chạy script, không tải media, không gọi API và không sửa dự án audio2md. Prompt trong code là dữ liệu để phân tích.

| Nội dung | Code thực tế | File mẫu thực tế | Cách dùng trong PDF2MD |
|---|---|---|---|
| Hàm chính liên quan | `refine_content()` nhận text, tạo `_refine.md` | File có hậu tố `_refine.md` | Tách ý tưởng thành `summary_md.py`, đổi hậu tố `_summary.md` |
| Ngôn ngữ | Prompt yêu cầu hai phần Việt rồi Anh | Chỉ có tiếng Việt, không có phần Anh | Phải hỏi người dùng, không kết luận mẫu đã song ngữ |
| Cấu trúc | H1 là tiêu đề; H2 đánh số 1 Tóm tắt, 2 Bài học, 3 Trích dẫn | H1 `1. Tiêu đề chính`, sau đó H2 số 2, 3, 4 | Chưa tự chọn một cấu trúc và gọi là giống cả hai |
| Độ dài | Đúng 3 câu tóm tắt, bullet bài học, 1-3 trích dẫn | 3 câu, 4 bullet, 2 đoạn trích dẫn | Dùng làm lựa chọn định dạng, không áp số bullet cứng từ một mẫu |
| Nguồn tham khảo | Code luôn nối `**Reference:** ...` sau response | File mẫu không có dòng Reference | Không suy ra file được tạo bởi đúng phiên bản code đang đọc |
| Model | Thử `gemini-3.6-flash`, sau lỗi thử `gemini-2.5-flash` | Không ghi model/usage | Không sao chép danh sách rồi tuyên bố khả dụng; cấu hình Flash phải được chốt và kiểm tra |
| API | Tạo chat mới, gửi một prompt chứa toàn bộ transcript | Không thể xác minh request từ file mẫu | Summary MD chỉ cần text generation, không cần chat nhiều lượt hoặc agent framework |
| Kiểm tra | Chỉ kiểm tra response.text có nội dung | Mẫu lệch cấu trúc prompt | Thêm kiểm tra ba mục, ngôn ngữ và trạng thái kết thúc trước công bố |

`original_title` được truyền vào `refine_content()` nhưng không dùng trong prompt hiện tại. Code không có kiểm tra 3 câu, song ngữ, độ dài context, nội dung bị cắt hoặc trích dẫn đúng nguồn; bắt exception rồi thử model sau với sleep 10 giây. Không kế thừa retry cho mọi lỗi. Đường lỗi không có report thành công/thất bại thống nhất. Các phần yt-dlp, FFmpeg, audio upload, bóc băng và sửa bảng `build-audio2md.md` không cần cho Summary MD.

File mẫu chứa gạch ngang dài và tiêu đề mang tính biên tập; đầu ra mới phải tuân thủ quy tắc chữ hiện tại của dự án. Chưa có transcript gốc tương ứng nên chưa xác minh được các trích dẫn trong mẫu là nguyên văn hay bản dịch. Không dùng mẫu để xác nhận tính đúng của các phát biểu về Marketing.

#### Các lựa chọn đã chốt

| Quyết định | Cấu hình |
|---|---|
| Ngôn ngữ | Combo Tiếng Việt / Tiếng Anh / Song ngữ Việt-Anh; mặc định song ngữ |
| Nội dung | Ba mục: Tóm tắt nội dung chính; Các mấu chốt cần lưu ý; Các hạn chế và giải pháp. Bỏ hoàn toàn Trích dẫn |
| Nguồn/đích | Mặc định `data/output`, lưu `data/summary`, giữ cây thư mục con; Browse được nơi khác |
| Độ chi tiết | Theo độ phức tạp và loại tài liệu, không giới hạn đúng 3 câu; file dài chia mục rồi tổng hợp |
| Model | Dùng chung `GEMINI_MODEL` hiện có; backend Summary yêu cầu model thuộc dòng Gemini Flash |
| Link nguồn | Chỉ link về file Markdown nguồn ở cuối Summary; không sao chép URL Reference |

Đã nhận đủ câu trả lời và chốt các lựa chọn. Các chi tiết triển khai MVP bên dưới không thay đổi ba mục nội dung hoặc tự bổ sung Trích dẫn.

#### Cấu trúc Summary đã chốt

Song ngữ trình bày toàn bộ phần Việt trước, rồi phần Anh tương ứng; hai phần giữ cùng ý, không tự thêm thông tin khi dịch. Một ngôn ngữ chỉ render phần tương ứng.

```markdown
# <Tiêu đề tài liệu>

## Tiếng Việt
### 1. Tóm tắt nội dung chính
### 2. Các mấu chốt cần lưu ý
### 3. Các hạn chế và giải pháp

## English
### 1. Main Summary
### 2. Key Points
### 3. Limitations and Solutions
```

Không có mục Trích dẫn, trường quote trong schema hoặc bước kiểm tra nguyên văn. Không áp yêu cầu đúng 3 câu hoặc mục Bài học của template cũ. Giữ heading con theo cấu trúc nguồn trong từng mục khi cần cho tài liệu dài, không tăng số mục chính.

Mục hạn chế/giải pháp chỉ nêu nội dung nguồn hỗ trợ. Nếu nguồn nêu hạn chế nhưng không có giải pháp, ghi `Nguồn chưa nêu giải pháp`; không có cả hai thì ghi `Nguồn không nêu hạn chế và giải pháp`. Không sáng tạo giải pháp để lấp đủ mục, không biến phần này thành tư vấn bên ngoài tài liệu.

GUI bổ sung combo `Loại văn bản`: `Báo cáo / thông thường` (mặc định MVP), `Kỹ thuật`. Người dùng chọn một loại cho lượt hiện tại; không thêm request phân loại tự động. Với thư mục trộn nhiều loại, chọn các file cùng loại và chạy từng lượt. Đây là cách triển khai đề xuất theo yêu cầu phân biệt loại văn bản, không phải tính năng đã chạy.

- Kỹ thuật: giữ số liệu, đơn vị, ký hiệu, điều kiện áp dụng, giả thiết, quy trình và giới hạn. Bảng/công thức quan trọng được giữ hoặc diễn giải đủ điều kiện; không rút gọn làm đổi nghĩa. Ưu tiên cấu trúc theo phần kỹ thuật của nguồn.
- Báo cáo / thông thường: làm rõ mục tiêu, kết quả, quyết định, vấn đề còn tồn tại và hành động được nguồn nêu. Không tự thêm người phụ trách, hạn chót hoặc chỉ tiêu.
- Cả hai: độ dài theo nội dung, tránh lặp ý, không đặt trần số câu/bullet cứng. Có giới hạn token vận hành theo model; vượt giới hạn thì chia và tổng hợp, không bỏ nội dung âm thầm.

#### Phần thiết kế đã xác định

- Mục `Tóm tắt file md`, bộ lọc `.md`, dùng Browse/cây đệ quy, chọn file hoặc cả thư mục như hiện có. Nút `Tóm tắt` chỉ bật khi có file hợp lệ và cấu hình API/model cần thiết; không yêu cầu Office.
- Nguồn mặc định `ROOT/data/output`; đích cố định `ROOT/data/summary`. Ví dụ `data/output/du-an/a.md` thành `data/summary/du-an/a_summary.md`. Browse thư mục ngoài giữ cây tương đối với gốc được chọn; Browse file dùng thư mục cha như quy tắc chung. Không thêm gốc ngoài vào tên thư mục đích. Nút quay nguồn của mục này ghi `Về output`, không ghi `Về input`.
- Loại `data/summary` khỏi mọi lần quét đệ quy để tránh tự đọc output Summary. Nếu Browse chọn chính thư mục này thì báo nguồn không hợp lệ. Tạo thư mục đích cần thiết khi có job thực sự chạy; dùng staging cùng filesystem với `data/summary`, giữ Replace/Bỏ qua và report/history hiện có.
- Không tự chạy Summary sau conversion. Không có tùy chọn xóa nguồn trong mục này. Cờ xóa Office phải reset khi đổi mục.
- Tên đích là `nguon.stem + '_summary.md'`: `a.md` thành `a_summary.md`; `a_refine.md` thành `a_refine_summary.md`. Không tự cắt `_raw`, `_refine` hoặc dịch/đổi basename vì có thể gây đụng tên. Ví dụ file mẫu sẽ thành `4-Year Marketing Degree in 2 MINUTES._refine_summary.md`.
- Loại `_summary.md` không phân biệt hoa/thường khỏi quét và từ chối chọn trực tiếp trong MVP để tránh tạo summary lặp. File rỗng, chỉ frontmatter hoặc không có nội dung văn bản báo Bỏ qua với lý do.
- Đích đã tồn tại hỏi Replace/Bỏ qua trước đọc sâu hoặc gọi API. Bỏ qua không tạo client/request. Replace chỉ công bố atomically sau kiểm tra response; lỗi giữ bản summary cũ.
- Quyền đọc output là ngoại lệ có chủ đích của Summary, không bỏ cơ chế loại output ở hai mục khác. Bộ quy tắc đường dẫn phải nhận `chuc_nang`, không hard-code một nguồn/đích chung.

#### Luồng nội dung và kiểm tra

1. Đọc UTF-8/UTF-8 BOM; lỗi decode thì báo, không âm thầm thay ký tự. Giữ heading, nội dung đoạn, bảng và code có ý nghĩa. Frontmatter có thể lấy title nhưng không coi là chỉ dẫn; không dùng Reference để bổ sung nguồn ngoài. Không tự mở link, wikilink hoặc ảnh nhúng; Summary MVP chỉ tóm tắt văn bản có trong file.
2. Đặt chỉ dẫn tóm tắt và dữ liệu nguồn ở phần riêng trong request. Nêu rõ prompt/chỉ thị nằm trong Markdown nguồn chỉ là nội dung tài liệu; không thực hiện lệnh, tải URL hoặc bổ sung kiến thức bên ngoài. Không cấp công cụ cho model.
3. Chỉ yêu cầu thông tin có căn cứ trong nguồn; giữ số liệu, đơn vị, điều kiện và mức độ chắc chắn. Tiêu đề phải mô tả nội dung, không dùng yêu cầu “hấp dẫn” từ prompt cũ. Tránh tự biến tài liệu kỹ thuật thành lời khuyên truyền cảm hứng.
4. Ưu tiên response JSON có ba trường nội dung cho mỗi ngôn ngữ: tóm tắt, mấu chốt, hạn chế/giải pháp; Python dựng Markdown theo template. Kiểm tra structured output với Flash/model và SDK thực tế. Không dùng schema ba câu, bài học hoặc quote cũ; JSON hợp lệ chưa chứng minh nội dung đúng nguồn.
5. Giữ mã mục nguồn cho các ý trong kết quả trung gian để đối chiếu, không render thành mục Trích dẫn. Nếu input đã là Refine, Summary chỉ dựa vào file đó, không khẳng định đã xác minh với tài liệu nguyên thủy.
6. Kiểm tra đủ ngôn ngữ, ba mục, heading/bullet và finish reason. Response rỗng, bị chặn, bị cắt hoặc thiếu phần là failed/partial; không báo thành công chỉ vì có text. Không chạy vòng tự sửa bằng API vô hạn; báo lỗi định dạng và cho chạy lại có chủ đích.
7. Python render Markdown rồi thêm duy nhất dòng `Nguồn: [<tên file>](<đường dẫn file MD>)` cuối file; bản chỉ Anh dùng nhãn `Source`. Tính link tương đối từ thư mục summary tới nguồn nếu cùng ổ đĩa, percent-encode ký tự path cần thiết; nguồn khác ổ dùng URI file hợp lệ cho Obsidian. Không dùng basename wikilink có thể trùng, không nhờ model tạo link và không sao chép URL Reference. Kiểm tra mở đúng nguồn với tên Unicode/khoảng trắng. UI/plan/log vẫn tiếng Việt; phần Anh của summary là ngoại lệ được yêu cầu. Không emoji, icon hoặc gạch ngang dài.

#### Giới hạn context và chi phí

Summary đọc `GEMINI_MODEL` chung và `GEMINI_API_KEY`; không tạo biến model riêng, không copy danh sách fallback từ audio2md. Chụp model vào snapshot lượt chạy, hiển thị GUI/history. Nếu cấu hình không thuộc dòng Gemini Flash hoặc bị thiếu, báo cần cấu hình Flash; không tự sửa .env hoặc chọn model khác. Không dò model khi mở GUI. Dùng SDK Google GenAI hiện có và adapter tương thích phiên bản cài đặt. [Text generation](https://ai.google.dev/gemini-api/docs/text-generation), [Models](https://ai.google.dev/gemini-api/docs/models).

File dài xử lý bằng chia mục rồi tổng hợp: kiểm tra token input gồm cả prompt, dành chỗ output theo model; chia theo heading/đoạn, không cắt bảng hoặc code fence giữa chừng khi có thể. Tóm tắt từng phần rồi tổng hợp; lưu mã mục nguồn để truy vết ý từ bản trung gian. Nếu tổng hợp trung gian vẫn vượt context, tiếp tục gom theo tầng có giới hạn hoặc báo quá giới hạn; không lặng lẽ bỏ đuôi file. Một chunk lỗi không tạo summary cuối trông như đầy đủ. File vừa context dùng một request; không lặng lẽ cắt input. [Token counting](https://ai.google.dev/gemini-api/docs/tokens).

Concurrency API = 1, retry giới hạn cho lỗi tạm thời; thiếu key, 401/403 hoặc model 404 phải dừng đúng lỗi cấu hình, không thử liên tục. History thêm model thực dùng, số request và usage token nếu API trả về; không bịa chi phí/token. Không lưu toàn bộ prompt hoặc nội dung tài liệu vào log. Giữ mã nguồn và template ngắn, không mang pipeline audio sang dự án này.

### Xem Markdown bằng Tkinter cơ bản

#### Quyết định MVP

Tính năng khả thi bằng Python chuẩn và Tkinter đã có trong venv. Không thêm `pywebview`, WebView2, Qt, trình duyệt nhúng, Mermaid, MathJax, LaTeX hoặc thư viện Markdown ngoài. Phần mã mới dự kiến dưới 1 MiB; đây là ước lượng cho mã và test của tính năng, không phải số đo sau khi triển khai. `.venv` hiện khoảng 340,9 MiB, không thay đổi do tính năng này.

`src/markdown_viewer.py` mới quản lý các cửa sổ `tk.Toplevel`. Nút `Xem Markdown` trên menu chỉ bật khi Treeview chọn đúng một file `.md`; nhấp mở một cửa sổ mới cho chính file đó, kể cả khi file này đã được mở ở một cửa sổ khác. Mỗi cửa sổ có tiêu đề path file và các nút `Mới`, `Mở`, `Lưu`, `Lưu thành`. Không có danh sách tab, cửa sổ con MDI, browser hay dependency mới trong MVP.

```text
Tệp: C:\...\tai-lieu.md                 [Mới] [Mở] [Lưu] [Lưu thành]
[Nguồn] [Xem trước]

Nội dung Source hoặc Preview có scrollbar
Trạng thái: Đã lưu | Đã thay đổi | Không thể đọc | Đã thay đổi ngoài ứng dụng
```

`Nguồn` dùng `ScrolledText` để chỉnh sửa. `Xem trước` chỉ đọc, render lại khi người dùng chuyển sang chế độ này hoặc nhấn `F5`; không có chỉnh sửa rich text trực tiếp. Cách này tránh phải chuyển ngược rich text thành Markdown và giữ file nguồn là dữ liệu duy nhất được ghi.

#### Cú pháp hiển thị

Preview hỗ trợ Markdown phổ biến và một phần Obsidian đơn giản: heading, đoạn, bold, italic, strike, highlight, link Markdown, wikilink `[[...]]` ở dạng link/nội dung, danh sách lồng, task list, quote, callout `> [!note]`, code inline, fenced code, bảng pipe, đường kẻ, ảnh cục bộ có sẵn và footnote cơ bản. Giao diện dùng `Text` tags, `PhotoImage` cho ảnh Tk đọc được và hyperlink bằng binding nội bộ.

Các phần sau hiển thị dạng code hoặc ghi chú `Chưa hỗ trợ trong Xem trước`: Mermaid, công thức LaTeX, HTML nhúng, Canvas, Dataview, plugin Obsidian, truy vấn, audio/video nhúng, embed ghi chú đệ quy, JavaScript và macro. Preview không tải URL, không chạy JavaScript, không gọi API, không mở nội dung nhúng tự động. Link ngoài chỉ mở trình duyệt khi người dùng nhấp và xác nhận trong lần triển khai sau; MVP hiển thị link nhưng không mở.

Renderer là parser tuyến tính giới hạn, tách block trước rồi áp style inline; không nhằm tái tạo chính xác giao diện Obsidian. Bảng lớn dùng font monospace và scrollbar ngang nếu cần. Ảnh quá lớn được hiện bằng đường dẫn và kích thước thay vì tự nạp toàn bộ; GIF/SVG/định dạng không được Tk đọc hiển thị link. Không thêm Pillow chỉ để preview ảnh.

#### File và thao tác lưu

- `Mới` yêu cầu xử lý thay đổi chưa lưu, sau đó mở cửa sổ trống chưa có path. `Mở` chọn một `.md` khác trong chính cửa sổ đó. `Lưu` chỉ bật khi có path; `Lưu thành` luôn cho chọn path `.md`.
- `Lưu` và `Lưu thành` ghi UTF-8, dùng file tạm cùng thư mục rồi `os.replace`. Tên chưa có `.md` được bổ sung một lần. Không tự tạo path ngoài thư mục người dùng đã chọn.
- Mở file bằng UTF-8 hoặc UTF-8 BOM. Lỗi decode hiển thị, không thay ký tự và không cho ghi đè lên file chưa đọc được.
- Lưu snapshot `mtime_ns`, size và SHA-256 khi mở/lưu. Nếu file nguồn đổi ngoài ứng dụng trước Lưu, hiện `Nạp lại`, `Lưu thành`, `Ghi đè`, `Hủy`; focus mặc định `Hủy`. Không tự ghi đè file bị thay đổi ngoài cửa sổ.
- Khi đóng cửa sổ có thay đổi, hỏi `Lưu`, `Không lưu`, `Hủy`. `Không lưu` chỉ bỏ buffer trong cửa sổ, không xóa file. Menu chính vẫn chạy các conversion độc lập; để tránh ghi cạnh tranh, conversion/Replace không sửa file đang có buffer chưa lưu mà báo đường dẫn đang mở.
- Nếu New/Lưu thành trùng file có sẵn, dùng dialog Replace/Bỏ qua của ứng dụng, với `Hủy` mặc định. Bỏ qua giữ buffer chưa lưu và không ghi file.

Không ghi history cho thao tác chỉ xem. Lưu hoặc Lưu thành thành công ghi record `chuc_nang: Xem Markdown`, `trang_thai: Đã lưu`, path nguồn/đích và thời điểm vào `ROOT/history/yyyy-mm.log`; nội dung file không vào log. Nếu history không ghi được sau Save, file đã được lưu vẫn giữ, GUI báo rõ trạng thái tách biệt và cho ghi lại history.

#### Kiểm thử

| Ca kiểm thử | Kết quả cần đạt |
|---|---|
| Mở hai file và mở cùng một file hai lần | Mỗi lần có Toplevel riêng, resize/đóng không làm đóng menu hoặc cửa sổ khác |
| New/Open/Save/Save As | Đúng path, UTF-8, extension `.md`, không tự mất buffer |
| Source sang Preview | Preview chỉ đọc, cập nhật khi đổi chế độ hoặc F5 |
| Markdown cơ bản, callout, bảng, task list, wikilink, ảnh | Hiển thị đúng phạm vi đã nêu, không chạy nội dung nhúng |
| Mermaid, LaTeX, HTML, plugin Obsidian | Không render/chạy, hiện rõ chưa hỗ trợ |
| File lớn, bảng rộng, ảnh lớn/không hỗ trợ | GUI còn phản hồi, không tự nạp ảnh quá lớn |
| File đổi ngoài ứng dụng, Save As trùng tên, đóng khi chưa lưu | Không ghi đè âm thầm, dialog có Hủy mặc định |
| Link ngoài và Markdown chứa prompt/script | Không tự mở/tải/chạy bất cứ nội dung nào |
| Lưu thành công nhưng history lỗi | File vẫn có trên đĩa, trạng thái history báo đúng |

## 5. Lịch sử theo tháng

### Định dạng

`ROOT/history/2026-09.log` là lịch sử tháng 09/2026, `2026-10.log` cho tháng 10/2026. Dùng thời gian local có timezone của máy và `strftime('%Y-%m')`. Mỗi file có một record lúc kết thúc trạng thái; tên tháng lấy từ thời điểm record, không lấy tháng bắt đầu batch. Lượt chạy qua nửa đêm cuối tháng có record trong hai file tương ứng.

Log UTF-8, mỗi record là một dòng JSON để đường dẫn/lỗi chứa xuống dòng được escape; vẫn đọc được tiếng Việt với `ensure_ascii=False`. Khóa dùng tiếng Việt không dấu:

Áp dụng cho Xuất Markdown, Chuyển file Office và Tóm tắt file md. Thêm các trường `chuc_nang`, `dinh_dang_nguon`, `dinh_dang_dich`, `doi_ten`, `xoa_nguon`, `trang_thai_nguon` cho job Office; đường `dich` có thể nằm cạnh nguồn ngoài dự án. Job Summary thêm model/ngôn ngữ/số request/usage nếu có. Ghi riêng kết quả xóa sau conversion, vẫn theo quy tắc mới nhất ở trên và tháng tại thời điểm ghi.

```json
{"thoi_gian":"2026-09-05T15:10:30+07:00","ma_luot":"...","tac_vu":"PDF gốc (Native PDF), Local","nguon":"C:/pdf2md/data/input/quy-chuan/a.pdf","dich":"C:/pdf2md/data/output/quy-chuan/a.md","lua_chon":"Thay thế","trang_thai":"Thành công","thoi_gian_giay":2.3,"loi":null}
```

Đây là ví dụ định dạng, không phải lịch sử chạy thật. Ghi cả Thành công, Bỏ qua, Lỗi, Thiếu nội dung và Chưa chạy do hủy. Ghi thêm record cấp lượt cho mở lượt/kết thúc/hủy để phát hiện lượt dở dang. Không ghi API key, prompt đầy đủ hoặc nội dung tài liệu.

### Cách ghi bằng Python chuẩn

Một thành phần duy nhất trong runner ghi history, worker con không tự ghi cùng file. Khi có record mới:

1. Tạo file tạm cạnh file tháng trong history.
2. Ghi record mới và newline lên đầu, rồi dùng `shutil.copyfileobj` chép nội dung file tháng cũ theo khối xuống dưới.
3. Flush, `os.fsync`, đóng file rồi `os.replace` file tháng. Nếu chưa có file tháng, chỉ ghi record mới.
4. Chỉ xóa file tạm do thao tác này tạo khi có lỗi; giữ log tháng cũ.

Mới nhất nằm trên theo thứ tự ghi. Quét/convert song song có một bộ ghi tuần tự; không dùng nhiều process prepend. Khóa một phiên ứng dụng bằng thư viện chuẩn trên Windows (`msvcrt.locking`, giữ handle suốt lượt/phiên) để tránh hai ứng dụng cùng thay log/output; khóa được OS giải phóng khi process chết. GUI và đường CLI mới đều dùng cùng runner/khóa. Nếu đang khóa, thông báo tiếng Việt và không mở lượt ghi thứ hai.

Prepend phải chép lại file tháng, chi phí O(kích thước log) mỗi record. Đó là đánh đổi để giữ đúng yêu cầu mới ở trên; dùng copy theo khối để không nạp cả log vào RAM. Chưa thêm database, dịch vụ log hoặc chia file ngoài quy tắc yyyy-mm. Đo với log lớn trước khi điều chỉnh; không khẳng định ghi prepend có chi phí hằng số.

Kiểm tra quyền ghi history trước khi bắt đầu. Nếu ghi log thất bại giữa lượt, báo rõ và dừng lên lịch file tiếp theo, không báo lịch sử đã lưu. Output đã công bố vẫn giữ; kết quả chưa ghi log giữ trong bộ nhớ và cho thử ghi lại. Crash/mất điện không bảo đảm ghi được record kết thúc; record mở lượt giúp nhận biết, không tự dựng trạng thái thành công.

## 6. Ảnh giao diện cập nhật

Ba ảnh là mockup tạo bằng ImageGen, không phải ảnh ứng dụng đã chạy. Bố cục này thay các ảnh cũ có tab File/Thư mục và bảng phẳng.

Các ảnh bên dưới minh họa phiên bản trước khi thêm PPTX và Chuyển file Office. Chúng chưa thể hiện thanh chọn hai chức năng, combo PPTX, checkbox đổi tên/xóa nguồn hoặc trạng thái Office. Đặc tả mới tại mục 3 và 4 là cơ sở triển khai; không coi ảnh cũ là thiết kế đầy đủ của phần bổ sung.

Ảnh cũng chưa thể hiện mục Tóm tắt file md và còn ghi ví dụ history dạng cũ `0926.log`. Khi triển khai dùng `ROOT/history/2026-09.log` theo quy tắc mới, không lấy tên trong ảnh làm cấu hình. Không đổi tên hoặc di chuyển log thật trong lần sửa plan này.

### Nguồn mặc định, cây input

![Nguồn mặc định quét cây thư mục con](assets/images/tkinter-v3-01-input.png)

### Browse nguồn ngoài

![Browse file hoặc thư mục và giữ cấu trúc output](assets/images/tkinter-v3-02-browse.png)

### Lựa chọn khi trùng output

![Hộp thoại Thay thế hoặc Bỏ qua](assets/images/tkinter-v3-03-replace.png)

Ảnh minh họa có khác biệt nhỏ về nhãn nguồn và thanh công cụ. Khi viết GUI dùng thống nhất `Tác vụ`, `Nguồn`, `Lọc`, `Tìm tên`, `Duyệt (Browse)`, `Về input`, `Quét lại`; không thêm bản dịch tiếng Anh cho mọi nhãn. Bỏ câu “Không lựa chọn tự động áp dụng toàn bộ” mà công cụ sinh ảnh đã đưa vào dialog; đây là ghi chú thiết kế, không cần hiển thị với người dùng. Cây và nhật ký phải có scrollbar, dù ảnh không thể hiện đủ ở mọi vùng.

Mục tiêu bố cục: khoảng 1100x800, co giãn; kiểm tra màn hình 1366x768 và DPI 125%, 150%. Khi chạy, khóa Browse/nguồn/tác vụ/selection; vẫn đọc được cây và log. Nút dừng ghi đầy đủ `Dừng sau lượt hiện tại`. Với Native, một lượt hiện tại là cả batch subprocess, không phải một file riêng.

Prompt lưu tại [imagegen-prompts-v3.md](assets/images/imagegen-prompts-v3.md).

## 7. Phạm vi sửa code dự kiến

| File | Thay đổi |
|---|---|
| `pdf-2-md.bat` | Launcher 1/2/3/0, chữ không dấu; gọi venv trực tiếp; bỏ picker cũ sau nghiệm thu |
| `src/gui_app.py`, mới | Tk/ttk, Browse, cây Explorer, dialog Replace/Bỏ qua, queue polling |
| `src/gui_runner.py`, mới | Registry tác vụ, snapshot, quét nền, chọn file, mapping output, khóa phiên, điều phối và nhận report |
| `src/run_report.py`, mới | Job manifest, report JSON và kiểm tra trạng thái |
| `src/history_log.py`, mới | Record lịch sử và prepend file tháng |
| `src/pptx_native.py`, mới | Đọc Open XML bằng Python chuẩn, xuất Markdown theo slide |
| `src/office_com.py`, mới | Phát hiện Office, adapter COM ctypes giới hạn, kiểm tra khả dụng từng ứng dụng |
| `src/office_convert.py`, mới | DOC/PPT/XLS sang Open XML, đổi tên, kiểm tra kết quả, điều kiện xóa nguồn |
| `src/pptx_api.py`, mới | PowerPoint xuất PDF tạm, gọi Scan/Refine hiện có với mapping PPTX gốc |
| `src/summary_md.py`, mới | Đọc MD, chuẩn bị nội dung, gọi Gemini Flash theo GEMINI_MODEL, kiểm tra response và dựng Summary ba mục theo ngôn ngữ/loại văn bản |
| `src/markdown_viewer.py`, mới | Cửa sổ Source/Preview bằng Tkinter, parser Markdown giới hạn, thao tác New/Open/Save/Save As |
| Script 2 đến 6 | Nhận output tường minh, staging, report/exit code đúng; bỏ skip ngầm trong luồng GUI |
| `src/image_extractor.py` | Chỉ sửa phần đường dẫn nếu cần để assets tương đối với output mới |
| `README.md` | Cách Browse, tên output, Replace/Bỏ qua, lịch sử |
| `tests/` | Kiểm thử mapping, overwrite, lịch sử và điều phối lỗi |

Mã điều phối mới dùng `tkinter`, `pathlib`, `os`, `stat`, `threading`, `queue`, `subprocess`, `tempfile`, `json`, `datetime`, `shutil`, `uuid`, `msvcrt`; phần mới thêm `winreg`, `ctypes`, `zipfile`, `xml.etree.ElementTree`, `hashlib`. Không thêm framework GUI, plugin hay dependency cho Browse/history. Các thư viện đọc PDF/Office và SDK hiện tại vẫn cần cho engine cũ. Chuyển định dạng Office và render slide cần Office desktop đã cài, không phải thư viện Python thay thế Office.

### Giao tiếp GUI và backend

Dùng job manifest UTF-8 tạm thay list path đơn giản khi cần chỉ định output cho từng file. Mỗi job có input, output tường minh, tác vụ, lựa chọn create/replace và mã lượt. Backend nhận `--manifest` và `--report`, giữ positional CLI cũ để tương thích. Manifest giúp xử lý tên Unicode, ký tự đặc biệt và mapping riêng trong cùng batch mà không ghép chuỗi shell.

Native vẫn chạy một subprocess cho cả danh sách đủ điều kiện, pool nội bộ giữ nguyên. Bỏ qua loại khỏi manifest trước khi khởi chạy. Script 3 đến 6 chạy tuần tự từng file trong MVP. Gọi `[sys.executable, '-u', script, ...]`, `shell=False`, cwd ROOT, UTF-8, child không mở cửa sổ console riêng.

Report ghi đủ input với `success`, `skipped`, `failed`, `partial`, output và lỗi. Runner dịch sang nhãn tiếng Việt. Exit code khác 0 khi failed/partial; thiếu report là lỗi, không suy thành công từ file có sẵn hoặc chuỗi log. Report không thay thế history bền vững.

Worker đẩy event vào queue; chỉ main thread gọi Tk/after. Main thread polling khoảng 100 ms, xử lý event theo lô có giới hạn. Log trên GUI giữ khoảng 2.000 dòng gần nhất; history không bị cắt theo giới hạn hiển thị. Quét và conversion không chặn mainloop.

### API và hiệu năng

Giữ batch Native, không bọc thêm pool ngoài pool. Gemini concurrency 1, không gọi API khi mở GUI, Browse, quét, xem cây hoặc Bỏ qua. Replace với Gemini sẽ phát sinh một lần chuyển đổi lại; mô tả rõ trước Start, không tự chạy thêm Refine.

Giữ retry có giới hạn trong backend, không thêm retry ở GUI. Bổ sung deadline polling/request; xóa upload trong finally. Chunk thiếu là partial, không thay file output đã tốt. Tách ảnh và xử lý văn bản giữ logic hiện có.

Refine Office hiện upload trực tiếp DOCX/XLSX chưa được xác minh trong phiên khảo sát. Phải kiểm tra trước nghiệm thu; nếu không hỗ trợ đường đó, dùng Mammoth/pandas trích xuất Local rồi gửi text/Markdown, và mô tả đúng trên GUI. Không tự thêm Office/LibreOffice.

Đo thời gian quét cây, mở GUI, throughput Native, Preview với file lớn và thời gian ghi log theo kích thước file. Chưa có benchmark cho thiết kế này. Chưa làm EXE, renderer Mermaid/LaTeX, preview giống hoàn toàn Obsidian, resume từng chunk, database hoặc lịch chạy tự động.

## 8. Sửa BAT

- Giữ ROOT theo `%~dp0`; menu dùng `choice /c 1230`, nhánh 0 dùng `exit /b 0`.
- Setup tạo venv nếu thiếu; kiểm tra lỗi từng bước; gọi python của venv với `-m pip`, không phụ thuộc activate/pip toàn cục. Kiểm tra Tk, báo tiếng Việt không dấu.
- GUI gọi trực tiếp `.venv/Scripts/python.exe src/gui_app.py`, chờ đóng rồi về menu. Thiếu venv hoặc script thì báo lỗi.
- Giữ Git Sync với kiểm tra/xác nhận sẵn có. Không tự commit/push khi chạy conversion. Chú ý ký tự `!` trong commit message khi xử lý delayed expansion.
- Bỏ conversion label, picker, BATCH_OK và PICKFILE trong BAT sau khi GUI được kiểm thử. Toàn bộ quét, chọn, output/history nằm trong Python.

## 9. Trình tự thực hiện và kiểm thử

- [ ] Chốt mapping nguồn/đích và manifest, không thay đổi output cũ tự động.
- [ ] Triển khai đúng các lựa chọn Summary đã chốt: template ba mục, ngôn ngữ, loại văn bản, nguồn/đích và chia file dài.
- [ ] Thêm mục Tóm tắt file md, combo Việt/Anh/song ngữ và loại văn bản, hậu tố `_summary.md`.
- [ ] Thêm nút Xem Markdown và `markdown_viewer.py` theo phạm vi Tkinter cơ bản; không cài renderer web hoặc thư viện mới.
- [ ] Spike COM cho Word/Excel/PowerPoint, kiểm tra version, ownership, SaveAs, mở lại và cleanup trước khi làm menu Office.
- [ ] Viết PPTX Native và đường PowerPoint PDF cho Scan/Refine; kiểm thử thứ tự slide và giới hạn trích xuất.
- [ ] Thêm ba mục chức năng dùng chung nguồn/cây, đổi tên từng file, checkbox xóa và trạng thái ứng dụng Office; ẩn điều khiển không áp dụng khi đổi mục.
- [ ] Viết quét đệ quy, khóa phiên, mapping, report và history bằng Python chuẩn.
- [ ] Nối engine với staging/output tường minh; giữ batch Native; kiểm tra assets và partial.
- [ ] Viết GUI Browse/cây/dialog và trạng thái khi chạy.
- [ ] Đổi BAT, cập nhật README; rà tiếng Việt và bỏ icon/gạch ngang dài trong phần code được sửa.
- [ ] Chạy bộ test mock, smoke test mẫu nhỏ; không chạy ALL trên dữ liệu thật, không Git Sync thật để test menu.

| Ca kiểm thử | Kết quả cần đạt |
|---|---|
| Mở GUI chưa Browse | Tự hiện file input và thư mục con theo combo |
| Đổi PDF sang Word/Excel/Refine | Lọc đúng suffix, giữ nguồn, bỏ selection cũ |
| Browse thư mục/file, hủy Browse, Về input | Đúng gốc, đúng selection, không convert ngoài lựa chọn |
| Cây nhiều tầng, chọn cha và con | Giữ cấu trúc, không convert trùng |
| Junction/symlink, thư mục không có quyền | Không lặp vô hạn; lỗi một nhánh không dừng toàn bộ scan |
| Input cùng tên khác thư mục | Output nằm trong các thư mục tương ứng |
| Hai input cùng đích trong một lượt | Chặn trước worker, không cho ghi cạnh tranh |
| Output tồn tại, Bỏ qua | Không gọi converter/API, giữ file cũ, có record lịch sử |
| Output tồn tại, Replace thành công | Giữ basename, thay sau conversion; Markdown và assets mới đọc được |
| Replace lỗi/partial/đầy ổ/không có quyền | Bản cũ còn nguyên; trạng thái đúng, partial tách riêng |
| Đích thay đổi giữa preflight và công bố | Hỏi lại, không dùng lựa chọn Replace cũ |
| Tên tiếng Việt, khoảng trắng, !, &, dấu ngoặc | Path truyền nguyên vẹn qua manifest |
| Nhiều Native | Một batch subprocess với output riêng mỗi file |
| Qua ranh giới tháng/năm | 2026-09 sang 2026-10, 2026-12 sang 2027-01; record theo thời điểm ghi |
| Ghi nhiều record, có dòng lỗi chứa newline | JSON mỗi record một dòng; mới nhất trên cùng |
| Lỗi ghi history, hai phiên, crash giữa ghi tạm | Log cũ không hỏng; không ghi đè mất record do hai writer |
| Worker lỗi/đóng cửa sổ/dừng | Không gọi Tk từ worker, dừng lên lịch đúng, giải phóng khóa |
| Chạy Local hoặc Bỏ qua khi offline | Không gọi API |
| Nhãn GUI/BAT/log | Tiếng Việt đúng quy tắc, không emoji/icon trang trí/gạch ngang dài |
| PPTX Native khi không cài Office | Trích text/bảng/ảnh hỗ trợ; không gọi API, slide ảnh không báo có OCR |
| PPTX Scan/Refine khi thiếu PowerPoint hoặc API | Nút chạy inactive, mô tả đúng thành phần thiếu; Native không bị khóa |
| PPTX slide 1/2/10, group, slide ẩn | Đúng thứ tự presentation và phạm vi; không sort tên XML sai |
| Office chỉ cài Word, COM lỗi, license yêu cầu tương tác | Chỉ bật lựa chọn thực sự dùng được; không suy khả dụng từ registry |
| Office 365/2021/2024 và bản chỉ báo 16.0 | Nhận diện bằng sản phẩm và probe, không chấp nhận version thiếu căn cứ |
| DOC/PPT/XLS nhiều thư mục | File mới nằm cạnh từng nguồn, tên gốc chỉ đổi extension |
| Đổi tên từng file, hủy, tên cấm, hai tên trùng | Hỏi đúng mỗi file, không thoát thư mục, chặn collision |
| Replace/Bỏ qua trong mục Office | Kiểm tra bản mới trước Replace; Bỏ qua không mở Office, không xóa nguồn |
| Xóa nguồn bật/tắt, nguồn đổi trong lúc chạy | Chỉ unlink đúng nguồn chưa đổi sau xác minh/log; tắt thì giữ nguyên |
| Macro, mất tính năng, password, Protected View | Không chấp nhận âm thầm rồi xóa nguồn |
| Conversion tốt nhưng unlink/log sau xóa lỗi | Phân biệt kết quả conversion và xóa; không báo đã xóa khi chưa xác minh |
| Phiên Office người dùng đang mở | Không sửa/đóng tài liệu người dùng, không kill theo tên process |
| Chuyển mục Office sang Markdown | Không mang cờ xóa/đích cạnh nguồn sang Markdown |
| Summary Việt/Anh/song ngữ | Đúng ba mục mới, đúng ngôn ngữ; không còn yêu cầu 3 câu cũ |
| Nguồn không nêu hạn chế hoặc giải pháp | Ghi thiếu dữ liệu nguồn, không tạo giải pháp hoặc kết luận mới |
| Loại văn bản và cấu trúc Summary | Đúng ba mục; kỹ thuật giữ số liệu/điều kiện, báo cáo giữ kết quả/hành động; không thêm Trích dẫn |
| Model chung và link nguồn | Dùng GEMINI_MODEL Flash, không fallback âm thầm; link cuối mở đúng MD nguồn, không thêm URL Reference |
| MD nằm trong output, `_summary.md`, file rỗng | Cho đọc output theo chính sách Summary, loại summary lặp và file rỗng |
| Summary trùng tên chọn Bỏ qua | Không gọi API, không sửa/xóa nguồn; vẫn ghi history |
| Nội dung MD chứa prompt, URL, wikilink | Chỉ coi là dữ liệu nguồn, không thực thi hoặc tải nội dung ngoài |
| File dài/response bị cắt/chunk lỗi | Không bỏ đuôi âm thầm, không công bố như summary đầy đủ |
| Xem Markdown | Source chỉnh sửa, Preview rich text cơ bản chỉ đọc; Mermaid/LaTeX/HTML/plugin không được render hoặc thực thi |

Dùng `unittest`, `tempfile`, mock converter/API và clock để kiểm thử không tốn token API. Bộ mẫu output dùng thư mục thử nghiệm riêng. Không coi ảnh mockup là bằng chứng giao diện đã chạy.

## 10. Tham chiếu và điều kiện hoàn thành

- [[pdf-2-md.bat]], [[requirements.txt]], [[README]], thư mục `refer-2-convert_font`, các script `src/2_pdf_native.py` đến `src/6_gemini_refine.py`.
- [Python Tkinter](https://docs.python.org/3/library/tkinter.html): widget và event loop.
- [Python subprocess](https://docs.python.org/3/library/subprocess.html): gọi child process.
- [Gemini Document understanding](https://ai.google.dev/gemini-api/docs/document-processing): xử lý tài liệu; không suy ra raw Office đã chạy thành công từ mô tả chung.

Hoàn thành triển khai khi menu 1/2/3/0 hoạt động, đủ tác vụ cũ và PPTX Native/Scan/Refine, mục Chuyển file Office có kiểm tra ứng dụng và output cạnh nguồn đúng, đổi tên/xóa nguồn đúng điều kiện, Summary Gemini Flash đúng ba mục/ngôn ngữ đã chọn và hậu tố `_summary.md`, Xem Markdown có Source/Preview cơ bản và thao tác lưu an toàn, cây input/Browse và output Markdown tương đối đúng, Replace/Bỏ qua đúng, lịch sử `ROOT/history/yyyy-mm.log` mới nhất ở trên, backend báo đúng lỗi/partial và các ca kiểm thử trên đạt. Hiện mới cập nhật kế hoạch; ảnh chưa minh họa phần Office/PPTX/Summary/Xem Markdown bổ sung.
