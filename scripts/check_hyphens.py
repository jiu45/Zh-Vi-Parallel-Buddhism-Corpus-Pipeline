import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf")

hyphen_lines = []
for pno in range(4, 358):
    page = doc[pno]
    text_dict = page.get_text('dict')
    for b in text_dict['blocks']:
        if 'lines' not in b: continue
        for l in b['lines']:
            if l['bbox'][1] < 75: continue
            spans = [s for s in l['spans'] if s['size'] >= 12.5]
            if not spans: continue
            txt = ''.join(s['text'] for s in spans).strip()
            if txt.endswith('-'):
                hyphen_lines.append((pno + 1, txt))

print(f"Total lines ending with '-': {len(hyphen_lines)}")
for item in hyphen_lines[:20]:
    print(item)
