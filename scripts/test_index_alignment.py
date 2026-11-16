# -*- coding: utf-8 -*-
import os, sys, json
from pathlib import Path
from google import genai

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = os.environ.get("ENV_FILE", str(BASE_DIR / ".env"))
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key and os.path.exists(ENV_FILE):
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("GEMINI_API_KEY="):
                api_key = line.strip().split("=", 1)[1]

client = genai.Client(api_key=api_key)

with open(str(BASE_DIR / "metadata" / "han_articles_pilot.json"), "r", encoding="utf-8") as f:
    han_arts = json.load(f)
with open(str(BASE_DIR / "metadata" / "viet_articles.json"), "r", encoding="utf-8") as f:
    viet_arts = json.load(f)

art1_h = han_arts[0]
art1_v = viet_arts[0]

H = art1_h['clauses']
V = art1_v['sentences']

print(f"Article 1: {len(H)} H clauses, {len(V)} V sentences")

h_list_str = "\n".join(f"[H{i+1}] {c}" for i, c in enumerate(H))
v_list_str = "\n".join(f"[V{i+1}] {s}" for i, s in enumerate(V))

prompt = f"""Bạn là chuyên gia NLP ngữ liệu song ngữ Hán - Việt.
Nhiệm vụ: Dóng hàng (align) các mệnh đề Hán văn ([H1] đến [H{len(H)}]) với các câu tiếng Việt ([V1] đến [V{len(V)}]) tương ứng về ngữ nghĩa.

DANH SÁCH MỆNH ĐỀ HÁN:
{h_list_str}

DANH SÁCH CÂU TIẾNG VIỆT:
{v_list_str}

QUY TẮC BẮT BUỘC:
1. Mỗi cặp dóng hàng tương ứng một đơn vị dịch thuật trọn vẹn nghĩa (thường là 1 câu tiếng Việt [V_j] khớp với 1 hoặc nhiều mệnh đề Hán [H_start..H_end]).
2. Toàn bộ các chỉ số H (từ 1 đến {len(H)}) và V (từ 1 đến {len(V)}) phải được phủ kín 100%, liên tục theo thứ tự tăng dần, không bỏ sót bất kỳ H hay V nào (không có OMISSION), không lặp lại chỉ số.
3. Chỉ trả về duy nhất một mảng JSON các object theo định dạng sau:
[
  {{"h": [1, 1], "v": [1, 1]}},
  {{"h": [2, 9], "v": [2, 2]}},
  ...
]
Trong đó "h": [h_start, h_end] và "v": [v_start, v_end] là khoảng chỉ số bao gồm cả 2 đầu mút."""

print("Calling gemini-3.5-flash-lite for Article 1 alignment...")
inter = client.interactions.create(
    model="gemini-3.5-flash-lite",
    input=prompt,
    store=False
)

raw_json = inter.output_text.strip()
if raw_json.startswith("```json"):
    raw_json = raw_json[7:]
if raw_json.startswith("```"):
    raw_json = raw_json[3:]
if raw_json.endswith("```"):
    raw_json = raw_json[:-3]
raw_json = raw_json.strip()

mapping = json.loads(raw_json)
print(f"Received {len(mapping)} aligned pairs.")

# Verify coverage and continuity
h_curr = 1
v_curr = 1
valid = True
for idx, pair in enumerate(mapping):
    h_s, h_e = pair['h']
    v_s, v_e = pair['v']
    if h_s != h_curr:
        print(f"H Gap at pair {idx}: expected {h_curr}, got {h_s}")
        valid = False
    if v_s != v_curr:
        print(f"V Gap at pair {idx}: expected {v_curr}, got {v_s}")
        valid = False
    h_curr = h_e + 1
    v_curr = v_e + 1

if h_curr - 1 == len(H) and v_curr - 1 == len(V) and valid:
    print("SUCCESS: 100% continuous coverage for both H and V!")
else:
    print(f"Final H: {h_curr-1}/{len(H)}, Final V: {v_curr-1}/{len(V)}")

# Print sample pairs
for idx, pair in enumerate(mapping[:5]):
    h_s, h_e = pair['h']
    v_s, v_e = pair['v']
    zh_chunk = "".join(H[h_s-1 : h_e])
    vi_chunk = " ".join(V[v_s-1 : v_e])
    print(f"\n[Pair {idx+1}] H[{h_s}..{h_e}] <-> V[{v_s}..{v_e}]")
    print("  HÁN :", zh_chunk)
    print("  VIỆT:", vi_chunk)
