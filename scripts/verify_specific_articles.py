# -*- coding: utf-8 -*-
import sys, io, re, json
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Let's inspect Article 4, 27, 39, 45, 47, 68 from test_fixed_pipeline directly
with open(r"d:\CS\NLP\Mid-Term\scripts\test_fixed_pipeline.py", "r", encoding="utf-8") as f:
    code = f.read()

# Execute code in clean namespace
ns = {}
exec(code, ns)

articles = ns['articles']

print("=== ARTICLE 39 INSPECTION ===")
a39 = articles[38]
print("Title:", a39['vi_title'])
print("Number of paragraphs:", len(a39['paragraphs']))
for i, p in enumerate(a39['paragraphs']):
    print(f"  Para {i}: {p[:120]}...")
print("Paragraph 0 starts with:", a39['paragraphs'][0][:60])

print("\n=== ARTICLE 4 (formerly cut at 1.300) ===")
a4 = articles[3]
for idx, s in enumerate(a4['sentences']):
    if "1.300" in s or "v.v." in s:
        print(f"  Sent {idx}: {s}")

print("\n=== ARTICLE 27 (formerly cut at 1.800) ===")
a27 = articles[26]
print("  Sent 0:", a27['sentences'][0])

print("\n=== ARTICLE 45 (formerly cut at 2.000) ===")
a45 = articles[44]
for s in a45['sentences']:
    if "2.000" in s:
        print("  Sent:", s)

print("\n=== ARTICLE 47 (formerly cut at 2.000) ===")
a47 = articles[46]
for s in a47['sentences']:
    if "2.000" in s:
        print("  Sent:", s)

print("\n=== ARTICLE 68 (formerly cut at 1.800 / v.v.) ===")
a68 = articles[67]
for s in a68['sentences']:
    if "v.v." in s or "1.800" in s:
        print("  Sent:", s)
