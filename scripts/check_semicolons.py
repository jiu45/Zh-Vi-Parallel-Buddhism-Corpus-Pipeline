import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf")

semicolon_examples = []
for pno in range(4, 30):
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
            if txt:
                lines.append(txt)
    txt_page = ' '.join(lines)
    for m in re.finditer(r'[^.;!?]{10,50};[^.;!?]{10,50}', txt_page):
        semicolon_examples.append((pno+1, m.group(0)))

print(f"Total semicolon samples: {len(semicolon_examples)}")
for s in semicolon_examples[:10]:
    print(f"p.{s[0]}: {s[1]}")
