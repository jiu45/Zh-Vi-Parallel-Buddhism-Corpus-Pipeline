# -*- coding: utf-8 -*-
import sys, io, re, json
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

with open(r"d:\CS\NLP\Mid-Term\scripts\test_fixed_pipeline.py", "r", encoding="utf-8") as f:
    code = f.read()
ns = {}
exec(code, ns)
articles = ns['articles']

digit_period_sents = []
for a in articles:
    for idx, s in enumerate(a['sentences']):
        m = re.search(r'\b\d+\s*[.?!][”"\'\)\]]*$', s)
        if m:
            digit_period_sents.append((a['global_id'], idx, s))

print(f"Total sentences ending with digit+period: {len(digit_period_sents)}")
for c in digit_period_sents:
    print(f"  Art {c[0]} [s{c[1]}]: {c[2]}")
