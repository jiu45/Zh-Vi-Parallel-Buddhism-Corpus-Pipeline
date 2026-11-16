import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open(r"d:\CS\NLP\Mid-Term\metadata\viet_articles.json", 'r', encoding='utf-8') as f:
    articles = json.load(f)

art4 = articles[3] # Article 4 (index 3)
for idx in range(3, 8):
    print(f"s{idx}: {art4['sentences'][idx]}")
