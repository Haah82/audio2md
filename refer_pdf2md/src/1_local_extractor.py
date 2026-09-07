import os
import glob
import pymupdf4llm
import fitz
import pandas as pd
import mammoth

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(BASE_DIR, 'data', 'input')
OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'output')
NEEDS_AI_FLAG = "NEEDS_AI"

def is_pdf_scanned_or_garbage(pdf_path, text_content):
    try:
        doc = fitz.open(pdf_path)
        num_pages = len(doc)
        doc.close()
        if len(text_content.strip()) < num_pages * 50: return True
        garbage_count = sum(text_content.count(c) for c in ['', '?', '\x0c'])
        if len(text_content) > 0 and (garbage_count / len(text_content)) > 0.05: return True
        return False
    except:
        return True

def process_xlsx(file_path):
    # Pandas + Tabulate xuat bang Obsidian hoan hao
    md_content = ""
    xls = pd.read_excel(file_path, sheet_name=None)
    for sheet_name, df in xls.items():
        md_content += f"## Sheet: {sheet_name}\n\n"
        md_content += df.to_markdown(index=False) + "\n\n"
    return md_content, False

def process_docx(file_path):
    # Mammoth boc text rat tot nhung xu ly bang bieu kem, nen danh dau NEEDS_AI de Gemini lo bang
    with open(file_path, "rb") as docx_file:
        result = mammoth.convert_to_markdown(docx_file)
        md_text = result.value
    # Tu dong yeu cau AI hieu dinh neu file Word qua ngan hoac kha nang chua bang
    needs_ai = True 
    return md_text, needs_ai

def extract_local():
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    files = glob.glob(os.path.join(INPUT_DIR, '*.*'))
    valid_exts = ['.pdf', '.docx', '.xlsx']
    
    for file_path in files:
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in valid_exts: continue
        
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        md_path = os.path.join(OUTPUT_DIR, f"{base_name}.md")
        flag_path = os.path.join(OUTPUT_DIR, f"{base_name}.{NEEDS_AI_FLAG}")
        
        if os.path.exists(md_path) and not os.path.exists(flag_path):
            continue
            
        print(f"[{ext.upper()}] Dang xu ly local: {base_name}...")
        try:
            needs_ai = False
            md_text = ""
            
            if ext == '.pdf':
                md_text = pymupdf4llm.to_markdown(file_path)
                needs_ai = is_pdf_scanned_or_garbage(file_path, md_text)
            elif ext == '.xlsx':
                md_text, needs_ai = process_xlsx(file_path)
            elif ext == '.docx':
                md_text, needs_ai = process_docx(file_path)
            
            if needs_ai:
                with open(flag_path, 'w', encoding='utf-8') as f: f.write(ext)
                # Ghi tam nhap ra md
                with open(md_path, 'w', encoding='utf-8') as f: f.write(md_text)
            else:
                with open(md_path, 'w', encoding='utf-8') as f: f.write(md_text)
                if os.path.exists(flag_path): os.remove(flag_path)
                
        except Exception as e:
            print(f"Loi {base_name}: {e}")
            with open(flag_path, 'w', encoding='utf-8') as f: f.write(ext)

if __name__ == "__main__":
    extract_local()
