import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf')

toc_lines = []
for pno in range(358, 366): # 359 to 366
    page = doc[pno]
    blocks = page.get_text('blocks')
    for b in blocks:
        text = b[4].strip()
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line in ['MỤC LỤC', 'IV. TỰ', 'V. BẠT', 'ẤN QUANG PHÁP SƯ VĂN SAO', 'TĂNG QUẢNG CHÁNH BIÊN - QUYỂN III']:
                continue
            toc_lines.append(line)

# Let's inspect TOC entries
# In TOC, an entry usually starts with: "<num>." or "<num>.\t"
# Followed by title lines, and ends with page number.
entries = []
cur_num = None
cur_title_parts = []
cur_section = 'TỰ'

for line in toc_lines:
    # check if section change
    if 'V. BẠT' in line:
        cur_section = 'BẠT'
        continue
    
    # Check if starting with a number
    m = re.match(r'^(\d+)\.\s*(.*)', line)
    if m:
        if cur_num is not None:
            entries.append((cur_section, cur_num, cur_title_parts))
        cur_num = int(m.group(1))
        cur_title_parts = []
        rest = m.group(2).strip()
        if rest:
            cur_title_parts.append(rest)
    else:
        if cur_num is not None:
            cur_title_parts.append(line)

if cur_num is not None:
    entries.append((cur_section, cur_num, cur_title_parts))

print(f"Total raw TOC entries: {len(entries)}")
# Let's see how each entry looks: the last token of title_parts is usually the page number!
parsed_toc = []
current_sec = 'TỰ'
for sec, num, parts in entries:
    full_str = ' '.join(parts).strip()
    # If num resets to 1, section becomes BẠT
    if num == 1 and len(parsed_toc) >= 90:
        current_sec = 'BẠT'
    # Extract page number at the end
    m_page = re.search(r'(\d+)$', full_str)
    if m_page:
        page_no = int(m_page.group(1))
        title = full_str[:m_page.start()].strip()
    else:
        page_no = None
        title = full_str
    # normalize spaces
    title = re.sub(r'\s+', ' ', title)
    parsed_toc.append({
        'section': current_sec,
        'num': num,
        'title': f"{num}. {title}",
        'toc_page': page_no
    })

print(f"Parsed TOC count: {len(parsed_toc)}")
for item in parsed_toc[:5]:
    print(item)
print("...")
for item in parsed_toc[-5:]:
    print(item)
