import os, sys, glob, mammoth, re
from markdownify import markdownify as md

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(BASE_DIR, 'data', 'input')
# GUI dat PDF2MD_OUTPUT_DIR de giu cau truc thu muc con cua input trong output.
# Khong dat bien nay thi hanh vi CLI cu giu nguyen.
OUTPUT_DIR = os.environ.get('PDF2MD_OUTPUT_DIR') or os.path.join(BASE_DIR, 'data', 'output')
FORCE = os.environ.get('PDF2MD_FORCE') == '1'

def process():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    target = sys.argv[1] if len(sys.argv) > 1 else "ALL"
    if target == "ALL":
        files = glob.glob(os.path.join(INPUT_DIR, '*.docx'))
    else:
        file_path = os.path.join(INPUT_DIR, target)
        if not os.path.exists(file_path):
            print(f"❌ Khong tim thay file: {target}")
            return
        files = [file_path]
        
    for f in files:
        base = os.path.splitext(os.path.basename(f))[0]
        out_path = os.path.join(OUTPUT_DIR, f"{base}.md")
        if os.path.exists(out_path) and not FORCE: continue
        print(f"📝 [Word Local] Dang xu ly: {base}...")
        
        try:
            with open(f, "rb") as docx_file:
                # 1. Ép Mammoth xuất ra HTML để "khóa" toàn vẹn cấu trúc Bảng biểu
                res = mammoth.convert_to_html(docx_file)
                html_content = res.value
                
                # 2. Dùng markdownify để dựng lại thành văn bản & bảng Markdown cực đẹp
                md_text = md(
                    html_content, 
                    heading_style="ATX", 
                    strip=['a'],  # Tự động triệt tiêu toàn bộ thẻ <a> rác sinh ra từ mục lục Word
                    escape_asterisks=False,
                    escape_underscores=False
                )
                
                # 3. BỘ LỌC RÁC KẾ THỪA TỪ EXCEL (Xử lý hậu kỳ)
                # Dọn dẹp các đường vạch ngang rác sinh ra do format gạch dưới
                md_text = re.sub(r'_{2,}', '', md_text)
                
                # Diệt dứt điểm các dấu gạch chéo ngược "\" vô duyên bị chèn trước các dấu câu
                md_text = re.sub(r'\\([.\-\+\(\)\[\]*_])', r'\1', md_text)
                
                # Tối ưu khoảng trắng, gom các hàng rỗng thừa thãi về thành 1 hàng chuẩn
                md_text = re.sub(r'\n{3,}', '\n\n', md_text)  
                
                with open(out_path, 'w', encoding='utf-8') as out: out.write(md_text)
                
        except Exception as e: 
            print(f"Loi: {e}")

if __name__ == "__main__": process()