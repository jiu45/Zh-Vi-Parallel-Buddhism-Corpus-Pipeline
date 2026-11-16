import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open(r"d:\CS\NLP\Mid-Term\metadata\viet_articles.json", 'r', encoding='utf-8') as f:
    articles = json.load(f)

for a in articles:
    if not a['paragraphs']: continue
    p0 = a['paragraphs'][0]
    if p0.startswith('(') and p0.endswith(')'):
        print(f"Article {a['global_id']} ({a['vi_title']}): Para 0 is parenthesized: {p0}")
