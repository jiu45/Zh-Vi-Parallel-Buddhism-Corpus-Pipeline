import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def clean_spacing(text):
    """Normalize whitespace and punctuation spacing."""
    text = re.sub(r'[ \t\u00a0]+', ' ', text)
    # Normalize v.v.
    text = re.sub(r'\bv\.\s*v\.\s*\.', 'v.v..', text)
    text = re.sub(r'\bv\.\s*v\.', 'v.v.', text)
    # Remove space before punctuation
    text = re.sub(r'\s+([,.;:!?\)\]”"’\'])', r'\1', text)
    # Comma spacing: only when followed by letter or quote
    text = re.sub(r',(?=[a-zA-ZÀ-ỹ“"\'])', ', ', text)
    # Period spacing: only when followed by uppercase letter or quote/bracket, NOT digit or lowercase
    text = re.sub(r'(?<!\d)\.(?=[A-ZÀ-Ỹ“"\'\(\[])', '. ', text)
    # Semicolon spacing
    text = re.sub(r';(?=[a-zA-ZÀ-ỹ0-9“"\'])', '; ', text)
    # Colon spacing (not between digits)
    text = re.sub(r':(?=[a-zA-ZÀ-ỹ“"\'])', ': ', text)
    # Exclamation and question mark
    text = re.sub(r'([!?])(?=[a-zA-ZÀ-ỹ0-9“"\'])', r'\1 ', text)
    # Remove space after opening quotes/brackets
    text = re.sub(r'([\(“"‘\[])\s+', r'\1', text)
    # Re-normalize v.v.
    text = re.sub(r'\bv\.\s*v\.', 'v.v.', text)
    text = re.sub(r'[ \t\u00a0]+', ' ', text)
    return text.strip()

def split_sentences_viet(text):
    text = text.strip()
    if not text:
        return []
    
    # 1. Protect numbers with dots (e.g. 1.300, 2.000)
    text = re.sub(r'(\d+)\.(\d+)', r'\1@NUMDOT@\2', text)
    
    # 2. Protect v.v. inside sentence (followed by lowercase, comma, semicolon, or closing quote+lowercase)
    text = re.sub(r'\bv\.v\.(?=\s+[a-zà-ỹ])', '@VV_LOWER@', text)
    text = re.sub(r'\bv\.v\.(?=,)', '@VV_COMMA@', text)
    text = re.sub(r'\bv\.v\.(?=;)', '@VV_SEMI@', text)
    text = re.sub(r'\bv\.v\.(?=\s*[\)\]”"’\']\s+[a-zà-ỹ])', '@VV_CLOSE_LOWER@', text)
    
    # 3. Handle double-dot v.v.. at end of sentence
    text = re.sub(r'\bv\.v\.\.', '@VV_END@.', text)
    
    # Sentence splitting pattern: punctuation followed by uppercase or quote, or end of string
    pattern = r'([.?!]+[”"\'\)\]]*)(?=\s+[A-ZÀ-Ỹ“"\'\(]|$)'
    parts = re.split(pattern, text)
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
        # Restore protected tokens
        sent = sent.replace('@NUMDOT@', '.')
        sent = sent.replace('@VV_LOWER@', 'v.v.')
        sent = sent.replace('@VV_COMMA@', 'v.v.')
        sent = sent.replace('@VV_SEMI@', 'v.v.')
        sent = sent.replace('@VV_CLOSE_LOWER@', 'v.v.')
        sent = sent.replace('@VV_END@', 'v.v.')
        sent = clean_spacing(sent)
        if sent:
            sentences.append(sent)
            
    return sentences

# Test on problematic texts
test_samples = [
    "trộm nghĩ: Sách này lưu truyền đến nay đã hơn 1.300 năm qua, sai lầm chẳng ít.",
    "Từ khi Phật pháp truyền vào Trung Quốc đã hơn 1.800 năm.",
    "Do vậy hơn 2.000 năm qua, đạo ấy lưu truyền khắp thiên hạ.",
    "Chính là “thật thể, thật tánh của hết thảy các pháp: căn, trần, thức v.v. đều là không, vô sở hữu.” Hiểu rõ điều này thì...",
    "nghiệp tiêu chướng tận v.v.. “Minh cảm minh ứng” là trong đời quá khứ...",
    "Thiên Trúc Sơn ở Chiết Giang v.v. là những nơi cảm ứng rõ ràng, hương đèn nhộn nhịp."
]

for s in test_samples:
    cleaned = clean_spacing(s)
    sents = split_sentences_viet(cleaned)
    print("INPUT:  ", s)
    print("CLEANED:", cleaned)
    print("SENTS (count={}):".format(len(sents)))
    for idx, sent in enumerate(sents):
        print(f"   [{idx+1}] {sent}")
    print()
