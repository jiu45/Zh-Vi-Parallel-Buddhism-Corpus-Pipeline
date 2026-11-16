import sys, json
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')

with open(r'd:\CS\NLP\Mid-Term\metadata\viet_articles.json', 'r', encoding='utf-8') as f:
    viet_arts = json.load(f)

art2 = viet_arts[1]
print(f"Article 2 title: {art2['vi_title']}")
print(f"Article 2 paragraphs count: {len(art2['paragraphs'])}")
print(f"Article 2 sentences count: {len(art2['sentences'])}")
print("\nLast 3 sentences:")
for i, s in enumerate(art2['sentences'][-3:], len(art2['sentences'])-2):
    print(f"[{i}] {s}")
