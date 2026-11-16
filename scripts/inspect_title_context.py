import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf')

for pno in range(4, 358):
    page = doc[pno]
    blocks = page.get_text('dict')['blocks']
    lines = []
    for b in blocks:
        if 'lines' not in b:
            continue
        for l in b['lines']:
            if l['bbox'][1] < 75:
                continue
            txt = ''.join(s['text'] for s in l['spans']).strip()
            if txt and txt not in ['IV. TỰ', 'V. BẠT']:
                lines.append((l, txt))
    
    for idx, (l, txt) in enumerate(lines):
        m = re.match(r'^(\d+)\.\s*(.*)', txt)
        s0 = l['spans'][0]
        if m and s0['size'] >= 14.0 and (s0['flags'] & 16 or 'Bold' in s0['font']):
            # Print this line and the next 2 lines
            print(f"--- Article {txt[:40]} (Page {pno+1}) ---")
            for offset in range(1, 3):
                if idx + offset < len(lines):
                    next_l, next_txt = lines[idx + offset]
                    ns0 = next_l['spans'][0]
                    print(f"   Line +{offset}: [size={ns0['size']}, flags={ns0['flags']}, bbox_x0={next_l['bbox'][0]:.1f}, bbox_y0={next_l['bbox'][1]:.1f}] {next_txt[:60]}")
