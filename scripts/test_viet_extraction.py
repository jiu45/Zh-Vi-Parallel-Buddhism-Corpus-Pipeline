# -*- coding: utf-8 -*-
"""
Prototype script to test Vietnamese text extraction, cleaning, and QA.
"""

import os
import sys
import io
import re
import json
import pymupdf

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

VI_PDF_PATH = r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf"
ANCHOR_MAP_PATH = r"d:\CS\NLP\Mid-Term\metadata\anchor_map.json"

def clean_spacing(text):
    """Normalize spaces and punctuation spacing."""
    # Collapse multiple whitespaces
    text = re.sub(r'[ \t\u00a0]+', ' ', text)
    # Remove space before punctuation
    text = re.sub(r'\s+([,.;:!?\)\]”"’\'])', r'\1', text)
    # Ensure space after punctuation if followed by a letter/number or opening quote
    text = re.sub(r'([,.;:!?])(?=[a-zA-ZÀ-ỹ0-9“"\'])', r'\1 ', text)
    # Remove space after opening quotes/brackets
    text = re.sub(r'([\(“"‘\[])\s+', r'\1', text)
    # Clean up double spaces created by substitutions
    text = re.sub(r'[ \t\u00a0]+', ' ', text)
    return text.strip()

def split_sentences_viet(text):
    """Split Vietnamese paragraph into sentences cleanly."""
    text = text.strip()
    if not text:
        return []
    
    # Protect abbreviations
    text = re.sub(r'\bv\.v\.', '@V_V@', text)
    text = re.sub(r'(\d+)\.(\d+)', r'\1@DOT@\2', text)
    
    # Sentence splitting pattern
    pattern = r'([.?!]+[”"\'\)\]]*)(?=\s+[A-ZÀ-Ỹ“"\'\(0-9]|$)'
    
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
        sent = sent.replace('@V_V@', 'v.v.').replace('@DOT@', '.')
        sent = clean_spacing(sent)
        if sent:
            sentences.append(sent)
            
    return sentences

def extract_and_parse_all():
    doc = pymupdf.open(VI_PDF_PATH)
    with open(ANCHOR_MAP_PATH, 'r', encoding='utf-8') as f:
        anchor_map = json.load(f)
    
    # Map (section, num) to anchor entry
    anchor_lookup = {(a['section'], a['article_num']): a for a in anchor_map}
    
    # Step 1: Collect all clean lines page by page
    # Each line: (pno, x0, y0, text, is_title_start, title_num, is_bold)
    all_pages_lines = []
    
    cur_section = 'TỰ'
    for pno in range(4, 358): # 5 to 358
        page = doc[pno]
        blocks = page.get_text('dict')['blocks']
        page_lines = []
        for b in blocks:
            if 'lines' not in b: continue
            for l in b['lines']:
                if l['bbox'][1] < 75: continue # header
                # Filter spans < 12.5 (removes footnotes and superscripts)
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
                    'is_bold': is_bold
                })
        all_pages_lines.append(page_lines)
    
    # Step 2: Assemble lines into articles and paragraphs
    articles = []
    cur_article = None
    cur_para_lines = []
    in_title = False
    
    # Flatten lines in document order
    flat_lines = [l for pl in all_pages_lines for l in pl]
    
    idx = 0
    while idx < len(flat_lines):
        line = flat_lines[idx]
        
        # Check if new article starts
        if line['is_title_start']:
            # Close previous paragraph and article
            if cur_para_lines:
                para_text = join_lines_to_para(cur_para_lines)
                if para_text and cur_article:
                    cur_article['paragraphs'].append(para_text)
                cur_para_lines = []
            
            # Start new article
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
            
            # Skip any title continuation lines
            in_title = True
            idx += 1
            while idx < len(flat_lines):
                nline = flat_lines[idx]
                if nline['is_title_start']:
                    break
                # Indented regular paragraph marks start of body
                if nline['x0'] > 85 and not nline['is_bold']:
                    in_title = False
                    break
                # If still title line, skip (title is already in anchor['vi_title'])
                idx += 1
            continue
        
        # Body lines
        if line['x0'] > 85: # Indented line: start of new paragraph
            if cur_para_lines:
                para_text = join_lines_to_para(cur_para_lines)
                if para_text and cur_article:
                    cur_article['paragraphs'].append(para_text)
                cur_para_lines = []
            cur_para_lines.append(line['text'])
        else: # Continuation line
            cur_para_lines.append(line['text'])
            
        idx += 1
        
    # Close last paragraph
    if cur_para_lines and cur_article:
        para_text = join_lines_to_para(cur_para_lines)
        if para_text:
            cur_article['paragraphs'].append(para_text)
            
    # Step 3: Sentence splitting for each article
    total_sentences = 0
    total_paragraphs = 0
    for art in articles:
        total_paragraphs += len(art['paragraphs'])
        for p in art['paragraphs']:
            sents = split_sentences_viet(p)
            art['sentences'].extend(sents)
        total_sentences += len(art['sentences'])
        
    print(f"Total articles: {len(articles)}")
    print(f"Total paragraphs: {total_paragraphs}")
    print(f"Total sentences: {total_sentences}")
    
    return articles

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

if __name__ == '__main__':
    articles = extract_and_parse_all()
    # Print sample
    print("--- Article 1 Sample ---")
    print("Title:", articles[0]['vi_title'])
    print("Paragraphs:", len(articles[0]['paragraphs']))
    print("Sentences:", len(articles[0]['sentences']))
    for i, s in enumerate(articles[0]['sentences'][:5]):
        print(f"  [{i+1}] {s}")
    print("--- Last Article Sample ---")
    print("Title:", articles[-1]['vi_title'])
    print("Paragraphs:", len(articles[-1]['paragraphs']))
    print("Sentences:", len(articles[-1]['sentences']))
    for i, s in enumerate(articles[-1]['sentences'][:5]):
        print(f"  [{i+1}] {s}")
