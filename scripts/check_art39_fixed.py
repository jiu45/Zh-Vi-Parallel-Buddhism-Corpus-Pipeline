import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Run and inspect Article 39
from test_fixed_pipeline import articles

art39 = articles[38] # Article 39
print("=== ARTICLE 39 ===")
print("vi_title:", art39['vi_title'])
print("Total paragraphs:", len(art39['paragraphs']))
for i, p in enumerate(art39['paragraphs']):
    print(f"Para {i}: {p[:100]}...")
print("Total sentences:", len(art39['sentences']))
for i, s in enumerate(art39['sentences'][:5]):
    print(f"Sent {i}: {s}")
