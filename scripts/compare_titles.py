import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf')

# 1. Parse TOC
toc_entries = []
for pno in range(358, 366):
    page = doc[pno]
    blocks = page.get_text('blocks')
    for b in blocks:
        if b[1] < 75: continue # skip header
        text = b[4].strip()
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for l in lines:
            if l in ['MỤC LỤC', 'IV. TỰ', 'V. BẠT', 'ẤN QUANG PHÁP SƯ VĂN SAO', 'TĂNG QUẢNG CHÁNH BIÊN - QUYỂN III']:
                continue
            toc_entries.append(l)

# Group TOC items
parsed_toc = []
cur_num = None
cur_title_parts = []
cur_section = 'TỰ'

for line in toc_entries:
    if line == 'V. BẠT':
        cur_section = 'BẠT'
        continue
    m = re.match(r'^(\d+)\.\s*(.*)', line)
    if m:
        if cur_num is not None:
            parsed_toc.append((cur_section, cur_num, ' '.join(cur_title_parts)))
        cur_num = int(m.group(1))
        cur_title_parts = []
        if cur_num == 1 and len(parsed_toc) >= 90:
            cur_section = 'BẠT'
        rest = m.group(2).strip()
        if rest: cur_title_parts.append(rest)
    else:
        if cur_num is not None:
            cur_title_parts.append(line)

if cur_num is not None:
    parsed_toc.append((cur_section, cur_num, ' '.join(cur_title_parts)))

# Extract TOC page and title
clean_toc = {}
for sec, num, raw in parsed_toc:
    raw = re.sub(r'\s+', ' ', raw).strip()
    m_p = re.search(r'\s+(\d+)$', raw)
    if m_p:
        p_no = int(m_p.group(1))
        t = raw[:m_p.start()].strip()
    else:
        p_no = None
        t = raw
    clean_toc[(sec, num)] = (f"{num}. {t}", p_no)

# 2. Extract body titles
# In body, let's see how title lines are structured:
body_titles = {}
cur_section = 'TỰ'

for pno in range(4, 358):
    page = doc[pno]
    blocks = page.get_text('dict')['blocks']
    lines = []
    for b in blocks:
        if 'lines' not in b: continue
        for l in b['lines']:
            if l['bbox'][1] < 75: continue
            # Only keep spans with size >= 12.5 to avoid footnote superscripts
            spans_clean = [s for s in l['spans'] if s['size'] >= 12.5]
            if not spans_clean: continue
            txt = ''.join(s['text'] for s in spans_clean).strip()
            if txt:
                lines.append((l, txt, spans_clean))
    
    for idx, (l, txt, spans) in enumerate(lines):
        if txt == 'IV. TỰ': continue
        if txt == 'V. BẠT':
            cur_section = 'BẠT'
            continue
        
        m = re.match(r'^(\d+)\.\s*(.*)', txt)
        s0 = spans[0]
        if m and s0['size'] >= 14.0 and (s0['flags'] & 16 or 'Bold' in s0['font']):
            num = int(m.group(1))
            title_lines = [txt]
            # check next lines on this page that belong to the title
            # A line is part of title if:
            # - It's bold OR italic/note OR
            # - Its x0 is unindented (~62 or ~70) and does not end with sentence period and is before the indented paragraph
            for offset in range(1, 4):
                if idx + offset < len(lines):
                    nl, ntxt, nspans = lines[idx + offset]
                    if ntxt in ['IV. TỰ', 'V. BẠT'] or re.match(r'^\d+\.', ntxt):
                        break
                    ns0 = nspans[0]
                    # Indented paragraph has bbox_x0 > 85 (even: ~90.7, odd: ~99.2)
                    is_indented = nl['bbox'][0] > 85
                    if is_indented and ns0['flags'] == 4 and not (ns0['flags'] & 16):
                        # This is regular body paragraph start
                        break
                    # Otherwise, if it's bold, italic (flags=6), or continuing title:
                    title_lines.append(ntxt)
                else:
                    break
            full_title = ' '.join(title_lines)
            full_title = re.sub(r'\s+', ' ', full_title).strip()
            body_titles[(cur_section, num)] = (full_title, pno + 1)

print(f"Clean TOC count: {len(clean_toc)}")
print(f"Body titles count: {len(body_titles)}")

# Compare body titles vs TOC
print("\n--- Differences or Comparison ---")
for key in sorted(body_titles.keys(), key=lambda x: (0 if x[0]=='TỰ' else 1, x[1])):
    b_t, b_p = body_titles[key]
    t_t, t_p = clean_toc.get(key, ('MISSING', None))
    if b_p != t_p or b_t != t_t:
        print(f"[{key[0]} {key[1]:2d}] Body (p.{b_p}): {b_t}")
        print(f"         TOC  (p.{t_p}): {t_t}")
