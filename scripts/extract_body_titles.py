import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf')

# Let's inspect each of the 110 articles in the body
# An article starts with an article title.
# Let's see: on each page, we collect lines with size >= 12.5 (main text).
# Title lines have size = 15.0.
# Let's see how title lines are formatted in the body.

body_articles = []
current_section = 'TỰ'

for pno in range(4, 358): # 5 to 358
    page = doc[pno]
    blocks = page.get_text('dict')['blocks']
    for b in blocks:
        if 'lines' not in b:
            continue
        for l in b['lines']:
            if l['bbox'][1] < 75:
                continue
            line_text = ''.join(s['text'] for s in l['spans']).strip()
            if not line_text:
                continue
            if line_text == 'IV. TỰ':
                continue
            if line_text == 'V. BẠT':
                current_section = 'BẠT'
                continue
            
            s0 = l['spans'][0]
            # Check for title start
            m = re.match(r'^(\d+)\.\s*(.*)', line_text)
            if m and s0['size'] >= 14.0 and (s0['flags'] & 16 or 'Bold' in s0['font']):
                num = int(m.group(1))
                body_articles.append({
                    'global_id': len(body_articles) + 1,
                    'section': current_section,
                    'num': num,
                    'start_page': pno + 1,
                    'title_first_line': line_text,
                    'bbox': l['bbox']
                })

print(f"Total articles found: {len(body_articles)}")
# Now let's see for each article, does it have subsequent title lines?
