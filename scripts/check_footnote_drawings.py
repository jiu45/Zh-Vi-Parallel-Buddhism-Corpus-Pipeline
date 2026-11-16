import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf")

# Check all drawings and span sizes
pages_with_drawings = 0
drawing_y_coords = {}

for pno in range(4, 358):
    page = doc[pno]
    drawings = page.get_drawings()
    horiz_lines = []
    for d in drawings:
        # Check for horizontal line
        r = d['rect']
        if r.width > 50 and r.height < 5: # horizontal divider line
            horiz_lines.append(r.y0)
    if horiz_lines:
        pages_with_drawings += 1
        drawing_y_coords[pno + 1] = horiz_lines

print(f"Pages with horizontal divider lines: {pages_with_drawings}")
# Let's inspect a few drawing coordinates
for p in list(drawing_y_coords.keys())[:10]:
    print(f"Page {p}: horizontal line at y = {drawing_y_coords[p]}")

# Now let's check if there are any spans below these lines with size >= 12.5:
spans_below_divider = []
for pno in range(4, 358):
    if (pno + 1) in drawing_y_coords:
        y_div = min(drawing_y_coords[pno + 1])
        page = doc[pno]
        text_dict = page.get_text('dict')
        for b in text_dict['blocks']:
            if 'lines' not in b: continue
            for l in b['lines']:
                if l['bbox'][1] > y_div:
                    for s in l['spans']:
                        if s['size'] >= 12.5:
                            spans_below_divider.append((pno + 1, s['size'], s['text'], l['bbox']))

print(f"Spans below footnote divider with size >= 12.5: {len(spans_below_divider)}")
if spans_below_divider:
    for s in spans_below_divider[:10]:
        print(s)
