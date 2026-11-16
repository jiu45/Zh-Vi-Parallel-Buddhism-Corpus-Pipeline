import sys, re
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')

sample_verse = "Người thấy nghe, tùy hỷ,"
from test_new_clean_split import split_sentences_viet
sents = split_sentences_viet(sample_verse)
print("Split verse line:", sents)
