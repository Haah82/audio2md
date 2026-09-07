Cơ chế Auto-reload đã kích hoạt thành công: hệ thống charge ₫150,000, khấu trừ 10% VAT (₫15,000), credit thực nhận vào dự án là ₫135,000. Cùng với số dư cũ, Ending balance hiện tại đạt ₫151,256. Với cấu hình nạp tự động khi số dư dưới 10k, pipeline pdf2md đã được bảo vệ khỏi rủi ro gián đoạn do lỗi 402 Payment Required.




Tuy nhiên, mức nạp ròng 135k/lần là tương đối mỏng nếu chạy Auto mode cho các bộ Hồ sơ mời thầu (Bidding Documents) hoặc Báo cáo Khảo sát địa chất (Geological Survey Reports) định dạng Scanned PDF hàng trăm trang. Để tối ưu hóa dải credit này, kiến trúc phần mềm tại thư mục src/ cần được tái cấu trúc ở cấp độ tiền xử lý (Preprocessing) và quản lý tải.




1. Tối ưu thuật toán Vision AI trong 3_pdf_scan.py







Bản vẽ thiết kế (Mặt bằng móng, Cắt dọc tuyến, Biện pháp thi công cừ Larsen) thường ở khổ A3/A1. Nếu đẩy trực tiếp ma trận pixel gốc lên Gemini Vision, Input Tokens sẽ vượt ngưỡng rất nhanh.








Giải pháp: Bổ sung module xử lý ảnh cục bộ trước khi encode Base64. Ép kiểu ảnh về Grayscale và giới hạn kích thước tối đa.





MVP Code:



Python

import cv2
import numpy as np

def preprocess_engineering_drawing(image_path, max_dim=2048):
    # Đọc ảnh dạng Grayscale để giảm channel từ 3 (RGB) xuống 1
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    
    # Adaptive Thresholding để làm nổi bật nét vẽ/text CAD trên nền scan mờ
    img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    
    # Scale down nếu vượt quá max_dim để bảo vệ quota
    h, w = img.shape
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    
    return img


2. Tối ưu Pipeline xử lý Bảng Tiên lượng/Dự toán tại 5_excel.py & 6_gemini_refine.py







Các file Excel Bảng Tiên lượng (Bill of Quantities - BOQ) thường chứa rất nhiều ô trống (NaN), merge cells, và công thức.








Giải pháp: Chuyển đổi trung gian. Trong 5_excel.py, bắt buộc dùng pandas dropna(how='all') để dọn rác, sau đó convert dataframe sang dạng CSV string hoặc Markdown table thu gọn trước khi truyền vào payload của 6_gemini_refine.py. Không bao giờ truyền raw Excel XML hay JSON nguyên bản vì sẽ sinh ra hàng ngàn tokens vô nghĩa.





Prompt Engineering: Tại 6_gemini_refine.py, thiết lập response_mime_type="application/json" và truyền một JSON Schema chuẩn hóa cho cấu trúc BOQ để ép LLM trả về đúng key/value, triệt tiêu tokens giải thích thừa.



3. Khai thác API Pool trong .env







Khuyến nghị thiết lập API Routing trực tiếp trong pipeline thay vì chỉ dùng 1 key trả phí.








Bổ sung các biến GEMINI_API_KEY_FREE_1, GEMINI_API_KEY_FREE_2, GEMINI_API_KEY_PAID vào file .env.





Thiết kế một Singleton API Manager: Mặc định route traffic của các task text-only (như xử lý .docx trong 4_word.py hoặc PDF Native trong 2_pdf_native.py) sang các node Free Tier. Chỉ switch sang node Paid Tier (số dư 151k) cho các task Vision hạng nặng (3_pdf_scan.py). Điều này giúp giãn biên độ burn rate của 135k credit lên tối đa. Quy trình Khởi tạo & Cấu hình API Routing cho Free Tier Quota




Để khai thác luồng Free Tier (15 RPM, 1M TPM) phân tải cho pipeline pdf2md, cần tạo các API key độc lập gắn với từng Google Cloud Project nhàn rỗi.




1. Khởi tạo API Key trên Google AI Studio








Truy cập Google AI Studio: [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)





Chọn Create API key.





Tại modal Create API key in a new or existing project, chọn project thứ nhất: Gstudio-project. Copy chuỗi AIza... được tạo ra.





Lặp lại bước 2, chọn project thứ hai: Gemini Project. Copy chuỗi AIza... tương ứng.



2. Cập nhật biến môi trường (.env) Tại thư mục gốc của dự án pdf2md, mở hoặc tạo file .env và khai báo cấu hình API Pool:




Code snippet

# Môi trường: /pdf2md/.env
GEMINI_API_KEY_FREE_1=AIzaSy_YOUR_KEY_FROM_GSTUDIO_PROJECT
GEMINI_API_KEY_FREE_2=AIzaSy_YOUR_KEY_FROM_GEMINI_PROJECT


3. Kiến trúc Inject Key vào Python Scripts (MVP) Thay vì load tĩnh một key duy nhất, cần import thư viện python-dotenv và điều hướng linh hoạt (route) trong từng module xử lý tài liệu tại thư mục src/.








Tích hợp vào src/4_word.py và src/2_pdf_native.py (Task xử lý text, tải nhẹ):



Python

import os
import google.generativeai as genai
from dotenv import load_dotenv

# Khởi tạo load_dotenv() tại đầu file
load_dotenv()

# Binding riêng node Free 1
API_KEY = os.getenv("GEMINI_API_KEY_FREE_1")
if not API_KEY:
    raise ValueError("CRITICAL: Thiếu GEMINI_API_KEY_FREE_1 trong .env")

genai.configure(api_key=API_KEY)
# ... tiếp tục logic xử lý MS Word / Native PDF ...






Tích hợp vào src/5_excel.py (Task tiền xử lý Bảng tiên lượng/BOQ):



Python

import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Binding riêng node Free 2 để tránh Rate Limit (429) do xung đột với pipeline khác
API_KEY = os.getenv("GEMINI_API_KEY_FREE_2")
if not API_KEY:
    raise ValueError("CRITICAL: Thiếu GEMINI_API_KEY_FREE_2 trong .env")

genai.configure(api_key=API_KEY)
# ... tiếp tục logic parse DataFrame bằng pandas ...


Lưu ý Vận hành (Ops): Khi chạy auto mode (quét toàn bộ thư mục data/input/) qua file pdf-2-md.bat, việc tách bạch API key này đảm bảo các file Word, PDF native và Excel được đẩy song song qua 2 luồng Free Tier riêng biệt, giữ nguyên số dư của key Paid Tier chỉ dành riêng cho Vision AI (3_pdf_scan.py) và mô hình Refine phức tạp (6_gemini_refine.py).