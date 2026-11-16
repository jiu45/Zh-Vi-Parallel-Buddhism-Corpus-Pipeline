import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf")

def split_sentences_viet(text):
    """
    Split clean Vietnamese paragraph into sentences.
    Respects quotes, parentheses, abbreviations like v.v.
    """
    text = text.strip()
    if not text:
        return []
    
    # Protect common abbreviations
    protected = text
    # e.g., 'v.v...'
    protected = re.sub(r'\bv\.v\.', '@V_V@', protected)
    protected = re.sub(r'\bth\.sĩ\b', '@TH_SI@', protected)
    protected = re.sub(r'\bts\.', '@TS@', protected)
    
    # Pattern for sentence end:
    # A punctuation [.?!] optionally followed by closing quotes/parentheses [”"'\)\]]*
    # followed by whitespace and an uppercase letter or start of next sentence
    pattern = r'([.?!]+[”"\'\)\]]*)(?=\s+[A-ZÀ-Ỹ0-9“"\'\(]|$)'
    
    parts = re.split(pattern, protected)
    sentences = []
    
    i = 0
    while i < len(parts):
        chunk = parts[i].strip()
        if not chunk:
            i += 1
            continue
        punct = ""
        if i + 1 < len(parts):
            punct = parts[i+1].strip()
            i += 2
        else:
            i += 1
        
        sent = (chunk + (" " + punct if punct and not chunk.endswith(punct) else punct)).strip()
        # restore abbreviations
        sent = sent.replace('@V_V@', 'v.v.').replace('@TH_SI@', 'th.sĩ').replace('@TS@', 'ts.')
        # Clean double spaces
        sent = re.sub(r'\s+', ' ', sent)
        if sent:
            sentences.append(sent)
            
    return sentences

# Let's test on article 1 text
# We extract article 1 paragraphs
p1_lines = []
for pno in range(4, 8):
    p = doc[pno]
    td = p.get_text('dict')
    for b in td['blocks']:
        if 'lines' not in b: continue
        for l in b['lines']:
            if l['bbox'][1] < 75: continue
            spans = [s for s in l['spans'] if s['size'] >= 12.5]
            if not spans: continue
            txt = ''.join(s['text'] for s in spans).strip()
            if txt:
                p1_lines.append((pno+1, l['bbox'][0], l['bbox'][1], txt))

# Look at lines of Article 1
print(f"Total lines in p.5-8: {len(p1_lines)}")
for item in p1_lines[:15]:
    print(item)
