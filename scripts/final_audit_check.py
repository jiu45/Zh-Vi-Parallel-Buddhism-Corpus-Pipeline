import sys, json, re
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

with open(r'd:\CS\NLP\Mid-Term\metadata\viet_articles.json', 'r', encoding='utf-8') as f:
    articles = json.load(f)

# 1. Check article 39
a39 = articles[38]
print('=== ART 39 ===')
print('Title:', a39['vi_title'])
print('Para 0:', a39['paragraphs'][0][:80])

# 2. Check broken sentences ending with digits
broken = []
for a in articles:
    for idx, s in enumerate(a['sentences']):
        if re.search(r'\b(hơn|gần|khoảng|đến|là)\s+\d+\s*[.?!][”"\'\)\]]*$', s, re.IGNORECASE):
            broken.append((a['global_id'], idx, s))
print('Broken sentences ending with digits count:', len(broken))

# 3. Check v. v. and numbers with space
with open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\03_text_sach\viet.txt', 'r', encoding='utf-8') as f:
    txt = f.read()
vv_space = len(re.findall(r'\bv\.\s+v\.', txt))
print('v. v. with space count in viet.txt:', vv_space)
num_dot_space = len(re.findall(r'\b\d+\.\s+\d+\b', txt))
print('numbers with dot space (1. 300) count in viet.txt:', num_dot_space)
