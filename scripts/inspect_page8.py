import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf")

for b in doc[7].get_text('dict')['blocks']:
    if 'lines' in b:
        for l in b['lines']:
            if l['bbox'][1] < 75: continue
            spans = [s for s in l['spans'] if s['size'] >= 12.5]
            if not spans: continue
            txt = ''.join(s['text'] for s in spans).strip()
            print(f"y={l['bbox'][1]:5.1f}, x0={l['bbox'][0]:5.1f}, flags={spans[0]['flags']}: {txt}")
