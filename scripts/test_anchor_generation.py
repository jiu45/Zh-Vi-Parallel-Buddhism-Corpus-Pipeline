import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf')

body_articles = []
cur_section = 'TỰ'

for pno in range(4, 358):
    page = doc[pno]
    blocks = page.get_text('dict')['blocks']
    lines = []
    for b in blocks:
        if 'lines' not in b: continue
        for l in b['lines']:
            if l['bbox'][1] < 75: continue
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
            for offset in range(1, 4):
                if idx + offset < len(lines):
                    nl, ntxt, nspans = lines[idx + offset]
                    if ntxt in ['IV. TỰ', 'V. BẠT'] or re.match(r'^\d+\.', ntxt):
                        break
                    ns0 = nspans[0]
                    # Body paragraphs are indented (x0 > 85) with regular font (flags==4)
                    is_indented = nl['bbox'][0] > 85
                    if is_indented and ns0['flags'] == 4 and not (ns0['flags'] & 16):
                        break
                    title_lines.append(ntxt)
                else:
                    break
            full_title = ' '.join(title_lines)
            full_title = re.sub(r'\s+', ' ', full_title).strip()
            body_articles.append({
                'global_id': len(body_articles) + 1,
                'section': cur_section,
                'article_num': num,
                'vi_title': full_title,
                'vi_start_page': pno + 1,
                'idx_on_page': idx,
                'total_lines_on_page': len(lines)
            })

# Now calculate end_page for each article
for i in range(len(body_articles)):
    cur = body_articles[i]
    if i < len(body_articles) - 1:
        nxt = body_articles[i+1]
        if nxt['vi_start_page'] == cur['vi_start_page']:
            cur['vi_end_page'] = cur['vi_start_page']
        else:
            # Check if next article has preceding lines on its start page
            # If nxt starts after line 0 (meaning there was body text of cur on nxt's start page)
            if nxt['idx_on_page'] > 0:
                cur['vi_end_page'] = nxt['vi_start_page']
            else:
                cur['vi_end_page'] = nxt['vi_start_page'] - 1
    else:
        cur['vi_end_page'] = 358

print(f"Total processed: {len(body_articles)}")
for a in body_articles:
    print(f"{a['global_id']:3d}. [{a['section']:3s} {a['article_num']:2d}] (p.{a['vi_start_page']:3d}-{a['vi_end_page']:3d}): {a['vi_title']}")
