# -*- coding: utf-8 -*-
"""
Generates structured OCR output files (CSV, JSON, XLSX) matching the TA's specification:
Columns:
  1. quyển: File name (e.g., "Ấn Quang Pháp Sư Văn Sao - Zh - 3.pdf")
  2. trang: Page number (1-indexed)
  3. nội dung: "[XXXXaYY] <paragraph/block text>"
  4. ngôn ngữ: "zh" or "vi"
  5. note: Bounding box "(x0, y0) - (x1, y1)" in PDF points (rounded to 1 decimal place)
"""

import os
import sys
import re
import json
import csv
import numpy as np
from PIL import Image
import pymupdf
import pandas as pd
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Dynamic project paths
BASE_DIR = Path(__file__).resolve().parent.parent
BOOK_DIR = BASE_DIR / os.environ.get("BOOK_DIR_NAME", "CV09_AQPSVS_Q3")
METADATA_DIR = BASE_DIR / "metadata"

ZH_PDF_NAME = os.environ.get("ZH_PDF_NAME", "Ấn Quang Pháp Sư Văn Sao - Zh - 3.pdf")
VI_PDF_NAME = os.environ.get("VI_PDF_NAME", "Ấn Quang Pháp Sư Văn Sao - Vi - 3.pdf")

ZH_PDF_PATH = os.environ.get("ZH_PDF_PATH", str(BOOK_DIR / "01_nguon" / "han" / ZH_PDF_NAME))
VI_PDF_PATH = os.environ.get("VI_PDF_PATH", str(BOOK_DIR / "01_nguon" / "viet" / VI_PDF_NAME))

RAW_HAN_DIR = os.environ.get("RAW_HAN_DIR", str(BOOK_DIR / "02_ocr_tho" / "han"))
RAW_VIET_DIR = os.environ.get("RAW_VIET_DIR", str(BOOK_DIR / "02_ocr_tho" / "viet"))
CLEANED_IMG_DIR = os.environ.get("CLEANED_IMG_DIR", str(BOOK_DIR / "02_ocr_tho" / "cleaned_pages"))
OUT_DIR = os.environ.get("OUT_DIR", str(BOOK_DIR / "02_ocr_tho"))
HAN_ARTICLES_JSON = os.environ.get("HAN_ARTICLES_JSON", str(METADATA_DIR / "han_articles.json"))


def load_han_titles():
    titles = {
        "增廣印光法師文鈔",
        "三冊",
        "印光法師文鈔卷第三",
        "序",
        "跋",
        "徹悟禪師念佛伽陀教義百偈（第五十六至七十）",
        "徹悟禪師念佛伽陀教義百偈（第七十一至八十五）",
    }
    if os.path.exists(HAN_ARTICLES_JSON):
        arts = json.load(open(HAN_ARTICLES_JSON, encoding="utf-8"))
        for a in arts:
            titles.add(a["zh_title"].strip())
            # Also add base title without parenthetical note
            base_t = re.sub(r"[（\(].*?[）\)]", "", a["zh_title"]).strip()
            if base_t:
                titles.add(base_t)
    return titles


def segment_han_page_lines(pno, lines, known_titles):
    """Groups lines on a Chinese page into logical blocks (titles vs paragraph blocks)."""
    blocks = []
    cur_lines = []

    for line in lines:
        s = line.strip()
        if not s:
            continue
        # Remove running banxin header if any slipped in
        if re.match(r"^(印光法師文鈔卷三|卷三)\s*[序跋]", s) and len(s) < 20:
            continue

        base_s = re.sub(r"[（\(].*?[）\)]", "", s).strip()
        is_title = (
            s in known_titles
            or base_s in known_titles
            or (len(s) <= 22 and "。" not in s and "、" not in s and (s.endswith("序") or s.endswith("跋") or s in ("序", "跋", "印光法師文鈔卷第三")))
        )
        if is_title:
            if cur_lines:
                blocks.append("".join(cur_lines))
                cur_lines = []
            blocks.append(s)
        else:
            cur_lines.append(s)

    if cur_lines:
        blocks.append("".join(cur_lines))

    return blocks


def compute_han_bboxes(doc_zh, pno, blocks):
    """
    Uses image ink projection on cleaned_pages/page_XXXX.png to compute accurate
    PDF-coordinate bounding boxes (x0, y0) - (x1, y1) for each block on page `pno`
    (reading right-to-left in traditional vertical layout).
    """
    page = doc_zh[pno - 1]
    pw, ph = page.rect.width, page.rect.height

    img_path = os.path.join(CLEANED_IMG_DIR, f"page_{pno:04d}.png")
    if os.path.exists(img_path):
        img = np.array(Image.open(img_path).convert("L"))
    else:
        pix = page.get_pixmap(dpi=200, colorspace=pymupdf.csGRAY)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)

    ih, iw = img.shape
    scale_x = pw / iw
    scale_y = ph / ih

    # Exclude outer border & banxin margin (odd pages: banxin is on left < 12%; even pages: banxin is on right > 88%)
    if pno in (1, 2, 199, 200):
        x_min_px, x_max_px = int(iw * 0.06), int(iw * 0.94)
    elif pno % 2 == 1:
        x_min_px, x_max_px = int(iw * 0.11), int(iw * 0.94)
    else:
        x_min_px, x_max_px = int(iw * 0.06), int(iw * 0.89)

    y_min_px, y_max_px = int(ih * 0.11), int(ih * 0.92)

    roi = img[y_min_px:y_max_px, x_min_px:x_max_px]
    ink_mask = roi < 180

    if np.any(ink_mask):
        ys, xs = np.where(ink_mask)
        tight_x0 = x_min_px + int(np.min(xs))
        tight_x1 = x_min_px + int(np.max(xs))
        tight_y0 = y_min_px + int(np.min(ys))
        tight_y1 = y_min_px + int(np.max(ys))
    else:
        tight_x0, tight_x1 = x_min_px, x_max_px
        tight_y0, tight_y1 = y_min_px, y_max_px

    n_blocks = len(blocks)
    if n_blocks == 0:
        return []
    if n_blocks == 1:
        b = (
            round(tight_x0 * scale_x, 1),
            round(tight_y0 * scale_y, 1),
            round(tight_x1 * scale_x, 1),
            round(tight_y1 * scale_y, 1),
        )
        return [f"({b[0]:.1f}, {b[1]:.1f}) - ({b[2]:.1f}, {b[3]:.1f})"]

    # Partition horizontal width [tight_x0 .. tight_x1] from RIGHT to LEFT across the 11 columns
    total_w = max(tight_x1 - tight_x0, 11)
    col_w = total_w / 11.0

    # Estimate how many columns each block occupies (at least 1 column per title/short block, proportional for body)
    weights = []
    for blk in blocks:
        c_len = len(blk)
        if c_len <= 25:
            weights.append(1.0)
        else:
            weights.append(max(1.0, round(c_len / 38.0, 1)))
    sum_w = sum(weights)
    norm_cols = [w * (11.0 / sum_w) for w in weights]

    bboxes = []
    cur_right_x = float(tight_x1)
    for idx, nc in enumerate(norm_cols):
        blk_w = nc * col_w
        bx1 = cur_right_x
        bx0 = max(float(tight_x0), cur_right_x - blk_w)
        if idx == n_blocks - 1:
            bx0 = float(tight_x0)
        cur_right_x = bx0

        # Refine vertical bounds (y0, y1) inside this horizontal slice [bx0..bx1]
        sx0 = max(0, int(bx0) - x_min_px)
        sx1 = min(roi.shape[1], int(bx1) - x_min_px + 1)
        sub_mask = ink_mask[:, sx0:sx1] if sx1 > sx0 else ink_mask
        if np.any(sub_mask):
            sys_y, _ = np.where(sub_mask)
            by0 = y_min_px + int(np.min(sys_y))
            by1 = y_min_px + int(np.max(sys_y))
        else:
            by0, by1 = tight_y0, tight_y1

        rx0 = round(bx0 * scale_x, 1)
        ry0 = round(by0 * scale_y, 1)
        rx1 = round(bx1 * scale_x, 1)
        ry1 = round(by1 * scale_y, 1)
        bboxes.append(f"({rx0:.1f}, {ry0:.1f}) - ({rx1:.1f}, {ry1:.1f})")

    return bboxes


def extract_han_ocr_rows():
    doc_zh = pymupdf.open(ZH_PDF_PATH)
    known_titles = load_han_titles()
    rows = []

    for pno in range(1, len(doc_zh) + 1):
        txt_file = os.path.join(RAW_HAN_DIR, f"page_{pno:04d}.txt")
        if not os.path.exists(txt_file):
            continue
        raw_text = open(txt_file, encoding="utf-8").read().strip()
        if not raw_text:
            continue

        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        blocks = segment_han_page_lines(pno, lines, known_titles)
        bboxes = compute_han_bboxes(doc_zh, pno, blocks)

        for b_idx, (blk_text, bbox_str) in enumerate(zip(blocks, bboxes), start=1):
            para_id = f"[{pno:04d}a{b_idx:02d}]"
            rows.append({
                "quyển": ZH_PDF_NAME,
                "trang": pno,
                "nội dung": f"{para_id} {blk_text}",
                "ngôn ngữ": "zh",
                "note": bbox_str,
            })

    return rows


def extract_viet_ocr_rows():
    doc_vi = pymupdf.open(VI_PDF_PATH)
    rows = []

    for pno in range(1, len(doc_vi) + 1):
        page = doc_vi[pno - 1]
        d = page.get_text("dict")

        # Collect valid lines with their bounding boxes
        page_lines = []
        for b in d.get("blocks", []):
            if b.get("type") != 0:
                continue
            for l in b.get("lines", []):
                bbox = l["bbox"]
                if pno >= 5 and bbox[1] < 75:
                    continue  # skip running header

                spans_text = []
                max_size = 0.0
                is_bold = False
                flags_val = 4
                for s in l.get("spans", []):
                    sz = s["size"]
                    if pno >= 5 and pno <= 358 and sz < 12.5:
                        continue  # skip superscripts & footnotes in main body
                    txt = s["text"]
                    if txt:
                        spans_text.append(txt)
                        if sz > max_size:
                            max_size = sz
                        if "Bold" in s.get("font", ""):
                            is_bold = True
                        flags_val = s.get("flags", 4)

                line_str = "".join(spans_text).strip()
                line_str = re.sub(r"\s+", " ", line_str)
                if line_str:
                    page_lines.append({
                        "text": line_str,
                        "bbox": bbox,
                        "x0": bbox[0],
                        "y0": bbox[1],
                        "x1": bbox[2],
                        "y1": bbox[3],
                        "is_bold": is_bold,
                        "flags": flags_val,
                    })

        if not page_lines:
            continue

        # Group page_lines into paragraph blocks on this page, tracking union bbox
        para_blocks = []
        cur_texts = []
        cur_boxes = []

        for l in page_lines:
            is_new_block = False
            if l["is_bold"] or (l["x0"] > 85 and l["flags"] == 4) or (l["x0"] > 130 and len(l["text"]) < 60):
                if cur_texts:
                    is_new_block = True

            if is_new_block:
                bx0 = min(b[0] for b in cur_boxes)
                by0 = min(b[1] for b in cur_boxes)
                bx1 = max(b[2] for b in cur_boxes)
                by1 = max(b[3] for b in cur_boxes)
                para_blocks.append((" ".join(cur_texts), (bx0, by0, bx1, by1)))
                cur_texts = []
                cur_boxes = []

            cur_texts.append(l["text"])
            cur_boxes.append(l["bbox"])
            if l["is_bold"]:
                bx0 = min(b[0] for b in cur_boxes)
                by0 = min(b[1] for b in cur_boxes)
                bx1 = max(b[2] for b in cur_boxes)
                by1 = max(b[3] for b in cur_boxes)
                para_blocks.append((" ".join(cur_texts), (bx0, by0, bx1, by1)))
                cur_texts = []
                cur_boxes = []

        if cur_texts:
            bx0 = min(b[0] for b in cur_boxes)
            by0 = min(b[1] for b in cur_boxes)
            bx1 = max(b[2] for b in cur_boxes)
            by1 = max(b[3] for b in cur_boxes)
            para_blocks.append((" ".join(cur_texts), (bx0, by0, bx1, by1)))

        for b_idx, (blk_text, b) in enumerate(para_blocks, start=1):
            para_id = f"[{pno:04d}a{b_idx:02d}]"
            bbox_str = f"({b[0]:.1f}, {b[1]:.1f}) - ({b[2]:.1f}, {b[3]:.1f})"
            rows.append({
                "quyển": VI_PDF_NAME,
                "trang": pno,
                "nội dung": f"{para_id} {blk_text}",
                "ngôn ngữ": "vi",
                "note": bbox_str,
            })

    return rows


def save_structured_outputs(rows, base_path):
    # Save CSV (UTF-8 with BOM so Excel opens Vietnamese/Chinese cleanly)
    csv_path = base_path + ".csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["quyển", "trang", "nội dung", "ngôn ngữ", "note"])
        writer.writeheader()
        writer.writerows(rows)

    # Save JSON
    json_path = base_path + ".json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    # Save XLSX
    xlsx_path = base_path + ".xlsx"
    df = pd.DataFrame(rows)
    df.to_excel(xlsx_path, index=False)

    print(f"Saved {len(rows)} rows -> {os.path.basename(csv_path)}, .json, .xlsx")


def main():
    print("Đang trích xuất bảng kết quả OCR có tọa độ Bounding Box cho bản Hán (zh)...")
    han_rows = extract_han_ocr_rows()
    save_structured_outputs(han_rows, os.path.join(OUT_DIR, "ocr_ket_qua_han"))

    print("Đang trích xuất bảng kết quả OCR có tọa độ Bounding Box cho bản Việt (vi)...")
    viet_rows = extract_viet_ocr_rows()
    save_structured_outputs(viet_rows, os.path.join(OUT_DIR, "ocr_ket_qua_viet"))

    all_rows = han_rows + viet_rows
    save_structured_outputs(all_rows, os.path.join(OUT_DIR, "ocr_ket_qua_toan_bo"))

    print("\n--- MẪU 5 DÒNG ĐẦU BẢN HÁN ---")
    for r in han_rows[:5]:
        print(r)
    print("\n--- MẪU 5 DÒNG ĐẦU BẢN VIỆT ---")
    for r in viet_rows[:5]:
        print(r)


if __name__ == "__main__":
    main()
