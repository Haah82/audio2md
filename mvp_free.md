# MVP Free-First: vắt kiệt Free Tier trước, chỉ rót sang Paid khi hết

Mẫu thiết kế rút ra từ `audio2md`, viết để **kế thừa sang dự án khác**. Nguyên tắc:
mỗi request đi qua key rẻ nhất còn dùng được; chỉ tiêu tiền khi thật sự không còn
lựa chọn miễn phí trong ngưỡng chờ chấp nhận được.

Tham chiếu code: [`src/gemini_pool.py`](src/gemini_pool.py) (pool, tái sử dụng được nguyên file),
[`src/main_audio2md.py`](src/main_audio2md.py) (cách gọi).

---

## 1. Nguyên tắc gốc

| # | Nguyên tắc | Vì sao |
|---|---|---|
| 1 | **Free trước, paid sau** | Mỗi project Google Cloud có hạn mức riêng. Nhiều key free = nhiều hạn mức cộng dồn. |
| 2 | **Mặc định là PAID khi không chắc** | Gõ nhầm tên biến không được phép đẩy tài liệu mật qua Free Tier. Sai sót phải nghiêng về phía an toàn, không nghiêng về phía rẻ. |
| 3 | **429 thì đổi key, không ngồi chờ** | Hết quota là vấn đề của *key*, không phải của model. Retry cùng key = phí thời gian. |
| 4 | **Chờ ngắn thì rẻ hơn trả tiền** | Cooldown 30s mà nhảy sang paid là mua 30 giây bằng tiền. Có ngưỡng để quyết định. |
| 5 | **Trạng thái cooldown sống xuyên suốt phiên** | Key vừa báo cạn ở bước A không cần dò lại ngay ở bước B. |

## 2. Quy ước đặt tên biến (phần quan trọng nhất khi port)

> **Chỉ tên biến chứa chữ `FREE` mới được coi là Free Tier. Mọi tên khác — kể cả
> `GEMINI_API_KEY` trần — đều mặc định là trả phí.**

Đây là cơ chế fail-safe, không phải quy ước cho đẹp. Theo điều khoản Gemini API,
nội dung gửi qua dịch vụ **không trả phí** có thể được Google dùng để cải thiện sản
phẩm **và có người thật xem xét**. Với hồ sơ mời thầu, hợp đồng, báo cáo khảo sát có
ràng buộc bảo mật, phải đặt `GEMINI_KHONG_DUNG_FREE=1`.

Pool tự quét toàn bộ biến môi trường khớp `GEMINI_API_KEY*`, nên **thêm key mới chỉ
cần thêm một dòng vào `.env`, không đụng code**:

```
GEMINI_API_KEY_FREE_1=...      -> Free Tier
GEMINI_API_KEY_FREE_2=...      -> Free Tier
GEMINI_API_KEY_FREE_3=...      -> tự động nhận, không sửa code
GEMINI_API_KEY_PAID=...        -> trả phí
```

Key trùng giá trị bị loại tự động; key rỗng hoặc còn `YOUR_...` bị bỏ qua.

## 3. Thuật toán chọn key

Với mỗi model (model chính trong `GEMINI_MODEL` trước, rồi tới dự phòng), sắp xếp key theo khoá:

```python
(thoi_gian_cho_con_lai > GEMINI_CHO_FREE_TOI_DA, thu_tu_goc)
```

Trong đó `thu_tu_goc` là **toàn bộ key FREE trước, rồi tới PAID**. Kết quả:

| Trạng thái key FREE | Key PAID | Chọn | Lý do |
|---|---|---|---|
| Rảnh | Rảnh | **FREE** ngay | Rẻ nhất, không chờ |
| Cooldown 30s (dưới ngưỡng) | Rảnh | **FREE**, chờ 30s | Chờ 30s rẻ hơn trả tiền |
| Cooldown 200s (trên ngưỡng) | Rảnh | **PAID** ngay | Không đáng treo batch 200s |
| Tất cả cooldown dài | Cooldown dài | **FREE** (chờ) | Ngưỡng chỉ đổi *thứ tự ưu tiên*, không phải giới hạn cứng — không bao giờ bỏ cuộc |

Phân loại lỗi quyết định hành vi tiếp theo — đây là chỗ hay làm sai:

| Lỗi | Nhận diện | Xử lý |
|---|---|---|
| Hết quota | `429`, `RESOURCE_EXHAUSTED`, `quota`, `rate limit` | Đọc `retryDelay` Google trả về, cho **key đó** nghỉ đúng số giây (không có thì dùng `GEMINI_COOLDOWN_MAC_DINH`), chuyển key kế tiếp |
| Model không tồn tại | `404`, `not found`, `not supported` | Loại **model** khỏi danh sách vĩnh viễn, sang model kế. Không quay vòng hết key — key không có lỗi gì |
| Lỗi khác | còn lại | Ghi cảnh báo, thử key kế tiếp |

Phân biệt 429 với 404 là điểm khác biệt lớn nhất so với retry loop ngây thơ: nhầm
404 thành 429 sẽ dò hết mọi key cho một model vốn không tồn tại.

## 4. Bảng biến `.env`

Tất cả biến chỉnh tinh đang **để trống trong `.env` hiện tại**, tức đang chạy bằng
giá trị mặc định trong code. Chỉ bỏ comment khi cần đổi.

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `GEMINI_API_KEY_FREE_*` | — | Key Free Tier. Bao nhiêu key cũng được |
| `GEMINI_API_KEY_PAID` | — | Key trả phí, dùng khi free cạn |
| `GEMINI_MODEL` | *(trống)* | Model chính, thử trước tiên. Bỏ trống thì chạy thẳng danh sách dự phòng `gemini-3.6-flash` → `gemini-2.5-flash`. `.env` hiện tại đặt `gemini-3.6-flash` để tránh vòng lặp quét 404 |
| `GEMINI_CHO_FREE_TOI_DA` | `90` | **Ngưỡng chờ**. Cooldown dưới mức này thì nằm chờ để giữ miễn phí |
| `GEMINI_FREE_MIN_INTERVAL` | `4.5` | Giây tối thiểu giữa 2 lượt gọi **cùng một** key free (né rate limit theo phút) |
| `GEMINI_PAID_MIN_INTERVAL` | `0.5` | Như trên, cho key trả phí |
| `GEMINI_COOLDOWN_MAC_DINH` | `60` | Giây nghỉ khi Google **không** trả về `retryDelay` |
| `GEMINI_KHONG_DUNG_FREE` | `0` | Đặt `1` để **cấm tuyệt đối** Free Tier (tài liệu mật) |

### Vì sao ngưỡng là 90s

`retryDelay` Google trả về thường rơi vào 20–60s, nên ngưỡng 90s giữ **phần lớn**
trường hợp ở lại miễn phí, đồng thời chặn được cooldown theo **hạn mức ngày** (thường
dài hơn nhiều) làm treo cả batch.

Hai đầu mút để tự chỉnh:

- `GEMINI_CHO_FREE_TOI_DA=0` — không bao giờ chờ, cạn free là trả phí ngay. Nhanh nhất, đắt nhất.
- Đặt rất lớn (vd `86400`) — không bao giờ bỏ free. Rẻ nhất, nhưng batch dài có thể treo rất lâu.

**Đánh đổi đã chấp nhận:** với ngưỡng 90s, một bước sau có thể phải chịu thêm vài
lượt gọi hỏng để thử lại key free vừa cạn, thay vì đi thẳng sang paid. Đây là giá
phải trả để ở lại free tier.

## 5. Bốn cái bẫy khi port sang dự án khác

**1. File đã upload thuộc về đúng key đã upload nó.** Upload bằng key A rồi 429, đổi
sang key B thì *phải upload lại* — handle cũ vô nghĩa với B. Hệ quả kiến trúc:
toàn bộ chu trình upload + generate phải nằm **trong một closure** truyền cho pool,
không tách rời:

```python
def boc_bang(client, model):
    uploaded = client.files.upload(file=duong_dan)   # trong cùng lượt key
    try:
        return client.models.generate_content(model=model, contents=[uploaded, prompt]).text
    finally:
        client.files.delete(name=uploaded.name)      # dọn cả khi 429

pool.chay(boc_bang, "Bóc băng")
```

**2. Phải dọn file cả trên nhánh lỗi.** Không có `finally`, mỗi lần retry bỏ lại một
file rác trong kho Files API của từng project free — âm thầm ăn hạn mức lưu trữ.

**3. Dùng `models.generate_content`, đừng dùng `chats.create().send_message()`.** Chat
session mang theo history và gửi lại mỗi lượt. Với lời gọi một phát, phần history đó
là token trả tiền vô ích.

**4. Nạp `.env` TRƯỚC khi import pool.** Pool đọc cấu hình ngay lúc khởi tạo:

```python
load_dotenv(os.path.join(BASE_DIR, '.env'))
from gemini_pool import GeminiPool          # phải sau load_dotenv
```

## 6. Cách kế thừa sang dự án khác

1. Copy `src/gemini_pool.py` — không phụ thuộc gì vào audio2md, chỉ cần `google-genai` và biến môi trường.
2. Copy khối biến `GEMINI_*` trong `.env`.
3. Bọc mỗi lời gọi API thành `pool.chay(ham, "mô tả")`, trong đó `ham(client, model)` **tự chứa** toàn bộ chu trình (xem bẫy #1). Ném exception ra ngoài để pool tự đổi key.
4. Gọi `pool.tong_ket()` cuối phiên để in số lượt free / paid đã dùng.

Pool không biết gì về audio, PDF hay Excel — mọi tác vụ Gemini đều dùng chung được.

## 7. Kết quả kiểm chứng

Kiểm bằng client giả, không gọi API thật. Dự án `audio2md` có 2 giai đoạn tốn token
là `_raw` (bóc băng, đắt nhất vì upload audio) và `_refine` (tinh luyện văn bản):

| Kịch bản | `_raw` | `_refine` | Kết luận |
|---|---|---|---|
| Mọi key còn quota | `f1` | `f1` | Không chạm PAID |
| Cả 2 key FREE cạn | `f1→f2→p1` | `f1→f2→p1` | Vắt kiệt FREE mới rót PAID |
| Quota hồi phục | `f1` | `f1` | Tự về lại FREE, không bỏ rơi key |
| `KHONG_DUNG_FREE=1` | `p1` | `p1` | Không byte nào qua Free Tier |
| FREE cooldown 30s, PAID rảnh | chờ 30s → `f1` | | Dưới ngưỡng: giữ miễn phí |
| FREE cooldown 200s, PAID rảnh | → `p1` ngay | | Trên ngưỡng: không treo batch |
| Đổi key giữa chừng | upload lại + dọn ở **cả 3** key | | Không để lại file rác |

Cả hai giai đoạn dùng **chung một pool**, nên free-trước-paid-sau là một đường code
duy nhất — không nhánh nào lách qua được.

## 8. Các đòn giảm token khác (ngoài pool)

Pool giảm *đơn giá*. Bốn đòn dưới đây giảm *số token* — thường ăn tiền hơn:

| Đòn | Hiệu quả |
|---|---|
| Lấy phụ đề có sẵn (`yt-dlp`) thay vì bóc băng audio | Bỏ hẳn giai đoạn đắt nhất. Đòn lớn nhất |
| Có sẵn `_raw.md` thì không bóc băng lại | Không trả tiền hai lần cho cùng một audio |
| `generate_content` thay cho chat session | Cắt token history thừa |
| Nén ảnh trong PDF trước khi upload | Giảm băng thông và lỗi upload, **không** giảm token — Google tính mỗi trang PDF là 258 token bất kể độ phân giải |

Dòng cuối là cái bẫy đáng nhớ khi port: tối ưu dung lượng file không đồng nghĩa với
tối ưu chi phí.
