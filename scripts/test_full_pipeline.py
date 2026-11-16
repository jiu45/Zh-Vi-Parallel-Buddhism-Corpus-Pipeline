import sys, io, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf")

# Load anchor_map.json
with open(r"d:\CS\NLP\Mid-Term\metadata\anchor_map.json", 'r', encoding='utf-8') as f:
    anchor_map = json.load(f)

print(f"Loaded anchor map: {len(anchor_map)} articles.")
