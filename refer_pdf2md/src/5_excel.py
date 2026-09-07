import os, sys, glob, re
import pandas as pd

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
        files = glob.glob(os.path.join(INPUT_DIR, '*.xlsx'))
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
        print(f"📊 [Excel Local] Dang xu ly: {base}...")
        
        try:
            md_content = ""
            xls = pd.read_excel(f, sheet_name=None, header=None)
            
            for sheet, df in xls.items():
                # 1. Xóa các dòng và cột rỗng hoàn toàn
                df.dropna(how='all', inplace=True)
                df.dropna(axis=1, how='all', inplace=True)
                
                if df.empty:
                    continue
                
                df.fillna("", inplace=True)
                
                # 2. Bỏ thẻ <br>, thay dấu xuống dòng (Alt+Enter) bằng dấu cách để dàn trang mềm mại
                def clean_cell(x):
                    if isinstance(x, str):
                        # Thay \n thành dấu cách thay vì <br> 
                        x = x.replace('\n', ' ')
                        # Xử lý các khoảng trắng thừa liên tiếp thành 1 khoảng trắng duy nhất
                        x = re.sub(r'\s+', ' ', x).strip()
                    return x
                
                if hasattr(df, 'map'):
                    df = df.map(clean_cell)
                else:
                    df = df.applymap(clean_cell)
                
                # 3. Tách các dòng tiêu đề (chỉ có 1 cột chứa dữ liệu) ra khỏi bảng
                cleaned_rows = []
                pre_text = ""
                
                for idx, row in df.iterrows():
                    non_empty_cells = [val for val in row if str(val).strip() != ""]
                    if len(non_empty_cells) == 1:
                        # Dòng này chỉ có 1 ô có chữ -> Thường là tiêu đề bảng (VD: BẢNG CHI PHÍ...)
                        pre_text += f"**{non_empty_cells[0]}**\n\n"
                    elif len(non_empty_cells) > 1:
                        # Dòng có từ 2 ô trở lên -> Thuộc về bảng
                        cleaned_rows.append(row)
                
                md_content += f"## Sheet: {sheet}\n\n"
                md_content += pre_text
                
                # 4. Tạo bảng Markdown nếu còn dữ liệu
                if cleaned_rows:
                    new_df = pd.DataFrame(cleaned_rows)
                    # Thiết lập lại cột bị rỗng sau khi tách tiêu đề
                    new_df.dropna(axis=1, how='all', inplace=True)
                    
                    if not new_df.empty:
                        headers = new_df.iloc[0].tolist()
                        new_df = new_df[1:]
                        md_content += new_df.to_markdown(index=False, headers=headers) + "\n\n"
                
            # --- BỘ LỌC RÁC TỔNG THỂ KẾ THỪA TỪ PDF & WORD ---
            md_content = re.sub(r'</?a[^>]*>', '', md_content)  
            md_content = re.sub(r'_{3,}', '', md_content)  
            # Diệt dấu escape (\) thừa do các phần mềm tự chèn
            md_content = re.sub(r'\\([.\-\+\(\)\[\]*_])', r'\1', md_content)     
            md_content = re.sub(r'\n{3,}', '\n\n', md_content)  

            with open(out_path, 'w', encoding='utf-8') as out: out.write(md_content)
            
        except Exception as e: print(f"Loi: {e}")

if __name__ == "__main__": process()