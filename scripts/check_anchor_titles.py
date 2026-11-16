import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open(r"d:\CS\NLP\Mid-Term\metadata\anchor_map.json", 'r', encoding='utf-8') as f:
    anchor_map = json.load(f)

for gid in [16, 25, 26, 39]:
    print(anchor_map[gid - 1])
