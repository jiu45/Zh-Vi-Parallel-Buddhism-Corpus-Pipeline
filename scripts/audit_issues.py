import sys, io, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf")

# 1. Inspect Article 39 (page 139)
print("=== ARTICLE 39 ON PAGE 139 ===")
p = doc[138] # page 139 (0-indexed 138)
for b in p.get_text('dict')['blocks']:
    if 'lines' in b:
        for l in b['lines']:
            if l['bbox'][1] < 75: continue
            spans = [s for s in l['spans'] if s['size'] >= 12.5]
            if not spans: continue
            txt = ''.join(s['text'] for s in spans).strip()
            s0 = spans[0]
            print(f"y={l['bbox'][1]:5.1f}, x0={l['bbox'][0]:5.1f}, font={s0['font']}, size={s0['size']}, flags={s0['flags']}: {txt}")

# 2. Check all sentences ending with a digit or period after digit in current viet_articles.json
with open(r"d:\CS\NLP\Mid-Term\metadata\viet_articles.json", 'r', encoding='utf-8') as f:
    articles = json.load(f)

cut_sentences = []
for a in articles:
    for idx, s in enumerate(a['sentences']):
        # If sentence ends with a digit followed by period or quote
        if re.search(r'\b\d+\s*[.?!][”"\'\)\]]*$', s):
            cut_sentences.append((a['global_id'], a['vi_title'], idx, s))

print(f"\nTotal sentences ending with digit+period in current viet_articles.json: {len(cut_sentences)}")
for c in cut_sentences:
    print(f"Bài {c[0]} (câu {c[2]}): {c[3]}")
