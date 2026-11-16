import sys, pymupdf
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')

doc = pymupdf.open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf')

verses = []
for pno in range(4, 358):
    p = doc[pno]
    for b in p.get_text('dict')['blocks']:
        if 'lines' in b:
            for l in b['lines']:
                if l['bbox'][1] < 75: continue
                spans = [s for s in l['spans'] if s['size'] >= 12.5]
                if not spans: continue
                txt = ''.join(s['text'] for s in spans).strip()
                if l['bbox'][0] > 120 and len(txt) < 40 and not txt.startswith('('):
                    verses.append((pno+1, l['bbox'][0], txt))

print(f"Total verse lines detected: {len(verses)}")
for v in verses[:20]:
    print(f"Page {v[0]}: (x0={v[1]:.1f}) {v[2]}")
