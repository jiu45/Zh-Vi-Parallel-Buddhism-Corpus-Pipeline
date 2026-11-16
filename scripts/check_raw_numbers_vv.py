import sys, io, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf")

# Let's inspect raw text from pymupdf before any clean_spacing
raw_full = ""
for pno in range(4, 358):
    p = doc[pno]
    td = p.get_text('dict')
    for b in td['blocks']:
        if 'lines' not in b: continue
        for l in b['lines']:
            if l['bbox'][1] < 75: continue
            spans = [s for s in l['spans'] if s['size'] >= 12.5]
            if not spans: continue
            txt = ''.join(s['text'] for s in spans).strip()
            raw_full += " " + txt

print("Numbers with dots in raw text:")
numbers = re.findall(r'\b\d+\.\d+\b', raw_full)
print(set(numbers))

print("\nOccurrences of v.v. in raw text:")
vv_matches = re.findall(r'.{0,30}v\.\s*v\.?.{0,30}', raw_full)
for m in vv_matches[:15]:
    print("  ", m.strip())
