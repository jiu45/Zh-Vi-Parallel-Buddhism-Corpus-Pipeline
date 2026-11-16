import os, sys, glob, re
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

raw_han_dir = r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\02_ocr_tho\han"

for pno in range(3, 15):
    fname = os.path.join(raw_han_dir, f"page_{pno:04d}.txt")
    with open(fname, "r", encoding="utf-8") as f:
        text = f.read()
    # Check for title-like lines ending with 序
    for l in text.splitlines():
        l_str = l.strip()
        if "序" in l_str and (l_str.endswith("序") or l_str.endswith("）") or l_str.endswith("代撰）")):
            if len(l_str) < 30:
                print(f"Page {pno:04d}: TITLE -> {l_str}")
