import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf')
page = doc[22] # page 23
for b in page.get_text('dict')['blocks']:
    if 'lines' in b:
        for l in b['lines']:
            txt = ''.join(s['text'] for s in l['spans']).strip()
            s0 = l['spans'][0]
            if s0['size'] >= 12.0:
                print(f"{s0['size']} | flags={s0['flags']} | bbox={l['bbox']} | {txt}")
