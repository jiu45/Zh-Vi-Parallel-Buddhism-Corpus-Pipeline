import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf")

in_between = []

for pno in range(4, 358):
    page = doc[pno]
    text_dict = page.get_text('dict')
    for b in text_dict['blocks']:
        if 'lines' not in b: continue
        for l in b['lines']:
            if l['bbox'][1] < 75: continue # header
            spans = [s for s in l['spans'] if s['size'] >= 12.5]
            if not spans: continue
            txt = ''.join(s['text'] for s in spans).strip()
            if not txt or txt in ['IV. TỰ', 'V. BẠT']: continue
            x0 = l['bbox'][0]
            if 75 <= x0 <= 85:
                in_between.append((pno + 1, x0, txt))

print(f"Lines with x0 between 75 and 85: {len(in_between)}")
for item in in_between[:10]:
    print(item)
