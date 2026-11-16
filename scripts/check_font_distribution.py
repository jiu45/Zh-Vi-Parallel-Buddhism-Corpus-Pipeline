import sys, io
from collections import Counter
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf")

size_counter = Counter()

for pno in range(4, 358):
    page = doc[pno]
    text_dict = page.get_text('dict')
    for b in text_dict['blocks']:
        if 'lines' not in b: continue
        for l in b['lines']:
            if l['bbox'][1] < 75: continue # header
            for s in l['spans']:
                # round size to 1 decimal place
                size_counter[round(s['size'], 1)] += len(s['text'].strip())

print("Character counts by font size (excluding header y < 75):")
for sz, count in sorted(size_counter.items()):
    print(f"Size {sz:4.1f}: {count:7d} characters")
