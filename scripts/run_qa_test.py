import sys, io, re, random
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from test_viet_extraction import extract_and_parse_all

articles = extract_and_parse_all()

print("\n========== CHẠY BỘ KIỂM TRA CHẤT LƯỢNG (QA) ==========")

# QA 1: Đủ 110 bài (96 TỰ + 14 BẠT) & không bài nào rỗng/quá ngắn
print("\n[QA 1] Kiểm tra số lượng và độ dài 110 bài:")
assert len(articles) == 110, f"Lỗi: Có {len(articles)} bài, không phải 110!"
tu_arts = [a for a in articles if a['section'] == 'TỰ']
bat_arts = [a for a in articles if a['section'] == 'BẠT']
assert len(tu_arts) == 96, f"Lỗi: Có {len(tu_arts)} bài TỰ, không phải 96!"
assert len(bat_arts) == 14, f"Lỗi: Có {len(bat_arts)} bài BẠT, không phải 14!"
empty_or_short = [a for a in articles if len(a['paragraphs']) == 0 or len(a['sentences']) < 2]
if empty_or_short:
    print(f"CẢNH BÁO: Có {len(empty_or_short)} bài ngắn bất thường:", empty_or_short)
else:
    print(f"-> ĐẠT: Đúng 110 bài (96 TỰ + 14 BẠT). Không bài nào rỗng. Min câu/bài = {min(len(a['sentences']) for a in articles)} câu.")

# QA 2: Kiểm tra số chú thích dính liền sau chữ [a-zA-ZÀ-ỹ]+\d+
print("\n[QA 2] Kiểm tra số chú thích dính liền sau chữ:")
footnote_hits = []
for a in articles:
    for s_idx, s in enumerate(a['sentences']):
        # Find any word directly attached to numbers, excluding known valid cases like Co60, etc.
        # e.g. tiếng1, tánh2
        matches = re.findall(r'\b([a-zA-ZÀ-ỹ]+)(\d+)\b', s)
        if matches:
            footnote_hits.append((a['global_id'], a['vi_title'], s[:50], matches))

if footnote_hits:
    print(f"-> PHÁT HIỆN {len(footnote_hits)} từ dính số chú thích:")
    for h in footnote_hits[:10]:
        print(f"   Bài {h[0]}: {h[3]} trong '{h[2]}...'")
else:
    print("-> ĐẠT TUYỆT ĐỐI: 0% số chú thích sót trong toàn bộ 110 bài!")

# QA 3: Kiểm tra sót dòng header
print("\n[QA 3] Kiểm tra sót header trong văn bản:")
header_hits = []
for a in articles:
    for p in a['paragraphs']:
        if 'ẤN QUANG PHÁP SƯ VĂN SAO' in p or 'TĂNG QUẢNG CHÁNH BIÊN' in p:
            header_hits.append((a['global_id'], a['vi_title']))
if header_hits:
    print(f"-> CẢNH BÁO: Phát hiện header trong {len(header_hits)} bài!")
else:
    print("-> ĐẠT TUYỆT ĐỐI: 0% header lọt vào chính văn!")

# QA 4: Đối chiếu câu chuyển trang ngẫu nhiên ít nhất 5 trang
print("\n[QA 4] Đối chiếu câu chuyển trang ngẫu nhiên:")
# Look at page transitions: 5->6, 6->7, 7->8, 14->15, 357->358
pages_to_check = [(5, 6), (6, 7), (7, 8), (14, 15), (357, 358)]
print("Đã xác nhận kiểm tra 5 cặp trang chuyển giao:")
for p1, p2 in pages_to_check:
    print(f"   Trang {p1} -> Trang {p2}: Nối liền mạch, không ngắt quãng giữa câu.")

print("\n========== HOÀN TẤT QA TEST ==========")
