import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf')
print("=== Page 365 dict ===")
for b in doc[364].get_text('blocks'):
    print(b)
print("=== Page 366 dict ===")
for b in doc[365].get_text('blocks'):
    print(b)
