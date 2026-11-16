import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pymupdf

doc = pymupdf.open(r"d:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\01_nguon\viet\Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf")

def split_sentences_basic(text, include_semicolon=False):
    # Protect common abbreviations and numbers
    text = re.sub(r'\bv\.v\.', '@V_V@', text)
    text = re.sub(r'(\d+)\.(\d+)', r'\1@DOT@\2', text)
    
    if include_semicolon:
        pattern = r'([.?!;]+[”"\'\)\]]*)(?=\s+[A-ZÀ-Ỹ0-9“"\'\(]|$)'
    else:
        pattern = r'([.?!]+[”"\'\)\]]*)(?=\s+[A-ZÀ-Ỹ0-9“"\'\(]|$)'
        
    parts = re.split(pattern, text)
    sents = []
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
        s = (chunk + (" " + punct if punct and not chunk.endswith(punct) else punct)).strip()
        s = s.replace('@V_V@', 'v.v.').replace('@DOT@', '.')
        s = re.sub(r'\s+', ' ', s)
        if s:
            sents.append(s)
    return sents

# Test on 10 articles
for art_idx in range(5):
    # let's just inspect some sample text
    pass
