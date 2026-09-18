# Check API — việc cần làm

## Hiện trạng (18/09/2026)

- Pool đã nhận **2 key FREE + 1 key PAID** và dùng `gemini-3.6-flash` trước.
- Cả hai key FREE trả **503 UNAVAILABLE / high demand**: lỗi tạm thời.
- `gemini-2.5-flash` trả **404**: không còn dùng được cho key mới.
- Key PAID trả phản hồi lỗi khi gọi `gemini-3.6-flash`.
- Link William Damon không được thêm vào `data/input/build-audio2md.md`; index hiện có mục 67 là Cynthia Osborne, đã có raw/refine.

## Checklist

1. [x] Viết src/check_api.py: list model generateContent theo nhãn key; --probe mới gửi prompt text nhỏ.
2. [x] Bỏ fallback hard-code. Pool đọc GEMINI_MODEL và GEMINI_FALLBACK_MODELS.
3. [x] Xử lý 503 ở FREE bằng exponential backoff, giới hạn lần thử và không dùng PAID.
4. [x] Phân loại 404 model/file; redact key khỏi error log.
5. [ ] Chạy unit test và smoke test sau khi sửa .venv; sau đó mới chạy lại William Damon.
