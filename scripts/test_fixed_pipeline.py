# -*- coding: utf-8 -*-
import sys, io, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

VI_PDF_PATH = r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf"
ANCHOR_MAP_PATH = r"d:\CS\NLP\Mid-Term\metadata\anchor_map.json"

def clean_spacing(text):
    """Normalize whitespace and punctuation spacing."""
    text = re.sub(r'[ \t\u00a0]+', ' ', text)
    # Normalize v.v.
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
    text = text.strip()
    if not text:
        return []
    
    # 1. Protect numbers with dots (e.g. 1.300, 2.000)
    text = re.sub(r'(\d+)\.(\d+)', r'\1@NUMDOT@\2', text)
    
    # 2. Protect v.v. inside sentence (followed by lowercase, comma, semicolon, or closing quote+lowercase)
    text = re.sub(r'\bv\.v\.(?=\s+[a-zà-ỹ])', '@VV_LOWER@', text)
    text = re.sub(r'\bv\.v\.(?=,)', '@VV_COMMA@', text)
    text = re.sub(r'\bv\.v\.(?=;)', '@VV_SEMI@', text)
    text = re.sub(r'\bv\.v\.(?=\s*[\)\]”"’\']\s+[a-zà-ỹ])', '@VV_CLOSE_LOWER@', text)
    
    # 3. Handle double-dot v.v.. at end of sentence
    text = re.sub(r'\bv\.v\.\.', '@VV_END@.', text)
    
    # Sentence splitting pattern: punctuation followed by uppercase or quote, or end of string
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

doc = pymupdf.open(VI_PDF_PATH)
with open(ANCHOR_MAP_PATH, 'r', encoding='utf-8') as f:
    anchor_map = json.load(f)
anchor_lookup = {(a['section'], a['article_num']): a for a in anchor_map}

all_pages_lines = []
cur_section = 'TỰ'
for pno in range(4, 358):
    page = doc[pno]
    blocks = page.get_text('dict')['blocks']
    page_lines = []
    for b in blocks:
        if 'lines' not in b: continue
        for l in b['lines']:
            if l['bbox'][1] < 75: continue
            spans = [s for s in l['spans'] if s['size'] >= 12.5]
            if not spans: continue
            txt = ''.join(s['text'] for s in spans).strip()
            if not txt: continue
            if txt == 'IV. TỰ': continue
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
        
        # Skip title lines
        idx += 1
        while idx < len(flat_lines):
            nline = flat_lines[idx]
            if nline['is_title_start']:
                break
            # If line text is already inside vi_title, skip
            if nline['text'].strip() in anchor['vi_title']:
                idx += 1
                continue
            # Body paragraph starts when x0 > 85 and flags == 4
            if nline['x0'] > 85 and nline['flags'] == 4:
                break
            # If italic or subtitle line
            if nline['flags'] == 6 or nline['text'].startswith('('):
                if nline['text'].strip('()') in anchor['vi_title']:
                    idx += 1
                    continue
            idx += 1
        continue
        
    if line['x0'] > 85 and line['flags'] == 4:
        if cur_para_lines:
            para_text = join_lines_to_para(cur_para_lines)
            if para_text and cur_article:
                cur_article['paragraphs'].append(para_text)
            cur_para_lines = []
        cur_para_lines.append(line['text'])
    else:
        cur_para_lines.append(line['text'])
        
    idx += 1

if cur_para_lines and cur_article:
    para_text = join_lines_to_para(cur_para_lines)
    if para_text:
        cur_article['paragraphs'].append(para_text)

# Post-processing: Remove any duplicate subtitle in paragraphs that is already part of vi_title
for art in articles:
    cleaned_paras = []
    for p in art['paragraphs']:
        p_clean = clean_spacing(p)
        # Check if paragraph is identical to or contained in vi_title
        if p_clean in art['vi_title'] or p_clean.strip('()') in art['vi_title']:
            print(f"-> Đã loại bỏ dòng phụ đề trùng lặp trong Bài {art['global_id']}: '{p_clean}'")
            continue
        cleaned_paras.append(p_clean)
    art['paragraphs'] = cleaned_paras
    
    art['sentences'] = []
    for p in art['paragraphs']:
        sents = split_sentences_viet(p)
        art['sentences'].extend(sents)

print("\n--- KIỂM TRA CÂU KẾT THÚC BẰNG SỐ+CHẤM (\\d+\\.$) ---")
cut_sents = []
for art in articles:
    for idx, s in enumerate(art['sentences']):
        # Match broken number at end of sentence: e.g., "đã hơn 1.", "hơn 2.", "gần 2."
        if re.search(r'\b(hơn|gần|khoảng|đến|là)\s+\d+\s*[.?!][”"\'\)\]]*$', s, re.IGNORECASE):
            cut_sents.append((art['global_id'], idx, s))

print(f"Tổng số câu bị cắt cụt ở số: {len(cut_sents)}")
for c in cut_sents:
    print(f"  Bài {c[0]} [câu {c[1]}]: {c[2]}")

print("\nTotal articles:", len(articles))
print("Total paragraphs:", sum(len(a['paragraphs']) for a in articles))
print("Total sentences:", sum(len(a['sentences']) for a in articles))
