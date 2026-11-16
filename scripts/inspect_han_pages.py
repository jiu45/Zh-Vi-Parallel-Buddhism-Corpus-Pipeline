import os, sys, glob
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

raw_han_dir = r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\02_ocr_tho\han"
files = sorted(glob.glob(os.path.join(raw_han_dir, "page_*.txt")))

for fpath in files:
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    print(f"=== {fname} ({len(lines)} lines) ===")
    print("  First 2 lines:", lines[:2])
    print("  Last 2 lines: ", lines[-2:])
