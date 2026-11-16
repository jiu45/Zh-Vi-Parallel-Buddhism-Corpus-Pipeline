import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf")

for pno in range(4, 358):
    page = doc[pno]
    text_dict = page.get_text('dict')
    lines = []
    for b in text_dict['blocks']:
        if 'lines' not in b: continue
        for l in b['lines']:
            if l['bbox'][1] < 75: continue
            spans = [s for s in l['spans'] if s['size'] >= 12.5]
            if not spans: continue
            txt = ''.join(s['text'] for s in spans).strip()
            if txt and txt not in ['IV. TỰ', 'V. BẠT']:
                lines.append(txt)
    
    for i in range(len(lines) - 1):
        l1 = lines[i]
        l2 = lines[i+1]
        if l1.endswith('-'):
            if l1.endswith(' -'):
                joined = l1 + ' ' + l2
            else:
                joined = l1 + l2
            print(f"p.{pno+1}: [{l1}] + [{l2}] --> [{joined[-40:]}]")
