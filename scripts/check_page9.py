import os, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

with open(r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\02_ocr_tho\han\page_0009.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

print("=== PAGE 0009 LINES ===")
for i, l in enumerate(lines):
    print(f"[{i:2d}] {l.strip()}")
