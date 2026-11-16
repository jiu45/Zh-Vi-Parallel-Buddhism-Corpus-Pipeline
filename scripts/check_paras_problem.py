import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open(r"d:\CS\NLP\Mid-Term\metadata\viet_articles.json", 'r', encoding='utf-8') as f:
    articles = json.load(f)

for gid in [25, 26, 39, 99]:
    art = articles[gid - 1]
    print(f"=== Article {gid}: {art['vi_title']} ===")
    print("  Paragraph 0:", art['paragraphs'][0][:100] if art['paragraphs'] else "EMPTY")
    print("  Paragraph 1:", art['paragraphs'][1][:100] if len(art['paragraphs']) > 1 else "NO PARA 1")
