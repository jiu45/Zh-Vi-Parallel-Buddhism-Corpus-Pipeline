# -*- coding: utf-8 -*-
import base64
import os
import sys
import time
from google import genai

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
env_file = os.environ.get("ENV_FILE", str(BASE_DIR / ".env"))
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key and os.path.exists(env_file):
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('GEMINI_API_KEY='):
                api_key = line.strip().split('=', 1)[1]

client = genai.Client(api_key=api_key)
cleaned_dir = os.environ.get("CLEANED_DIR", str(BASE_DIR / "CV09_AQPSVS_Q3" / "02_ocr_tho" / "cleaned_pages"))

def load_b64(pno):
    p = os.path.join(cleaned_dir, f"page_{pno:04d}.png")
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

img3_b64 = load_b64(3)
img4_b64 = load_b64(4)

prompt = """Bạn là chuyên gia OCR cổ tịch Hán văn Phật giáo (tác phẩm Ấn Quang Pháp Sư Văn Sao).
Dưới đây là 2 trang sách ảnh cổ được cung cấp tuần tự (Ảnh 1 là Trang 3, Ảnh 2 là Trang 4).
Hãy trích xuất CHÍNH XÁC toàn bộ chữ Hán của từng trang theo đúng thứ tự đọc truyền thống:
- Đọc theo từng cột dọc từ PHẢI sang TRÁI, trong mỗi cột đọc từ TRÊN xuống DƯỚI.
- Giữ nguyên 100% chữ Hán phồn thể/dị thể và dấu chấm câu (。) nguyên bản trên trang.
- Các chữ in nhỏ song hành trong cột (tiểu tự như 代撰 hoặc 不慧) hãy đặt trong ngoặc đơn đúng vị trí: （代撰）, （不慧）.
- KHÔNG trích xuất dòng chữ ở lề ngoài khung (cột Bản tâm ghi tên sách hoặc số tờ ở rìa ngoài cùng).
- Định dạng xuất kết quả:
Phân tách rõ ràng từng trang bằng tiêu đề:
=== PAGE 0003 ===
<Nội dung chữ Hán trang 3>
=== PAGE 0004 ===
<Nội dung chữ Hán trang 4>

Chỉ xuất đúng định dạng trên, không thêm bất kỳ lời bình luận hay giải thích nào!"""

print("Sending request for Page 3 & Page 4 to gemini-3.8-flash...")
try:
    interaction = client.interactions.create(
        model="gemini-3.8-flash",
        input=[
            {"type": "text", "text": prompt},
            {"type": "image", "data": img3_b64, "mime_type": "image/png"},
            {"type": "image", "data": img4_b64, "mime_type": "image/png"},
        ],
        store=False,
    )
    print("OUTPUT:")
    print(interaction.output_text)
    print("USAGE:", interaction.usage)
except Exception as e:
    print("ERROR:", e)
