import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf')
print("=== Page 355 lines ===")
p = doc[354]
for b in p.get_text('dict')['blocks']:
    if 'lines' in b:
        for l in b['lines']:
            if l['bbox'][1] < 75: continue
            txt = ''.join(s['text'] for s in l['spans'] if s['size'] >= 12.5).strip()
            if txt:
                print(f"y={l['bbox'][1]:.1f}: {txt}")
