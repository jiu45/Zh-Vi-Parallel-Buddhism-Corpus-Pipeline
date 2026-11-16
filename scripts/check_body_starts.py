import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf')

# Let's find every article's start page and full title in the body
articles = []
current_section = 'TỰ'

for pno in range(4, 358): # pages 5 to 358 (1-indexed)
    page = doc[pno]
    blocks = page.get_text('dict')['blocks']
    for b_idx, block in enumerate(blocks):
        if 'lines' not in block:
            continue
        for l_idx, line in enumerate(block['lines']):
            line_text = ''.join(s['text'] for s in line['spans']).strip()
            bbox = line['bbox']
            if bbox[1] < 75: # skip header
                continue
            if line_text == 'V. BẠT':
                current_section = 'BẠT'
                continue
            
            # Check if this line is an article title
            s0 = line['spans'][0]
            # Must be bold and size >= 14
            if s0['size'] >= 14.0 and (s0['flags'] & 16 or 'Bold' in s0['font']):
                m = re.match(r'^(\d+)\.\s*(.*)', line_text)
                if m:
                    art_num = int(m.group(1))
                    title_lines = [line_text]
                    
                    # Look ahead for remaining lines of this title
                    # Titles may continue in same block or next block before any body text
                    # In body text, normal lines have s0['flags'] == 4 (regular) and indent or normal text
                    # But wait, earlier we saw page 23: title line 2 had flags=4!
                    # Let's see how many lines follow that belong to the title.
                    articles.append({
                        'section': current_section,
                        'num': art_num,
                        'page': pno + 1,
                        'b_idx': b_idx,
                        'l_idx': l_idx,
                        'raw_title_line': line_text
                    })

print(f"Total detected in body: {len(articles)}")
for i, a in enumerate(articles):
    if i < len(articles) - 1:
        next_p = articles[i+1]['page']
    else:
        next_p = 358
    # print when next_p == a['page']
    if next_p == a['page']:
        print(f"Same page start: {a['section']} {a['num']} on p.{a['page']} and next on p.{next_p}")
