import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf")

p1_lines = []
for pno in range(4, 8):
    p = doc[pno]
    td = p.get_text('dict')
    for b in td['blocks']:
        if 'lines' not in b: continue
        for l in b['lines']:
            if l['bbox'][1] < 75: continue
            spans = [s for s in l['spans'] if s['size'] >= 12.5]
            if not spans: continue
            txt = ''.join(s['text'] for s in spans).strip()
            if txt and txt not in ['IV. TỰ', 'V. BẠT']:
                p1_lines.append((pno+1, l['bbox'][0], l['bbox'][1], txt))

# Article 1 ends at line before "2. Lời tựa..."
art1_lines = []
for pno, x0, y0, txt in p1_lines:
    if txt.startswith('2. Lời tựa'):
        break
    if txt.startswith('1. Lời tựa'):
        continue
    art1_lines.append((pno, x0, y0, txt))

print(f"Article 1 has {len(art1_lines)} body lines.")
for pno, x0, y0, txt in art1_lines:
    if x0 > 85:
        print(f"[NEW PARA] (p.{pno}, x0={x0:.1f}, y0={y0:.1f}): {txt[:60]}")
