# -*- coding: utf-8 -*-
"""
Phase 3: Chinese PDF Image Preprocessing & OCR with Cascading Fallback & Inline QA
- Supports --start-page, --end-page, --batch-size CLI parameters.
- Checkpoint: Skips pages that already have valid 02_ocr_tho/han/page_XXXX.txt.
- Batching: Batches 5 pages per request to save Free Tier requests.
- Validated Models:
    1. gemini-3.8-flash (5 RPM, 20 RPD)
    2. gemini-3.6-flash (5 RPM, 20 RPD)
    3. gemini-3.7-flash (5 RPM, 20 RPD)
    4. gemini-3.5-flash (5 RPM, 20 RPD)
    5. gemini-3.5-flash-lite (15 RPM, 500 RPD)
- Distinguishes 5 RPM rate limit vs RPD exhaustion: sleeps 25s on 429 before cascading.
- Inline QA Gate:
    - Page tag present
    - Han character count >= 80 (page 198 >= 50)
    - Full stop count (。) >= 4 (page 198 >= 2)
    - No repetition loop
- Individual page retry on QA fail without discarding passed pages
- Real-time logging to metadata/ocr_han_log.json
"""

import os
import sys
import argparse
import base64
import time
import re
import json
from pathlib import Path
import numpy as np
from PIL import Image
import pymupdf
from google import genai

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Dynamic project paths
BASE_DIR = Path(__file__).resolve().parent.parent
BOOK_DIR = BASE_DIR / os.environ.get("BOOK_DIR_NAME", "CV09_AQPSVS_Q3")
METADATA_DIR = BASE_DIR / "metadata"

ZH_PDF = os.environ.get("ZH_PDF_PATH", str(BOOK_DIR / "01_nguon" / "han" / "Ấn Quang Pháp Sư Văn Sao - Zh - 3.pdf"))
RAW_HAN_DIR = os.environ.get("RAW_HAN_DIR", str(BOOK_DIR / "02_ocr_tho" / "han"))
CLEANED_DIR = os.environ.get("CLEANED_DIR", str(BOOK_DIR / "02_ocr_tho" / "cleaned_pages"))
ENV_FILE = os.environ.get("ENV_FILE", str(BASE_DIR / ".env"))
OCR_LOG_FILE = os.environ.get("OCR_LOG_FILE", str(METADATA_DIR / "ocr_han_log.json"))

CASCADE_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.8-flash",
]

def load_api_key():
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        return env_key.strip()
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('GEMINI_API_KEY='):
                    return line.split('=', 1)[1].strip()
    raise ValueError(f"GEMINI_API_KEY not found in environment or {ENV_FILE}")

def get_or_render_cleaned_image(doc, pno):
    os.makedirs(CLEANED_DIR, exist_ok=True)
    out_img = os.path.join(CLEANED_DIR, f"page_{pno:04d}.png")
    if os.path.exists(out_img) and os.path.getsize(out_img) > 1000:
        return out_img
    page = doc[pno - 1]
    pix = page.get_pixmap(dpi=200, colorspace=pymupdf.csGRAY)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    clipped = np.clip((img.astype(np.float32) - 60) * (255.0 / (165 - 60)), 0, 255).astype(np.uint8)
    Image.fromarray(clipped).save(out_img)
    return out_img

def load_ocr_log():
    if os.path.exists(OCR_LOG_FILE):
        try:
            with open(OCR_LOG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_ocr_log(log_data):
    os.makedirs(os.path.dirname(OCR_LOG_FILE), exist_ok=True)
    with open(OCR_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

def check_repetition(text):
    """Check if there is an infinite repetition loop in OCR text."""
    for length in range(8, 25):
        pattern = r'(.{' + str(length) + r'})\1{3,}'
        if re.search(pattern, text):
            return True
    return False

def inline_qa_check(pno, text):
    """Inline QA Gate: validates extracted page text."""
    text_clean = text.strip()
    char_count = len(re.findall(r'[\u4e00-\u9fff]', text_clean))
    period_count = text_clean.count('。') + text_clean.count('、')
    
    min_chars = 50 if pno == 198 else 150
    min_periods = 4 if pno == 198 else 30
    
    reasons = []
    if char_count < min_chars:
        reasons.append(f"Chữ Hán quá ít ({char_count} < {min_chars})")
    if char_count > 650:
        reasons.append(f"Chữ Hán quá nhiều - nghi gộp trang ({char_count} > 650)")
    if period_count < min_periods:
        reasons.append(f"Dấu chấm câu 。 quá ít ({period_count} < {min_periods})")
    if check_repetition(text_clean):
        reasons.append("Phát hiện lặp từ vô tận (repetition loop)")
        
    passed = len(reasons) == 0
    return passed, char_count, period_count, reasons

def call_gemini_ocr(client, model_name, batch_pages, doc):
    pages_str = ', '.join(str(p) for p in batch_pages)
    prompt = f"""Bạn là chuyên gia OCR cổ tịch Hán văn Phật giáo (tác phẩm Ấn Quang Pháp Sư Văn Sao).
Dưới đây là {len(batch_pages)} trang sách ảnh cổ được cung cấp tuần tự (các trang {pages_str}).
Hãy trích xuất CHÍNH XÁC toàn bộ chữ Hán của từng trang theo đúng thứ tự đọc truyền thống:
- Đọc theo từng cột dọc từ PHẢI sang TRÁI, trong mỗi cột đọc từ TRÊN xuống DƯỚI.
- BẮT BUỘC giữ nguyên 100% chữ Hán phồn thể/dị thể và TOÀN BỘ dấu ngắt câu trên trang sách (bao gồm cả dấu chấm tròn rỗng 。 lẫn các dấu chấm tròn đặc • hoặc dấu phẩy chấm 、 nằm bên cạnh chân chữ Hán — hãy chuyển toàn bộ các dấu chấm câu/chấm đặc đó thành dấu 。 hoặc 、 đúng vị trí). Tuyệt đối không được lược bỏ dấu câu!
- Các chữ in nhỏ song hành trong cột (tiểu tự như 代撰 hoặc 不慧) hãy đặt trong ngoặc đơn đúng vị trí ngữ cảnh: （代撰）, （不慧）.
- KHÔNG trích xuất dòng chữ ở lề ngoài khung (cột Bản tâm ghi tên sách hoặc số tờ ở rìa ngoài cùng).
"""
    prompt += "\nĐịnh dạng xuất kết quả:\nPhân tách rõ ràng từng trang bằng tiêu đề chính xác:\n"
    for p in batch_pages:
        prompt += f"=== PAGE {p:04d} ===\n<Nội dung chữ Hán trang {p}>\n"
    prompt += "\nChỉ xuất đúng định dạng trên, không thêm bất kỳ lời bình luận hay giải thích nào!"

    inputs = [{"type": "text", "text": prompt}]
    for p in batch_pages:
        img_path = get_or_render_cleaned_image(doc, p)
        with open(img_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        inputs.append({"type": "image", "data": b64_data, "mime_type": "image/png"})

    thinking_lvl = "low" if ("3.8" in model_name or "3.7" in model_name) else "minimal"
    interaction = client.interactions.create(
        model=model_name,
        input=inputs,
        generation_config={"thinking_level": thinking_lvl},
        store=False,
    )
    return interaction.output_text

def parse_output(raw_output):
    page_texts = {}
    pattern = r'===\s*PAGE\s*(\d+)\s*===\s*\n?'
    splits = re.split(pattern, raw_output)
    i = 1
    while i < len(splits):
        pno_extracted = int(splits[i])
        txt_extracted = splits[i+1].strip()
        txt_extracted = txt_extracted.replace('•', '。').replace('．', '。').replace('・', '。')
        page_texts[pno_extracted] = txt_extracted
        i += 2
    return page_texts

def call_with_rpm_retry(client, model_name, pages, doc):
    """Calls call_gemini_ocr; retries up to 3 times on 5 RPM 429 or 503 high demand."""
    for attempt in range(4):
        try:
            return call_gemini_ocr(client, model_name, pages, doc)
        except Exception as e:
            err_msg = str(e)
            is_rpd = bool(re.search(r'retry in \d+h', err_msg.lower()))
            if is_rpd:
                raise RuntimeError(f"RPD_EXHAUSTED: {err_msg}")
            if attempt < 3 and ("429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "timed out" in err_msg.lower() or "503" in err_msg or "high demand" in err_msg.lower()):
                wait_s = 20 * (attempt + 1)
                print(f"  [Transient 429/503/Timeout trên {model_name} (lần {attempt+1})] Chờ {wait_s}s rồi thử lại...", flush=True)
                time.sleep(wait_s)
                continue
            raise

def ocr_batch_cascading(client, batch_pages, doc, model_idx_ref, ocr_log):
    remaining_in_batch = []
    for p in batch_pages:
        target_file = os.path.join(RAW_HAN_DIR, f"page_{p:04d}.txt")
        if not (os.path.exists(target_file) and os.path.getsize(target_file) > 50):
            remaining_in_batch.append(p)
            
    if not remaining_in_batch:
        return True, CASCADE_MODELS[model_idx_ref[0]]

    print(f"\n[OCR BATCH] Đang xử lý các trang: {remaining_in_batch}", flush=True)
    
    cur_idx = model_idx_ref[0]
    while cur_idx < len(CASCADE_MODELS):
        model_name = CASCADE_MODELS[cur_idx]
        print(f"  Thử với model: {model_name}...", flush=True)
        
        try:
            raw_output = call_with_rpm_retry(client, model_name, remaining_in_batch, doc)
            page_texts = parse_output(raw_output)
            
            failed_pages = []
            for p in remaining_in_batch:
                if p not in page_texts:
                    failed_pages.append(p)
                    continue
                txt = page_texts[p]
                passed, c_cnt, p_cnt, reasons = inline_qa_check(p, txt)
                if not passed:
                    print(f"  [QA FAIL] Trang {p}: {', '.join(reasons)}", flush=True)
                    failed_pages.append(p)
                else:
                    out_file = os.path.join(RAW_HAN_DIR, f"page_{p:04d}.txt")
                    with open(out_file, "w", encoding="utf-8") as f:
                        f.write(txt + "\n")
                    print(f"  [QA PASS] -> Đã lưu page_{p:04d}.txt ({c_cnt} chữ Hán, {p_cnt} dấu 。) [Model: {model_name}]", flush=True)
                    ocr_log[str(p)] = {
                        "page": p,
                        "model": model_name,
                        "char_count": c_cnt,
                        "period_count": p_cnt,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    save_ocr_log(ocr_log)
                    
            if not failed_pages:
                return True, model_name
            else:
                print(f"  Thử retry gộp (1 request) cho các trang chưa đạt ({failed_pages})...", flush=True)
                still_failed = []
                time.sleep(13)
                try:
                    retry_out = call_with_rpm_retry(client, model_name, failed_pages, doc)
                    retry_parsed = parse_output(retry_out)
                    for fp in failed_pages:
                        if fp in retry_parsed:
                            sp_txt = retry_parsed[fp]
                            s_pass, s_c, s_p, s_r = inline_qa_check(fp, sp_txt)
                            if s_pass:
                                out_file = os.path.join(RAW_HAN_DIR, f"page_{fp:04d}.txt")
                                with open(out_file, "w", encoding="utf-8") as f:
                                    f.write(sp_txt + "\n")
                                print(f"  [QA PASS RETRY] -> Đã lưu page_{fp:04d}.txt ({s_c} chữ, {s_p} dấu 。)", flush=True)
                                ocr_log[str(fp)] = {
                                    "page": fp,
                                    "model": model_name,
                                    "char_count": s_c,
                                    "period_count": s_p,
                                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                                }
                                save_ocr_log(ocr_log)
                                continue
                        still_failed.append(fp)
                except RuntimeError as re_err:
                    if "RPD_EXHAUSTED" in str(re_err):
                        remaining_in_batch = failed_pages
                        raise
                    still_failed = list(failed_pages)
                except Exception as e_single:
                    print(f"  Lỗi khi retry gộp {failed_pages}: {e_single}", flush=True)
                    still_failed = list(failed_pages)
                        
                if not still_failed:
                    return True, model_name
                else:
                    remaining_in_batch = still_failed
                    cur_idx += 1
                    if cur_idx < len(CASCADE_MODELS):
                        print(f"  Thử model dự phòng {CASCADE_MODELS[cur_idx]} cho các trang khó: {remaining_in_batch}...", flush=True)
                    else:
                        raise RuntimeError(f"Đã hết danh sách model chất lượng cao khi xử lý trang {remaining_in_batch}!")
                    
        except Exception as e:
            err_msg = str(e)
            print(f"  Model {model_name} gặp lỗi: {err_msg[:120]}", flush=True)
            if "RPD_EXHAUSTED" in err_msg or "requests per day" in err_msg.lower():
                print(f"  Model {model_name} đã chạm trần 20 RPD! Chuyển vĩnh viễn sang model tiếp theo (0s)...", flush=True)
                model_idx_ref[0] = max(model_idx_ref[0], cur_idx + 1)
            cur_idx += 1
            if cur_idx < len(CASCADE_MODELS):
                print(f"  -> CHUYỂN SANG MODEL DỰ PHÒNG: {CASCADE_MODELS[cur_idx]}!", flush=True)
            else:
                raise RuntimeError("Toàn bộ các model cascading đều đã cạn hạn mức!")

    raise RuntimeError(f"Không thể OCR các trang {remaining_in_batch} qua danh sách model cascading!")

def main():
    parser = argparse.ArgumentParser(description="OCR Chinese pages with Cascading Models & Inline QA")
    parser.add_argument("--start-page", type=int, default=75, help="Start page (1-indexed)")
    parser.add_argument("--end-page", type=int, default=198, help="End page (1-indexed)")
    parser.add_argument("--batch-size", type=int, default=5, help="Batch size of pages per request")
    args = parser.parse_args()

    os.makedirs(RAW_HAN_DIR, exist_ok=True)
    api_key = load_api_key()
    client = genai.Client(
        api_key=api_key,
        http_options={"timeout": 240000, "retry_options": {"attempts": 1}},
    )
    doc = pymupdf.open(ZH_PDF)
    ocr_log = load_ocr_log()

    print(f"=== BẮT ĐẦU GIAI ĐOẠN 3: OCR HÁN VĂN TRANG {args.start_page} -> {args.end_page} (BATCH SIZE: {args.batch_size}) ===", flush=True)
    print(f"Model Cascade: {CASCADE_MODELS}", flush=True)

    # Check existing pages (checkpoint)
    missing_pages = []
    for p in range(args.start_page, args.end_page + 1):
        target_file = os.path.join(RAW_HAN_DIR, f"page_{p:04d}.txt")
        if os.path.exists(target_file) and os.path.getsize(target_file) > 50:
            pass
        else:
            missing_pages.append(p)

    print(f"Tổng số trang cần OCR: {len(missing_pages)} / {args.end_page - args.start_page + 1} trang.", flush=True)
    if not missing_pages:
        print("Toàn bộ các trang đã có dữ liệu OCR hợp lệ!", flush=True)
        return

    model_idx_ref = [0]
    batch_size = args.batch_size

    for i in range(0, len(missing_pages), batch_size):
        batch = missing_pages[i:i+batch_size]
        success, used_model = ocr_batch_cascading(client, batch, doc, model_idx_ref, ocr_log)
        
        if i + batch_size < len(missing_pages):
            sleep_time = 5 if "lite" in used_model else 13
            print(f"Nghỉ {sleep_time}s tuân thủ rate limit ({used_model})...")
            time.sleep(sleep_time)

    print("\n=== TOÀN BỘ CÁC TRANG ĐÃ HOÀN TẤT OCR THÀNH CÔNG ===")

if __name__ == '__main__':
    main()
