import os, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

raw_han_dir = r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\02_ocr_tho\han"
with open(os.path.join(raw_han_dir, "page_0010.txt"), "r", encoding="utf-8") as f:
    p10 = f.read().strip()
with open(os.path.join(raw_han_dir, "page_0011.txt"), "r", encoding="utf-8") as f:
    p11 = f.read().strip()

print("P10 end:\n", p10[-200:])
print("\nP11 start:\n", p11[:200])
