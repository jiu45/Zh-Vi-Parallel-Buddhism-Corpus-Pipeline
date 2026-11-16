import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf")

# Extract all paragraphs and test sentence splitting
from test_viet_extraction import extract_and_parse_all

# Let's inspect all sentences in current viet_articles.json containing v.v. or v. v.
import json
with open(r"d:\CS\NLP\Mid-Term\metadata\viet_articles.json", 'r', encoding='utf-8') as f:
    articles = json.load(f)

for a in articles:
    for idx, s in enumerate(a['sentences']):
        if re.search(r'\bv\.\s*v\.', s):
            print(f"Art {a['global_id']} [s{idx}]: {s}")
