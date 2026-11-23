# -*- coding: utf-8 -*-
"""
Phase 2: Raw Extraction & Complete Cleaning of Vietnamese Text
- Step 2.1: Extract raw text of all 368 pages to 02_ocr_tho/viet/page_XXXX.txt
- Step 2.2: Extract & clean main body (Pages 5 to 358) using font size & coordinates
- Step 2.3: Structure into 110 articles in metadata/viet_articles.json & 03_text_sach/viet.txt
- Step 2.4: Automated QA and verification
"""

import os
import sys
import io
import re
import json
from pathlib import Path
import pymupdf

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Dynamic project paths
BASE_DIR = Path(__file__).resolve().parent.parent
BOOK_DIR = BASE_DIR / os.environ.get("BOOK_DIR_NAME", "CV09_AQPSVS_Q3")
METADATA_DIR = BASE_DIR / "metadata"

VI_PDF_PATH = os.environ.get("VI_PDF_PATH", str(BOOK_DIR / "01_nguon" / "viet" / "Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf"))
RAW_VIET_DIR = os.environ.get("RAW_VIET_DIR", str(BOOK_DIR / "02_ocr_tho" / "viet"))
ANCHOR_MAP_PATH = os.environ.get("ANCHOR_MAP_PATH", str(METADATA_DIR / "anchor_map.json"))
VIET_ARTICLES_JSON = os.environ.get("VIET_ARTICLES_JSON", str(METADATA_DIR / "viet_articles.json"))
CLEAN_VIET_TXT = os.environ.get("CLEAN_VIET_TXT", str(BOOK_DIR / "03_text_sach" / "viet.txt"))

def step2_1_extract_raw_pages(doc):
    """Step 2.1: Extract raw text of all 368 pages into 02_ocr_tho/viet/page_XXXX.txt."""
    print("--- Bước 2.1: Trích xuất thô 368 trang tiếng Việt ---")
    os.makedirs(RAW_VIET_DIR, exist_ok=True)
    total_pages = len(doc)
    for pno in range(total_pages):
        page = doc[pno]
        raw_text = page.get_text("text")
        out_path = os.path.join(RAW_VIET_DIR, f"page_{pno + 1:04d}.txt")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(raw_text)
    print(f"-> Đã lưu thành công {total_pages} file thô vào {RAW_VIET_DIR}")

def clean_spacing(text):
    """Normalize whitespace and punctuation spacing, protecting numbers and abbreviations."""
    text = re.sub(r'[ \t\u00a0]+', ' ', text)
    # Normalize v.v. and v.v..
    text = re.sub(r'\bv\.\s*v\.\s*\.', 'v.v..', text)
    text = re.sub(r'\bv\.\s*v\.', 'v.v.', text)
    # Remove space before punctuation
    text = re.sub(r'\s+([,.;:!?\)\]”"’\'])', r'\1', text)
    # Comma spacing: only when followed by letter or quote, not between digits
    text = re.sub(r',(?=[a-zA-ZÀ-ỹ“"\'])', ', ', text)
    # Period spacing: only when followed by uppercase letter or quote/bracket, NOT digit or lowercase
    text = re.sub(r'(?<!\d)\.(?=[A-ZÀ-Ỹ“"\'\(\[])', '. ', text)
    # Semicolon spacing
    text = re.sub(r';(?=[a-zA-ZÀ-ỹ0-9“"\'])', '; ', text)
    # Colon spacing (not between digits)
    text = re.sub(r':(?=[a-zA-ZÀ-ỹ“"\'])', ': ', text)
    # Exclamation and question mark
    text = re.sub(r'([!?])(?=[a-zA-ZÀ-ỹ0-9“"\'])', r'\1 ', text)
    # Remove space after opening quotes/brackets
    text = re.sub(r'([\(“"‘\[])\s+', r'\1', text)
    # Re-normalize v.v.
    text = re.sub(r'\bv\.\s*v\.', 'v.v.', text)
    text = re.sub(r'[ \t\u00a0]+', ' ', text)
    return text.strip()

def split_sentences_viet(text):
    """Split Vietnamese paragraph into clean sentences, protecting decimal/thousand numbers, v.v., and verse lines."""
    text = text.strip()
    if not text:
        return []
    
    # 1. Protect numbers with dots (e.g. 1.300, 1.800, 2.000, 1.600)
    text = re.sub(r'(\d+)\.(\d+)', r'\1@NUMDOT@\2', text)
    
    # 2. Protect v.v. inside sentence (followed by lowercase, comma, semicolon, or closing quote+lowercase)
    text = re.sub(r'\bv\.v\.(?=\s+[a-zà-ỹ])', '@VV_LOWER@', text)
    text = re.sub(r'\bv\.v\.(?=,)', '@VV_COMMA@', text)
    text = re.sub(r'\bv\.v\.(?=;)', '@VV_SEMI@', text)
    text = re.sub(r'\bv\.v\.(?=\s*[\)\]”"’\']\s+[a-zà-ỹ])', '@VV_CLOSE_LOWER@', text)
    
    # 3. Handle double-dot v.v.. at end of sentence
    text = re.sub(r'\bv\.v\.\.', '@VV_END@.', text)
    
    # Sentence splitting pattern: punctuation followed by uppercase or quote, or end of string (NO \d in lookahead)
    pattern = r'([.?!]+[”"\'\)\]]*)(?=\s+[A-ZÀ-Ỹ“"\'\(]|$)'
    parts = re.split(pattern, text)
    sentences = []
    i = 0
    while i < len(parts):
        chunk = parts[i].strip()
        if not chunk:
            i += 1
            continue
        punct = ""
        if i + 1 < len(parts):
            punct = parts[i+1].strip()
            i += 2
        else:
            i += 1
        
        sent = (chunk + (" " + punct if punct and not chunk.endswith(punct) else punct)).strip()
        # Restore protected tokens
        sent = sent.replace('@NUMDOT@', '.')
        sent = sent.replace('@VV_LOWER@', 'v.v.')
        sent = sent.replace('@VV_COMMA@', 'v.v.')
        sent = sent.replace('@VV_SEMI@', 'v.v.')
        sent = sent.replace('@VV_CLOSE_LOWER@', 'v.v.')
        sent = sent.replace('@VV_END@', 'v.v.')
        sent = clean_spacing(sent)
        if sent:
            sentences.append(sent)
            
    return sentences

def join_lines_to_para(lines):
    """Join physical lines in paragraph, respecting hyphenation."""
    if not lines:
        return ""
    result = lines[0].strip()
    for l in lines[1:]:
        l_str = l.strip()
        if not l_str:
            continue
        if result.endswith('-'):
            if result.endswith(' -'):
                result = result + ' ' + l_str
            else:
                result = result + l_str
        else:
            result = result + ' ' + l_str
    return clean_spacing(result)

def step2_2_and_2_3_clean_and_structure(doc):
    """Step 2.2 & 2.3: Clean main text and structure into 110 articles."""
    print("--- Bước 2.2 & 2.3: Làm sạch và cấu trúc 110 bài văn tiếng Việt ---")
    
    with open(ANCHOR_MAP_PATH, 'r', encoding='utf-8') as f:
        anchor_map = json.load(f)
    anchor_lookup = {(a['section'], a['article_num']): a for a in anchor_map}
    
    # Collect clean lines across pages 5 to 358 (1-indexed)
    all_pages_lines = []
    cur_section = 'TỰ'
    for pno in range(4, 358):
        page = doc[pno]
        blocks = page.get_text('dict')['blocks']
        page_lines = []
        for b in blocks:
            if 'lines' not in b:
                continue
            for l in b['lines']:
                if l['bbox'][1] < 75:  # skip header
                    continue
                # Skip footnote spans and superscript index numbers (size < 12.5)
                spans = [s for s in l['spans'] if s['size'] >= 12.5]
                if not spans:
                    continue
                txt = ''.join(s['text'] for s in spans).strip()
                if not txt:
                    continue
                if txt == 'IV. TỰ':
                    continue
                if txt == 'V. BẠT':
                    cur_section = 'BẠT'
                    continue
                
                s0 = spans[0]
                is_bold = bool(s0['flags'] & 16 or 'Bold' in s0['font'])
                m = re.match(r'^(\d+)\.\s*(.*)', txt)
                is_title = bool(m and s0['size'] >= 14.0 and is_bold)
                num = int(m.group(1)) if is_title else None
                
                page_lines.append({
                    'pno': pno + 1,
                    'x0': l['bbox'][0],
                    'y0': l['bbox'][1],
                    'text': txt,
                    'is_title_start': is_title,
                    'title_num': num,
                    'section': cur_section,
                    'is_bold': is_bold,
                    'flags': s0['flags']
                })
        all_pages_lines.append(page_lines)
        
    flat_lines = [l for pl in all_pages_lines for l in pl]
    
    articles = []
    cur_article = None
    cur_para_lines = []
    
    idx = 0
    while idx < len(flat_lines):
        line = flat_lines[idx]
        
        if line['is_title_start']:
            # Close previous paragraph and article
            if cur_para_lines:
                para_text = join_lines_to_para(cur_para_lines)
                if para_text and cur_article:
                    cur_article['paragraphs'].append(para_text)
                cur_para_lines = []
                
            sec = line['section']
            num = line['title_num']
            anchor = anchor_lookup[(sec, num)]
            cur_article = {
                'global_id': anchor['global_id'],
                'section': sec,
                'article_num': num,
                'vi_title': anchor['vi_title'],
                'vi_start_page': anchor['vi_start_page'],
                'vi_end_page': anchor['vi_end_page'],
                'paragraphs': [],
                'sentences': []
            }
            articles.append(cur_article)
            
            # Skip title and subtitle lines
            idx += 1
            while idx < len(flat_lines):
                nline = flat_lines[idx]
                if nline['is_title_start']:
                    break
                # If line is part of vi_title, skip
                if nline['text'].strip() in anchor['vi_title']:
                    idx += 1
                    continue
                # Indented regular paragraph marks start of body text (x0 > 85, flags == 4)
                if nline['x0'] > 85 and nline['flags'] == 4:
                    break
                # If italic subtitle or in parentheses that matches vi_title
                if nline['flags'] == 6 or nline['text'].startswith('('):
                    if nline['text'].strip('()') in anchor['vi_title']:
                        idx += 1
                        continue
                idx += 1
            continue
            
        # Check for verse lines (kệ/tụng/thơ indented > 130 and len < 60)
        is_verse = (line['x0'] > 130 and len(line['text']) < 60 and not line['is_bold'])
        if is_verse:
            if cur_para_lines:
                para_text = join_lines_to_para(cur_para_lines)
                if para_text and cur_article:
                    cur_article['paragraphs'].append(para_text)
                cur_para_lines = []
            cur_article['paragraphs'].append(clean_spacing(line['text']))
            idx += 1
            continue

        if line['x0'] > 85 and line['flags'] == 4:  # Indented regular line: start of new paragraph
            if cur_para_lines:
                para_text = join_lines_to_para(cur_para_lines)
                if para_text and cur_article:
                    cur_article['paragraphs'].append(para_text)
                cur_para_lines = []
            cur_para_lines.append(line['text'])
        else:  # Continuation line within paragraph
            cur_para_lines.append(line['text'])
            
        idx += 1
        
    # Close last paragraph
    if cur_para_lines and cur_article:
        para_text = join_lines_to_para(cur_para_lines)
        if para_text:
            cur_article['paragraphs'].append(para_text)
            
    # Post-processing: Remove any duplicate subtitle in paragraphs that is already part of vi_title
    for art in articles:
        cleaned_paras = []
        for p in art['paragraphs']:
            p_clean = clean_spacing(p)
            # Remove duplicate subtitle if identical or wrapped in parentheses in vi_title
            if p_clean in art['vi_title'] or p_clean.strip('()') in art['vi_title']:
                print(f"-> Đã loại bỏ dòng phụ đề trùng lặp trong Bài {art['global_id']}: '{p_clean}'")
                continue
            cleaned_paras.append(p_clean)
        art['paragraphs'] = cleaned_paras
        
        art['sentences'] = []
        for p in art['paragraphs']:
            sents = split_sentences_viet(p)
            art['sentences'].extend(sents)
        
    total_paragraphs = sum(len(a['paragraphs']) for a in articles)
    total_sentences = sum(len(a['sentences']) for a in articles)
    print(f"-> Tổng số bài trích xuất: {len(articles)}")
    print(f"-> Tổng số đoạn văn sạch: {total_paragraphs}")
    print(f"-> Tổng số câu sạch: {total_sentences}")
    
    # Save viet_articles.json
    os.makedirs(os.path.dirname(VIET_ARTICLES_JSON), exist_ok=True)
    with open(VIET_ARTICLES_JSON, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"-> Đã lưu cấu trúc chi tiết 110 bài vào {VIET_ARTICLES_JSON}")
    
    # Save 03_text_sach/viet.txt
    os.makedirs(os.path.dirname(CLEAN_VIET_TXT), exist_ok=True)
    with open(CLEAN_VIET_TXT, 'w', encoding='utf-8') as f:
        for a_idx, art in enumerate(articles):
            if art['global_id'] == 1:
                f.write("IV. TỰ\n\n")
            elif art['global_id'] == 97:
                f.write("V. BẠT\n\n")
            f.write(f"{art['vi_title']}\n\n")
            for para in art['paragraphs']:
                f.write(f"{para}\n\n")
            if a_idx < len(articles) - 1:
                f.write("\n")
    print(f"-> Đã lưu văn bản sạch hoàn chỉnh vào {CLEAN_VIET_TXT}")
    
    return articles

def step2_4_automated_qa(articles):
    """Step 2.4: Automated QA and verification checks."""
    print("--- Bước 2.4: Kiểm tra chất lượng tự động (QA) ---")
    
    # QA 1: Count and article validity
    assert len(articles) == 110, f"Lỗi: Số bài là {len(articles)}, không phải 110!"
    tu_count = sum(1 for a in articles if a['section'] == 'TỰ')
    bat_count = sum(1 for a in articles if a['section'] == 'BẠT')
    assert tu_count == 96, f"Lỗi: Số bài TỰ là {tu_count}, không phải 96!"
    assert bat_count == 14, f"Lỗi: Số bài BẠT là {bat_count}, không phải 14!"
    
    empty_arts = [a['global_id'] for a in articles if len(a['paragraphs']) == 0]
    assert len(empty_arts) == 0, f"Lỗi: Có bài rỗng: {empty_arts}"
    min_sentences = min(len(a['sentences']) for a in articles)
    print(f"  [QA 1] Đạt: Đúng 110 bài (96 TỰ + 14 BẠT). Không có bài rỗng. Min câu/bài = {min_sentences}.")
    
    # QA 2: Superscript footnote attachment
    footnote_hits = []
    for a in articles:
        for s in a['sentences']:
            matches = re.findall(r'\b([a-zA-ZÀ-ỹ]+)(\d+)\b', s)
            if matches:
                footnote_hits.append((a['global_id'], matches))
    assert len(footnote_hits) == 0, f"Lỗi: Phát hiện số chú thích sót: {footnote_hits}"
    print("  [QA 2] Đạt tuyệt đối: 0% số chú thích sót (không còn chữ dính số [a-zA-ZÀ-ỹ]+\\d+).")
    
    # QA 3: Header leakage
    header_hits = []
    for a in articles:
        for p in a['paragraphs']:
            if 'ẤN QUANG PHÁP SƯ VĂN SAO' in p or 'TĂNG QUẢNG CHÁNH BIÊN' in p:
                header_hits.append(a['global_id'])
    assert len(header_hits) == 0, f"Lỗi: Phát hiện dòng header lọt vào chính văn: {header_hits}"
    print("  [QA 3] Đạt tuyệt đối: 0% dòng header lọt vào văn bản sạch.")
    
    # QA 4: Broken numbers check (e.g. "đã hơn 1.", "hơn 2.", "gần 2.")
    broken_number_sents = []
    for a in articles:
        for s in a['sentences']:
            if re.search(r'\b(hơn|gần|khoảng|đến|là)\s+\d+\s*[.?!][”"\'\)\]]*$', s, re.IGNORECASE):
                broken_number_sents.append((a['global_id'], s))
    assert len(broken_number_sents) == 0, f"Lỗi: Phát hiện câu bị cắt cụt ở số: {broken_number_sents}"
    print("  [QA 4] Đạt tuyệt đối: 0 câu bị cắt cụt ở số hàng nghìn (1.300, 1.800, 2.000).")
    
    # QA 5: Duplicate subtitle check in Article 39
    a39 = articles[38]
    assert not any(p.strip() == "(Phần này thuộc phần dẫn khởi, phần sau tường thuật sự việc nên không sao lục)" for p in a39['paragraphs']), "Lỗi: Bài 39 vẫn bị lặp dòng phụ đề!"
    print("  [QA 5] Đạt: Dòng phụ đề Bài 39 đã được loại bỏ hoàn toàn khỏi paragraphs.")

    # QA 6: Verse splitting in Article 2
    a2 = articles[1]
    expected_verses = [
        "Người thấy nghe, tùy hỷ,",
        "Đều phát tâm Bồ-đề,",
        "Hết một báo thân này,",
        "Cùng sanh cõi Cực Lạc."
    ]
    for v in expected_verses:
        assert v in a2['sentences'], f"Lỗi: Thiếu câu kệ '{v}' trong Bài 2!"
    print("  [QA 6] Đạt: 4 câu kệ cuối Bài 2 đã được tách riêng rẽ hoàn hảo.")
    
    # QA 7: Check file existence and size
    assert os.path.exists(CLEAN_VIET_TXT), "Lỗi: Không tìm thấy viet.txt!"
    txt_size = os.path.getsize(CLEAN_VIET_TXT)
    assert txt_size > 400000, f"Lỗi: Dung lượng viet.txt bất thường: {txt_size} bytes"
    print(f"  [QA 7] Đạt: File 03_text_sach/viet.txt tồn tại hợp lệ ({txt_size:,} bytes).")
    
    print("=== TOÀN BỘ CÁC HẠNG MỤC QA ĐÃ ĐẠT 100% TIÊU CHUẨN TUYỆT ĐỐI ===")

def main():
    print("=== BẮT ĐẦU GIAI ĐOẠN 2: TRÍCH XUẤT THÔ & LÀM SẠCH BẢN TIẾNG VIỆT (BẢN FIX KỆ BÀI 2) ===")
    doc = pymupdf.open(VI_PDF_PATH)
    print(f"Đã mở PDF: {VI_PDF_PATH} ({len(doc)} trang)")
    
    step2_1_extract_raw_pages(doc)
    articles = step2_2_and_2_3_clean_and_structure(doc)
    step2_4_automated_qa(articles)
    print("=== GIAI ĐOẠN 2 HOÀN TẤT THÀNH CÔNG RỰC RỠ ===")

if __name__ == '__main__':
    main()
