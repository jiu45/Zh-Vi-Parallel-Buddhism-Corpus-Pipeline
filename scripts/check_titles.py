import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf')

current_section = 'TỰ'
articles = []

for pno in range(4, 358):
    page = doc[pno]
    text = page.get_text('dict')
    for block in text['blocks']:
        if 'lines' not in block:
            continue
        for line in block['lines']:
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
                    title_part = m.group(2).strip()
                    articles.append({
                        'section': current_section,
                        'num': num,
                        'page': pno + 1,
                        'line_text': line_text,
                        'title_part': title_part
                    })

print(f'Total articles detected: {len(articles)}')
tu_list = [a for a in articles if a['section'] == 'TỰ']
bat_list = [a for a in articles if a['section'] == 'BẠT']
print(f'TỰ count: {len(tu_list)}')
print(f'BẠT count: {len(bat_list)}')

# Check sequence
tu_nums = [a['num'] for a in tu_list]
bat_nums = [a['num'] for a in bat_list]
print('TỰ nums == 1..96?', tu_nums == list(range(1, 97)))
print('BẠT nums == 1..14?', bat_nums == list(range(1, 15)))
