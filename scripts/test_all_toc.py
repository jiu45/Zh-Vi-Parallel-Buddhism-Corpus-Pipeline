import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf')

all_toc_blocks = []
for pno in range(358, 366):
    page = doc[pno]
    for b in page.get_text('blocks'):
        text = b[4].strip()
        if text.startswith('MỤC LỤC') or 'ẤN QUANG PHÁP SƯ VĂN SAO' in text or 'TĂNG QUẢNG CHÁNH BIÊN' in text:
            continue
        all_toc_blocks.append(text)

full_toc_text = "\n".join(all_toc_blocks)
print(f"Full TOC text length: {len(full_toc_text)}")
# Let's inspect splitting by article numbers
items = re.split(r'\n(?=(\d+)\.\s+)', full_toc_text)
print(f"Items count after regex split: {len(items)}")
