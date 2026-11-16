import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf')

# 1. Parse TOC
toc_raw = ""
for pno in range(358, 366): # pages 359 to 366
    toc_raw += doc[pno].get_text() + "\n"

# Clean header/footer in TOC
toc_lines = []
for line in toc_raw.splitlines():
    l = line.strip()
    if not l:
        continue
    if l in ['MỤC LỤC', 'IV. TỰ', 'V. BẠT', 'ẤN QUANG PHÁP SƯ VĂN SAO', 'TĂNG QUẢNG CHÁNH BIÊN - QUYỂN III']:
        continue
    # skip single numbers if they look like header page numbers at top (360, 361, etc.)
    toc_lines.append(l)

# Let's inspect parsing TOC entries
print(f"Total cleaned TOC lines: {len(toc_lines)}")
for l in toc_lines[:30]:
    print("  ", l)
