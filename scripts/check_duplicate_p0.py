import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open(r"d:\CS\NLP\Mid-Term\metadata\viet_articles.json", 'r', encoding='utf-8') as f:
    articles = json.load(f)

for a in articles:
    if not a['paragraphs']: continue
    p0 = a['paragraphs'][0].strip()
    if p0 in a['vi_title']:
        print(f"Article {a['global_id']} has duplicate p0 in vi_title:")
        print("  vi_title:", a['vi_title'])
        print("  p0:      ", p0)
