import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf")

def get_page_body_lines(pno):
    page = doc[pno]
    text_dict = page.get_text('dict')
    lines = []
    for b in text_dict['blocks']:
        if 'lines' not in b: continue
        for l in b['lines']:
            if l['bbox'][1] < 75: continue
            spans = [s for s in l['spans'] if s['size'] >= 12.5]
            if not spans: continue
            txt = ''.join(s['text'] for s in spans).strip()
            if txt and txt not in ['IV. TỰ', 'V. BẠT']:
                lines.append((l['bbox'], txt))
    return lines

for p in [5, 6, 7, 8]:
    lines = get_page_body_lines(p-1)
    print(f"=== PAGE {p} ===")
    print("  First line:", lines[0] if lines else "EMPTY")
    print("  Last line: ", lines[-1] if lines else "EMPTY")
