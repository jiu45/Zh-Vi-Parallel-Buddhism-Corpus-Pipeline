import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf')

# Check start page and whether previous article text is present before the title on that page
articles = []
current_section = 'TỰ'

for pno in range(4, 358):
    page = doc[pno]
    blocks = page.get_text('dict')['blocks']
    lines = []
    for b in blocks:
        if 'lines' not in b: continue
        for l in b['lines']:
            if l['bbox'][1] < 75: continue
            txt = ''.join(s['text'] for s in l['spans'] if s['size'] >= 12.5).strip()
            if txt:
                lines.append((l, txt))
    
    for idx, (l, txt) in enumerate(lines):
        if txt in ['IV. TỰ', 'V. BẠT']:
            if txt == 'V. BẠT': current_section = 'BẠT'
            continue
        m = re.match(r'^(\d+)\.\s*(.*)', txt)
        s0 = l['spans'][0]
        if m and s0['size'] >= 14.0 and (s0['flags'] & 16 or 'Bold' in s0['font']):
            num = int(m.group(1))
            # Has preceding lines on this page?
            has_preceding_text = False
            preceding_lines = []
            for prev_l, prev_txt in lines[:idx]:
                if prev_txt not in ['IV. TỰ', 'V. BẠT']:
                    has_preceding_text = True
                    preceding_lines.append(prev_txt)
            articles.append({
                'section': current_section,
                'num': num,
                'start_page': pno + 1,
                'has_preceding': has_preceding_text,
                'preceding_count': len(preceding_lines)
            })

for i in range(len(articles)):
    cur = articles[i]
    if i < len(articles) - 1:
        nxt = articles[i+1]
        if nxt['start_page'] == cur['start_page']:
            end_page = cur['start_page']
        elif nxt['has_preceding']:
            end_page = nxt['start_page']
        else:
            end_page = nxt['start_page'] - 1
    else:
        end_page = 358
    cur['end_page'] = end_page

print(f"Total articles: {len(articles)}")
for a in articles[:10]:
    print(f"[{a['section']} {a['num']:2d}] Start: {a['start_page']:3d}, End: {a['end_page']:3d}, Next has preceding: {a['has_preceding']}")
print("...")
for a in articles[-10:]:
    print(f"[{a['section']} {a['num']:2d}] Start: {a['start_page']:3d}, End: {a['end_page']:3d}, Next has preceding: {a['has_preceding']}")
