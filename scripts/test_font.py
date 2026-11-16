import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf')

for pno in range(4, 358):
    page = doc[pno]
    text = page.get_text('dict')
    for block in text['blocks']:
        if 'lines' not in block:
            continue
        for line in block['lines']:
            line_text = ''.join(s['text'] for s in line['spans']).strip()
            bbox = line['bbox']
            if bbox[1] < 75:
                continue
            m = re.match(r'^(\d+)\.\s+(.*)', line_text)
            if m:
                s0 = line['spans'][0]
                if s0['flags'] != 20 or s0['size'] < 14:
                    print(f'Page {pno+1}: font={s0["font"]}, size={s0["size"]}, flags={s0["flags"]}: {line_text[:50]}')
