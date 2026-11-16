import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf')

toc_text = ""
for pno in range(358, 366): # pages 359 to 366 (1-indexed)
    toc_text += f"\n--- Page {pno+1} ---\n" + doc[pno].get_text()

print(toc_text[:2000])
