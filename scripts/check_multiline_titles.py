import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf')

# Let's see how titles in body look across multiple lines
current_section = 'TỰ'
articles = []

for pno in range(4, 358):
    page = doc[pno]
    text = page.get_text('dict')
    for b_idx, block in enumerate(text['blocks']):
        if 'lines' not in block:
            continue
        for l_idx, line in enumerate(block['lines']):
            line_text = ''.join(s['text'] for s in line['spans']).strip()
            bbox = line['bbox']
            if bbox[1] < 75:
                continue
            if line_text == 'V. BẠT':
                current_section = 'BẠT'
            
            s0 = line['spans'][0]
            if s0['size'] >= 14.0 and (s0['flags'] & 16 or 'Bold' in s0['font']):
                m = re.match(r'^(\d+)\.\s*(.*)', line_text)
                if m:
                    num = int(m.group(1))
                    # Check if there are following lines in the same block or next lines that are also bold/title
                    full_title_lines = [line_text]
                    for next_line in block['lines'][l_idx+1:]:
                        ns0 = next_line['spans'][0]
                        ntxt = ''.join(s['text'] for s in next_line['spans']).strip()
                        # If next line is bold title font and does NOT start with a new number
                        if (ns0['flags'] & 16 or 'Bold' in ns0['font']) and not re.match(r'^\d+\.', ntxt):
                            full_title_lines.append(ntxt)
                        else:
                            break
                    articles.append({
                        'section': current_section,
                        'num': num,
                        'page': pno + 1,
                        'full_title': ' '.join(full_title_lines)
                    })

for a in articles[:15]:
    print(f"[{a['section']} {a['num']:2d}] p.{a['page']:3d}: {a['full_title']}")
