import sys, io, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf")

with open(r"d:\CS\NLP\Mid-Term\metadata\anchor_map.json", 'r', encoding='utf-8') as f:
    anchor_map = json.load(f)

for a in anchor_map:
    pno = a['vi_start_page'] - 1
    page = doc[pno]
    blocks = page.get_text('dict')['blocks']
    lines = []
    for b in blocks:
        if 'lines' not in b: continue
        for l in b['lines']:
            if l['bbox'][1] < 75: continue
            spans = [s for s in l['spans'] if s['size'] >= 12.5]
            if not spans: continue
            txt = ''.join(s['text'] for s in spans).strip()
            if txt and txt not in ['IV. TỰ', 'V. BẠT']:
                lines.append((l, txt, spans[0]))
    
    # find title line
    for idx, (l, txt, s0) in enumerate(lines):
        m = re.match(r'^(\d+)\.\s*(.*)', txt)
        if m and int(m.group(1)) == a['article_num'] and s0['size'] >= 14.0 and (s0['flags'] & 16 or 'Bold' in s0['font']):
            # inspect following 1-3 lines
            for off in range(1, 4):
                if idx + off < len(lines):
                    nl, ntxt, ns0 = lines[idx + off]
                    if re.match(r'^\d+\.', ntxt): break
                    # check if italic (flags == 6) or in parentheses
                    if ns0['flags'] == 6 or (ntxt.startswith('(') and not ntxt.endswith(')')):
                        print(f"Article {a['global_id']} ({a['vi_title'][:30]}...): Line +{off} is subtitle/note: [flags={ns0['flags']}, x0={nl['bbox'][0]:.1f}]: {ntxt}")
