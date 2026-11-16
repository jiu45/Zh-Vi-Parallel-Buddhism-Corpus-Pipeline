import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf')
page = doc[330] # page 331
for b in page.get_text('dict')['blocks']:
    if 'lines' in b:
        for l in b['lines']:
            if l['bbox'][1] < 75: continue
            cleaned_spans = [s['text'] for s in l['spans'] if s['size'] >= 12.5]
            raw_spans = [s['text'] for s in l['spans']]
            cleaned_text = ''.join(cleaned_spans).strip()
            raw_text = ''.join(raw_spans).strip()
            if 'Quy Tâm Đường' in raw_text:
                print('RAW:    ', raw_text)
                print('CLEANED:', cleaned_text)
