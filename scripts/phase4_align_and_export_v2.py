# -*- coding: utf-8 -*-
"""
Phase 4 (v2): Hierarchical Anchor-Based Alignment — article count is data-driven (1..N).

Khác biệt so với phase4_align_and_export.py (bản gốc, vẫn được giữ nguyên):
- Không hard-code 110 bài: N = len(han_articles) và tự kiểm tra khớp 1-1 với bản Việt
  theo global_id (bản gốc chỉ chạy range(1, 111) nên bỏ sót bài và không phát hiện lệch).
- Bỏ 2 cặp đại mục cố định ("序" <-> "IV. TỰ") và ("跋" <-> "V. BẠT") vì chúng thuộc
  Quyển 3. Nếu cần chèn tiêu đề mục thì truyền SECTION_HEADERS_JSON, ví dụ:
      SECTION_HEADERS_JSON={"1": ["序", "IV. TỰ"], "97": ["跋", "V. BẠT"]}
  Mặc định rỗng: không bao giờ tự bịa thêm chữ Hán vào ngữ liệu.
- QA được làm lại: QA4 kiểm tra TỪNG BÀI tái tạo đúng 100% Hán văn và Quốc ngữ
  (không cần 03_text_sach/han.txt); QA5 đối chiếu toàn cục chỉ chạy khi có đủ file sạch.
- Một bài lỗi API không làm chết cả lượt chạy: ghi nhận, bỏ qua, chạy lại sẽ tự bổ sung.
- Đường dẫn mặc định trỏ tới Quyển 2 (CV09_AQPSVS_Q2); mọi đường dẫn vẫn ghi đè được
  bằng biến môi trường như bản gốc.

Giữ nguyên cơ chế cốt lõi: neo h_start + cắt lát tất định bằng Python để bảo toàn 100%
chuỗi ký tự gốc, xoay vòng nhiều API key/model, và checkpoint từng bài ra cache.

Cách chạy (chưa chạy trong phiên này):
    python scripts/phase4_align_and_export_v2.py
"""

import os
import sys
import json
import time
import re
from pathlib import Path
import openpyxl
from google import genai

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Dynamic project paths
BASE_DIR = Path(__file__).resolve().parent.parent
BOOK_DIR = BASE_DIR / os.environ.get("BOOK_DIR_NAME", "CV09_AQPSVS_Q2")
METADATA_DIR = BASE_DIR / "metadata"

ENV_FILE = os.environ.get("ENV_FILE", str(BASE_DIR / ".env"))
HAN_ARTICLES_JSON = os.environ.get("HAN_ARTICLES_JSON", str(METADATA_DIR / "articles.json"))
VIET_ARTICLES_JSON = os.environ.get("VIET_ARTICLES_JSON", str(METADATA_DIR / "viet_articles.json"))
CACHE_JSON = os.environ.get("CACHE_JSON", str(METADATA_DIR / "aligned_articles_cache.json"))
OUTPUT_TSV = os.environ.get("OUTPUT_TSV", str(BOOK_DIR / "04_dong_hang" / "AQPSVS_Q2_parallel.tsv"))
OUTPUT_XLSX = os.environ.get("OUTPUT_XLSX", str(BOOK_DIR / "04_dong_hang" / "AQPSVS_Q2_parallel.xlsx"))
CLEAN_HAN_TXT = os.environ.get("CLEAN_HAN_TXT", str(BOOK_DIR / "03_text_sach" / "han.txt"))
CLEAN_VIET_TXT = os.environ.get("CLEAN_VIET_TXT", str(BOOK_DIR / "03_text_sach" / "viet.txt"))

# Optional section header rows, e.g. '{"1": ["序", "IV. TỰ"], "97": ["跋", "V. BẠT"]}'.
# Empty by default: no invented Han text is ever inserted into the corpus.
SECTION_HEADERS_JSON = os.environ.get("SECTION_HEADERS_JSON", "")


def load_section_headers():
    if not SECTION_HEADERS_JSON.strip():
        return {}
    raw = json.loads(SECTION_HEADERS_JSON)
    return {int(k): [str(v[0]), str(v[1])] for k, v in raw.items()}


def load_api_keys():
    keys = []
    # 1. Environment variables
    env_keys = os.environ.get("GEMINI_API_KEYS")
    if env_keys:
        for k in env_keys.split(","):
            k = k.strip()
            if k and k not in keys:
                keys.append(k)
    env_single = os.environ.get("GEMINI_API_KEY")
    if env_single and env_single.strip() not in keys:
        keys.append(env_single.strip())

    # 2. Local .env file
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GEMINI_API_KEYS="):
                    raw_keys = line.split("=", 1)[1].split(",")
                    for k in raw_keys:
                        k = k.strip()
                        if k and k not in keys:
                            keys.append(k)
                elif line.startswith("GEMINI_API_KEY="):
                    k = line.split("=", 1)[1].strip()
                    if k and k not in keys:
                        keys.append(k)
    if not keys:
        raise ValueError(f"No GEMINI_API_KEYS found in environment variables or {ENV_FILE}")
    return keys


class MultiKeyModelRotator:
    def __init__(self, api_keys):
        self.slots = []
        # Priority 1: gemini-3.6-flash across all keys (minimal thinking -> super fast & high quality)
        for idx, k in enumerate(api_keys):
            self.slots.append({
                "key_id": f"Key#{idx+1}",
                "api_key": k,
                "model": "gemini-3.6-flash",
                "gen_cfg": {"thinking_level": "minimal"},
                "exhausted": False,
            })
        # Priority 2: gemini-3.8-flash across all keys (low thinking)
        for idx, k in enumerate(api_keys):
            self.slots.append({
                "key_id": f"Key#{idx+1}",
                "api_key": k,
                "model": "gemini-3.8-flash",
                "gen_cfg": {"thinking_level": "low"},
                "exhausted": False,
            })
        # Priority 3: gemini-3.5-flash-lite across all keys (500 RPD/key, 15 RPM)
        for idx, k in enumerate(api_keys):
            self.slots.append({
                "key_id": f"Key#{idx+1}",
                "api_key": k,
                "model": "gemini-3.5-flash-lite",
                "gen_cfg": {"thinking_level": "minimal"},
                "exhausted": False,
            })
        self.clients = {}
        for k in api_keys:
            self.clients[k] = genai.Client(
                api_key=k,
                http_options={"timeout": 120000, "retry_options": {"attempts": 1}},
            )
        self.current_idx = 0

    def get_active_slot(self):
        n = len(self.slots)
        for offset in range(n):
            idx = (self.current_idx + offset) % n
            if not self.slots[idx]["exhausted"]:
                self.current_idx = idx
                return self.slots[idx]
        raise RuntimeError("Toàn bộ API Key và Model trong danh sách đều đã cạn hạn mức RPD trong ngày!")

    def generate(self, prompt):
        while True:
            slot = self.get_active_slot()
            client = self.clients[slot["api_key"]]
            model = slot["model"]
            key_id = slot["key_id"]
            try:
                inter = client.interactions.create(
                    model=model,
                    input=prompt,
                    generation_config=slot["gen_cfg"],
                    store=False,
                )
                return inter.output_text, f"{key_id}:{model}"
            except Exception as e:
                err_msg = str(e)
                err_lower = err_msg.lower()
                is_rpd = (
                    ("requests per day" in err_lower)
                    or ("per_day" in err_lower)
                    or ("perday" in err_lower)
                    or bool(re.search(r"retry in \d+h", err_lower))
                    or ("403" in err_lower)
                    or ("permission_denied" in err_lower)
                )
                if is_rpd:
                    slot["exhausted"] = True
                    print(
                        f"  [ROTATE 0s] {key_id} ({model}) đã chạm trần RPD trong ngày hoặc bị từ chối. Chuyển ngay sang slot tiếp theo!",
                        flush=True,
                    )
                    self.current_idx = (self.current_idx + 1) % len(self.slots)
                    continue
                elif "429" in err_lower or "resource_exhausted" in err_lower:
                    print(
                        f"  [RPM LIMIT] {key_id} ({model}) chạm giới hạn phút (RPM). Chuyển sang key tiếp theo sau 4s...",
                        flush=True,
                    )
                    self.current_idx = (self.current_idx + 1) % len(self.slots)
                    time.sleep(4)
                    continue
                else:
                    print(
                        f"  [WARN] Lỗi tạm thời trên {key_id} ({model}): {err_msg[:120]}. Thử slot tiếp theo sau 3s...",
                        flush=True,
                    )
                    self.current_idx = (self.current_idx + 1) % len(self.slots)
                    time.sleep(3)


def parse_json_mapping(raw_text):
    raw = raw_text.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def align_single_article(rotator, gid, H, V):
    print(
        f"\n--- Dóng hàng Bài {gid} ({len(H)} H clauses, {len(V)} V sentences) ---",
        flush=True,
    )
    if len(V) == 1:
        zh_chunk = re.sub(r"[\r\n\t]+", "", "".join(H).strip())
        vi_chunk = re.sub(r"\s+", " ", re.sub(r"[\r\n\t]+", " ", V[0].strip())).strip()
        print(f"-> Bài {gid} chỉ có 1 câu tiếng Việt: ghép trực tiếp 100%.", flush=True)
        return [[zh_chunk, vi_chunk]]

    h_list_str = "\n".join(f"[H{i+1}] {c}" for i, c in enumerate(H))
    v_list_str = "\n".join(f"[V{i+1}] {s}" for i, s in enumerate(V))

    prompt = f"""Bạn là chuyên gia NLP ngữ liệu song ngữ Hán - Việt cổ.
Nhiệm vụ: Dóng hàng ngữ liệu song ngữ cho Bài {gid}.
Với mỗi câu tiếng Việt [V_j], hãy xác định chỉ số mệnh đề Hán văn bắt đầu [H_k].

DANH SÁCH MỆNH ĐỀ HÁN (từ 1 đến {len(H)}):
{h_list_str}

DANH SÁCH CÂU TIẾNG VIỆT (từ 1 đến {len(V)}):
{v_list_str}

QUY TẮC CẦN TUÂN THỦ TUYỆT ĐỐI:
1. Mọi câu tiếng Việt từ [V1] đến [V{len(V)}] phải được phủ kín, tuần tự từ 1 đến {len(V)}.
2. Với mỗi khối câu tiếng Việt [v_start, v_end] (thường là 1 câu [j, j]), hãy trả về:
   - "v": [v_start, v_end]
   - "h_start": chỉ số nguyên của mệnh đề Hán văn BẮT ĐẦU tương ứng với câu tiếng Việt này (1-indexed, từ 1 đến {len(H)}).
3. Chuỗi "h_start" phải tăng dần liên tục:
   - Câu đầu tiên V1 LUÔN có "h_start": 1.
   - Các mệnh đề Hán giữa 2 câu liên tiếp sẽ tự động thuộc về câu đứng trước: câu V_i quản lý từ H[h_start_i] đến H[h_start_{{i+1}} - 1].
   - Do đó, h_start của câu sau chính là điểm bắt đầu dịch của câu sau, không được gộp lấn sang phần của câu sau!

Chỉ trả về DUY NHẤT một mảng JSON hợp lệ (không giải thích thêm):
[
  {{"v": [1, 1], "h_start": 1}},
  ...
]
"""

    mapping = None
    used_slot_label = ""
    for attempt in range(4):
        raw_out, used_slot_label = rotator.generate(prompt)
        try:
            mapping = parse_json_mapping(raw_out)
            if isinstance(mapping, list) and len(mapping) > 0:
                break
        except Exception as e:
            print(f"  [JSON PARSE RETRY {attempt+1}] Lỗi parse JSON ({e}), gọi lại...", flush=True)
            mapping = None

    if not mapping:
        raise RuntimeError(f"Không thể dóng hàng Bài {gid} qua Gemini API!")

    # Clean and sort items by v_start
    cleaned_items = []
    for x in mapping:
        if not isinstance(x, dict) or "v" not in x or "h_start" not in x:
            continue
        v_val = x["v"]
        if isinstance(v_val, int):
            vs, ve = v_val, v_val
        elif isinstance(v_val, list) and len(v_val) >= 2:
            vs, ve = int(v_val[0]), int(v_val[1])
        elif isinstance(v_val, list) and len(v_val) == 1:
            vs, ve = int(v_val[0]), int(v_val[0])
        else:
            continue
        hs = int(x["h_start"])
        hs = max(1, min(len(H), hs))
        vs = max(1, min(len(V), vs))
        ve = max(vs, min(len(V), ve))
        cleaned_items.append({"v": [vs, ve], "h_start": hs})

    items = sorted(cleaned_items, key=lambda x: x["v"][0])
    items[0]["v"][0] = 1
    items[0]["h_start"] = 1

    # Ensure V ranges are contiguous (no missing V sentences) and h_start is non-decreasing
    for i in range(1, len(items)):
        if items[i]["h_start"] < items[i - 1]["h_start"]:
            items[i]["h_start"] = items[i - 1]["h_start"]
        if items[i]["v"][0] > items[i - 1]["v"][1] + 1:
            items[i - 1]["v"][1] = items[i]["v"][0] - 1
        elif items[i]["v"][0] <= items[i - 1]["v"][1]:
            items[i]["v"][0] = items[i - 1]["v"][1] + 1
            if items[i]["v"][1] < items[i]["v"][0]:
                items[i]["v"][1] = items[i]["v"][0]

    # Filter out any inverted V ranges after adjustment
    items = [it for it in items if it["v"][0] <= len(V) and it["v"][0] <= it["v"][1]]
    if items[-1]["v"][1] < len(V):
        items[-1]["v"][1] = len(V)

    # Merge items if they share the exact same h_start
    merged_items = []
    i = 0
    while i < len(items):
        curr = items[i]
        curr_vs, curr_ve = curr["v"]
        curr_hs = curr["h_start"]

        j = i + 1
        while j < len(items) and items[j]["h_start"] == curr_hs:
            curr_ve = max(curr_ve, items[j]["v"][1])
            j += 1

        merged_items.append({"v": [curr_vs, curr_ve], "h_start": curr_hs})
        i = j

    pairs = []
    for idx, item in enumerate(merged_items):
        h_s = item["h_start"]
        if idx < len(merged_items) - 1:
            h_e = merged_items[idx + 1]["h_start"] - 1
        else:
            h_e = len(H)

        v_s, v_e = item["v"]

        zh_chunk = "".join(H[h_s - 1 : h_e]).strip()
        vi_chunk = " ".join(V[v_s - 1 : v_e]).strip()

        zh_chunk = re.sub(r"[\r\n\t]+", "", zh_chunk)
        vi_chunk = re.sub(r"[\r\n\t]+", " ", vi_chunk)
        vi_chunk = re.sub(r"\s+", " ", vi_chunk).strip()

        if zh_chunk and vi_chunk:
            pairs.append([zh_chunk, vi_chunk])
        else:
            print(f"  Cảnh báo cặp rỗng: H[{h_s}:{h_e}], V[{v_s}:{v_e}]", flush=True)

    print(
        f"-> [{used_slot_label}] Tạo thành công {len(pairs)} cặp dóng hàng hợp lệ cho Bài {gid}.",
        flush=True,
    )
    return pairs


def build_full_pair_list(cache, han_arts, viet_arts, section_headers=None):
    """Builds ordered aligned pairs across all completed articles in cache.

    Inserts each completed article's title pair, plus any optional section-header
    rows configured via SECTION_HEADERS_JSON (keyed by article id).
    """
    section_headers = section_headers or {}
    all_pairs = []
    for gid in range(1, len(han_arts) + 1):
        if str(gid) not in cache:
            continue
        if gid in section_headers:
            all_pairs.append(list(section_headers[gid]))
        h_title = re.sub(r"[\r\n\t]+", "", han_arts[gid - 1]["zh_title"].strip())
        v_title = re.sub(r"\s+", " ", re.sub(r"[\r\n\t]+", " ", viet_arts[gid - 1]["vi_title"].strip())).strip()
        all_pairs.append([h_title, v_title])
        all_pairs.extend(cache[str(gid)])
    return all_pairs


def export_tsv_and_xlsx(all_aligned_pairs):
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, "w", encoding="utf-8") as f:
        for zh, vi in all_aligned_pairs:
            f.write(f"{zh}\t{vi}\n")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "DONG_HANG"
    ws.append(["Hán", "Việt"])  # Row 1: Header
    for zh, vi in all_aligned_pairs:
        ws.append([zh, vi])
    wb.save(OUTPUT_XLSX)


def run_qa(all_aligned_pairs, han_arts, viet_arts, cache, section_headers=None):
    section_headers = section_headers or {}
    print("\n--- CHẠY KIỂM ĐỊNH CHẤT LƯỢNG TỰ ĐỘNG (QA) CHO FILE TSV & XLSX ---", flush=True)
    assert os.path.exists(OUTPUT_TSV), "Lỗi: Không tìm thấy file TSV!"
    assert os.path.exists(OUTPUT_XLSX), "Lỗi: Không tìm thấy file XLSX!"

    with open(OUTPUT_TSV, "r", encoding="utf-8") as f:
        tsv_lines = [l.rstrip("\r\n") for l in f.readlines() if l.strip()]
    assert len(tsv_lines) == len(all_aligned_pairs), "Lỗi: Số dòng TSV không khớp!"

    wb_read = openpyxl.load_workbook(OUTPUT_XLSX)
    assert "DONG_HANG" in wb_read.sheetnames, "Lỗi: Không có sheet DONG_HANG trong Excel!"
    ws_read = wb_read["DONG_HANG"]
    assert ws_read.max_row == len(all_aligned_pairs) + 1, (
        f"Lỗi: Số dòng Excel ({ws_read.max_row}) không khớp TSV ({len(tsv_lines)+1})!"
    )
    print(
        f"  [QA 1] Đạt: Cả 2 file TSV và XLSX tồn tại và khớp 100% số lượng ({len(tsv_lines)} cặp).",
        flush=True,
    )

    for idx, line in enumerate(tsv_lines):
        cols = line.split("\t")
        assert len(cols) == 2, f"Lỗi: Dòng {idx+1} không có đúng 1 dấu Tab!"
        assert len(cols[0].strip()) > 0, f"Lỗi: Vế Hán dòng {idx+1} bị rỗng (MISSING)!"
        assert len(cols[1].strip()) > 0, f"Lỗi: Vế Việt dòng {idx+1} bị rỗng (MISSING)!"
    print("  [QA 2] Đạt tuyệt đối: Định dạng TSV chuẩn 1 Tab, không xuống dòng nội ô, MISSING = 0%.", flush=True)

    # Check the configured section headers (if any)
    if section_headers:
        missing = [gid for gid, pair in section_headers.items() if list(pair) not in all_aligned_pairs]
        assert not missing, f"Lỗi: Thiếu cặp đại mục đã cấu hình cho các Bài {missing}!"
        print(
            f"  [QA 3] Đạt: Đã có đầy đủ {len(section_headers)} cặp đại mục: "
            + ", ".join(f"'{p[0]}' <-> '{p[1]}'" for p in section_headers.values()),
            flush=True,
        )
    else:
        print("  [QA 3] Bỏ qua: Không cấu hình SECTION_HEADERS_JSON (không chèn tiêu đề mục do người dùng tự đặt).", flush=True)

    # Count sanity: every pair is either a title row, a section-header row, or a sentence pair
    expected = sum(len(v) for v in cache.values()) + len(cache) + len(
        [gid for gid in section_headers if str(gid) in cache]
    )
    assert len(all_aligned_pairs) == expected, (
        f"Lỗi: Số cặp tổng ({len(all_aligned_pairs)}) không khớp kỳ vọng ({expected})!"
    )

    # Per-article exact reconstruction: aligned chunks must rebuild 100% of both source texts,
    # in order, with no character invented or dropped.
    han_bad, vi_bad = [], []
    for gid in sorted(int(k) for k in cache):
        pairs = cache[str(gid)]
        h_full = re.sub(r"\s+", "", "".join(han_arts[gid - 1]["clauses"]))
        v_full = re.sub(r"\s+", "", " ".join(viet_arts[gid - 1]["sentences"]))
        h_cat = re.sub(r"\s+", "", "".join(p[0] for p in pairs))
        v_cat = re.sub(r"\s+", "", " ".join(p[1] for p in pairs))
        if h_cat != h_full:
            han_bad.append(gid)
        if v_cat != v_full:
            vi_bad.append(gid)

    assert not han_bad, f"Lỗi: Bài {han_bad} KHÔNG tái tạo đúng 100% Hán văn (mất/thừa ký tự)!"
    assert not vi_bad, f"Lỗi: Bài {vi_bad} KHÔNG tái tạo đúng 100% Quốc ngữ (mất/thừa ký tự)!"
    print(
        f"  [QA 4] Đạt tuyệt đối: {len(cache)}/{len(cache)} bài tái tạo 100% Hán văn và Quốc ngữ "
        f"(chuỗi ký tự gốc được bảo toàn từng bài, không chèn không bỏ).",
        flush=True,
    )

    # Optional: global cross-check against the cleaned full texts when they are available
    if os.path.exists(CLEAN_HAN_TXT) and os.path.exists(CLEAN_VIET_TXT):
        with open(CLEAN_HAN_TXT, "r", encoding="utf-8") as f:
            han_no_space = re.sub(r"\s+", "", f.read())
        han_sub_errors = 0
        for idx, (zh, vi) in enumerate(all_aligned_pairs):
            zh_clean = re.sub(r"\s+", "", zh)
            if zh_clean not in han_no_space:
                han_sub_errors += 1
                print(f"  Cảnh báo Hán không phải chuỗi con trong han.txt tại dòng {idx+1}: {zh[:30]}", flush=True)
        print(
            f"  [QA 5] Đối chiếu han.txt: {len(all_aligned_pairs) - han_sub_errors}/{len(all_aligned_pairs)} dòng khớp tuyệt đối.",
            flush=True,
        )
    else:
        print("  [QA 5] Bỏ qua: Không có đủ 03_text_sach/han.txt + viet.txt để đối chiếu toàn cục.", flush=True)

    print(f"\n=== TOÀN BỘ {len(cache)} BÀI ĐÃ DÓNG HÀNG VÀ XUẤT FILE THÀNH CÔNG! ===", flush=True)


def main():
    api_keys = load_api_keys()
    print(f"Đã nạp {len(api_keys)} API Keys hợp lệ vào bộ xoay vòng (Rotator).", flush=True)
    rotator = MultiKeyModelRotator(api_keys)

    with open(HAN_ARTICLES_JSON, "r", encoding="utf-8") as f:
        han_arts = json.load(f)
    with open(VIET_ARTICLES_JSON, "r", encoding="utf-8") as f:
        viet_arts = json.load(f)

    # Fail fast on a mismatched corpus instead of silently dropping an article
    assert len(han_arts) == len(viet_arts), (
        f"Lỗi: Số bài Hán ({len(han_arts)}) != số bài Việt ({len(viet_arts)})!"
    )
    for i in range(len(han_arts)):
        assert han_arts[i]["global_id"] == viet_arts[i]["global_id"], (
            f"Lỗi: Lệch global_id tại vị trí {i+1}: Hán={han_arts[i]['global_id']} Việt={viet_arts[i]['global_id']}!"
        )
    n_articles = len(han_arts)
    section_headers = load_section_headers()
    for gid in section_headers:
        assert 1 <= gid <= n_articles, f"Lỗi: SECTION_HEADERS_JSON có Bài {gid} ngoài phạm vi 1..{n_articles}!"

    print(f"=== BẮT ĐẦU GIAI ĐOẠN 4: DÓNG HÀNG TOÀN BỘ {n_articles} BÀI (ANCHOR ALIGNED + MULTI-KEY ROTATION) ===", flush=True)
    print(f"  Hán: {HAN_ARTICLES_JSON}\n  Việt: {VIET_ARTICLES_JSON}\n  Cache: {CACHE_JSON}", flush=True)
    print(f"  TSV: {OUTPUT_TSV}\n  XLSX: {OUTPUT_XLSX}", flush=True)

    cache = {}
    if os.path.exists(CACHE_JSON):
        try:
            with open(CACHE_JSON, "r", encoding="utf-8") as f:
                cache = json.load(f)
            print(f"Đã tải cache dóng hàng: {len(cache)}/{n_articles} bài đã hoàn tất trước đó.", flush=True)
        except Exception as e:
            print(f"Cảnh báo đọc cache: {e}", flush=True)
    elif os.environ.get("SEED_FROM_TSV") == "1" and os.path.exists(OUTPUT_TSV):
        # Legacy Q3 pilot seeding (opt-in only): Articles 1..5 from an existing verified TSV
        tsv_rows = [
            l.rstrip("\r\n").split("\t")
            for l in open(OUTPUT_TSV, "r", encoding="utf-8")
            if l.strip() and "\t" in l
        ]
        tsv_rows = [r for r in tsv_rows if len(r) == 2]
        idx = 0
        for gid in range(1, min(5, n_articles) + 1):
            v_art = viet_arts[gid - 1]
            art_text = " ".join(v_art["sentences"])
            pairs = []
            while idx < len(tsv_rows):
                zh, vi = tsv_rows[idx]
                if vi[:25] in art_text:
                    pairs.append([zh, vi])
                    idx += 1
                else:
                    break
            if pairs:
                cache[str(gid)] = pairs
        if len(cache) == 5:
            with open(CACHE_JSON, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            print(f"Đã khôi phục 5 bài Pilot đầu tiên ({idx} cặp câu) vào cache.", flush=True)

    # Immediately update TSV/XLSX with existing cached articles + section headers so files are always up-to-date
    if cache:
        initial_pairs = build_full_pair_list(cache, han_arts, viet_arts, section_headers)
        export_tsv_and_xlsx(initial_pairs)
        print(f"Đã cập nhật ngay file TSV/XLSX với {len(initial_pairs)} cặp hiện có (bao gồm đại mục & tiêu đề bài).", flush=True)

    failed = []
    for gid in range(1, n_articles + 1):
        if str(gid) in cache and len(cache[str(gid)]) > 0:
            continue
        h_art = han_arts[gid - 1]
        v_art = viet_arts[gid - 1]
        try:
            pairs = align_single_article(rotator, gid, h_art["clauses"], v_art["sentences"])
        except Exception as e:
            # Never let one article abort a 100+ article run: keep going, resume later.
            print(f"  [LỖI] Bài {gid} thất bại ({type(e).__name__}: {e}). Bỏ qua và thử lại ở lần chạy sau.", flush=True)
            failed.append(gid)
            continue
        cache[str(gid)] = pairs

        with open(CACHE_JSON, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

        # Update TSV & XLSX every 5 articles or on the last article
        if gid % 5 == 0 or gid == n_articles:
            cur_pairs = build_full_pair_list(cache, han_arts, viet_arts, section_headers)
            export_tsv_and_xlsx(cur_pairs)
            print(f"  [CHECKPOINT] Đã lưu {len(cache)}/{n_articles} bài ({len(cur_pairs)} cặp câu) vào TSV & XLSX.", flush=True)

        if gid < n_articles:
            time.sleep(3)

    final_pairs = build_full_pair_list(cache, han_arts, viet_arts, section_headers)
    export_tsv_and_xlsx(final_pairs)
    print(f"\n==========================================", flush=True)
    print(
        f"Tổng số cặp dóng hàng toàn bộ {n_articles} bài "
        f"(+ {len(section_headers)} đại mục + {len(cache)} tiêu đề): {len(final_pairs)}",
        flush=True,
    )
    print(f"==========================================", flush=True)
    run_qa(final_pairs, han_arts, viet_arts, cache, section_headers)

    missing = [gid for gid in range(1, n_articles + 1) if str(gid) not in cache]
    if missing:
        print(
            f"\n[CHƯA XONG] {len(missing)}/{n_articles} bài còn thiếu: {missing}\n"
            f"Chạy lại script này để tự động bổ sung các bài còn thiếu (cache đã có sẵn sẽ được giữ nguyên).",
            flush=True,
        )
        return 1
    print(f"\n[HOÀN TẤT] Đã dóng hàng đủ {n_articles}/{n_articles} bài.", flush=True)
    return 0


if __name__ == "__main__":
    main()
