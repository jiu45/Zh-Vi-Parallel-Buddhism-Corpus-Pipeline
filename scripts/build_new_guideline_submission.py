# -*- coding: utf-8 -*-
"""
Builds the complete submission package following the New Project Guidelines (PPOCRLabel + Align CSV/XLSX).
Fully portable across Windows / Ubuntu / macOS and reusable for any volume (Q1, Q2, Q3, Q4).

Default Book Folder Name: "An Quang Phap Su Van Sao - Q3"

Directory Structure Generated:
  <REPO_ROOT>/<OUTPUT_BOOK_NAME>/
  |-- ch/
  |   |-- <OUTPUT_BOOK_NAME>.<NNN>.jpg
  |   |-- Label.txt      (PPOCRLabel format, 4-point column boxes right-to-left)
  |   `-- fileState.txt  (PPOCRLabel format, state = 1)
  |-- vi/
  |   |-- <OUTPUT_BOOK_NAME>.<NNN>.jpg
  |   |-- Label.txt      (PPOCRLabel format, 4-point line boxes top-to-bottom, no footnotes)
  |   `-- fileState.txt  (PPOCRLabel format, state = 1)
  |-- intro/
  |   |-- <OUTPUT_BOOK_NAME>.<NNN>.jpg
  |   |-- Label.txt
  |   `-- fileState.txt
  |-- toc/
  |   |-- <OUTPUT_BOOK_NAME>.<NNN>.jpg
  |   |-- Label.txt
  |   `-- fileState.txt
  |-- blank/
  |   `-- <OUTPUT_BOOK_NAME>.<NNN>.jpg
  |-- misc/
  |   `-- <OUTPUT_BOOK_NAME>.<NNN>.jpg
  |-- <OUTPUT_BOOK_NAME>.pdf
  |-- <OUTPUT_BOOK_NAME>_updated.pdf
  |-- <OUTPUT_BOOK_NAME>.csv
  `-- <OUTPUT_BOOK_NAME>.xlsx

Usage (Volume 3 default):
  python scripts/build_new_guideline_submission.py

Usage (Other volumes, e.g. Volume 1):
  python scripts/build_new_guideline_submission.py \
      --book-name "An Quang Phap Su Van Sao - Q1" \
      --src-book-dir "CV09_AQPSVS_Q1" \
      --vi-content-start 5 --vi-content-end 350 \
      --vi-toc-start 351 --vi-toc-end 360
"""

import os
import sys
import re
import json
import csv
import shutil
import argparse
from pathlib import Path
import numpy as np
from PIL import Image
import pymupdf
import openpyxl

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Dynamic project paths (portable across any machine / OS)
BASE_DIR = Path(__file__).resolve().parent.parent
METADATA_DIR = BASE_DIR / "metadata"


def find_first_pdf(directory: Path) -> str:
    if directory.exists():
        pdfs = sorted(directory.glob("*.pdf"))
        if pdfs:
            return str(pdfs[0])
    return ""


def parse_page_set(spec: str) -> set:
    pages = set()
    if not spec or not spec.strip():
        return pages
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            s, e = part.split("-", 1)
            pages.update(range(int(s), int(e) + 1))
        else:
            pages.add(int(part))
    return pages


def clean_han_transcription(text: str) -> str:
    """Follows Text Data Rules for Chinese: no spaces, valid punctuation."""
    return re.sub(r"\s+", "", text).strip()


def clean_viet_transcription(text: str) -> str:
    """Follows Text Data Rules for Vietnamese: clean spaces, remove footnote indices like [1]."""
    t = re.sub(r"\[\d+\]", "", text)
    t = re.sub(r"[\r\n\t]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([,.;:?!])", r"\1", t)
    return t


def split_han_lines_to_columns(raw_lines, max_cells_per_col=35.0):
    """
    Splits raw OCR lines of a woodblock page into vertical columns (~35 grid cells per column).
    Normal CJK char = 1.0 cell, inline small note inside （...） = 0.5 cell, punctuation = 0.0 cell.
    """
    cols = []
    for line in raw_lines:
        line = clean_han_transcription(line)
        if not line:
            continue
        in_paren = False
        total_cells = 0.0
        for ch in line:
            if ch in "（(":
                in_paren = True
            elif ch in "）)":
                in_paren = False
            elif "\u4e00" <= ch <= "\u9fff":
                total_cells += 0.5 if in_paren else 1.0
        if total_cells <= max_cells_per_col + 3.5:
            cols.append(line)
        else:
            cur = []
            cur_cells = 0.0
            in_p = False
            for idx, ch in enumerate(line):
                cur.append(ch)
                if ch in "（(":
                    in_p = True
                elif ch in "）)":
                    in_p = False
                elif "\u4e00" <= ch <= "\u9fff":
                    cur_cells += 0.5 if in_p else 1.0
                next_ch = line[idx + 1] if idx + 1 < len(line) else ""
                if cur_cells >= max_cells_per_col and next_ch not in "。、）》)”":
                    cols.append("".join(cur))
                    cur = []
                    cur_cells = 0.0
            if cur:
                cols.append("".join(cur))
    return cols


def detect_han_column_boxes(img_gray, col_texts, n_max_cols=13):
    """
    Detects tight 4-point bounding boxes [[x1,y1],[x2,y1],[x2,y2],[x1,y2]] in pixel coordinates
    for each vertical column from RIGHT to LEFT, excluding outer frame and 版心 margin.
    """
    w, h = img_gray.size
    arr = np.array(img_gray)
    ink = (arr < 130).astype(np.uint8)

    row_proj = ink[:, int(w * 0.15) : int(w * 0.85)].sum(axis=1)
    top_c = np.where(row_proj[: int(h * 0.25)] > w * 0.35)[0]
    bot_c = np.where(row_proj[int(h * 0.80) :] > w * 0.35)[0] + int(h * 0.80)
    y_top = int(top_c[-1]) + 8 if len(top_c) else int(h * 0.13)
    y_bot = int(bot_c[0]) - 8 if len(bot_c) else int(h * 0.91)

    col_proj = ink[y_top:y_bot, :].sum(axis=0)
    left_margin_hi = min(int(w * 0.12), w - 1)
    left_margin_lo = min(int(w * 0.02), left_margin_hi)
    right_margin_lo = max(0, int(w * 0.88))
    right_margin_hi = max(right_margin_lo + 1, int(w * 0.985))

    left_v = np.where(col_proj[left_margin_lo:left_margin_hi] > 0.60 * (y_bot - y_top))[0] + left_margin_lo
    right_v = np.where(col_proj[right_margin_lo:right_margin_hi] > 0.60 * (y_bot - y_top))[0] + right_margin_lo
    x_left = int(left_v[-1]) + 3 if len(left_v) else int(w * 0.056)
    x_right = int(right_v[0]) - 3 if len(right_v) else int(w * 0.945)

    col_w = (x_right - x_left) / float(n_max_cols)
    char_h = (y_bot - y_top) / 35.0

    slot_boxes = []
    for c_idx in range(n_max_cols):
        cx2 = int(round(x_right - c_idx * col_w))
        cx1 = int(round(x_right - (c_idx + 1) * col_w))
        sub_ink = (arr[y_top:y_bot, max(0, cx1 + 3) : min(w, cx2 - 3)] < 115).astype(np.uint8)
        valid_ys = np.where(sub_ink.sum(axis=1) >= 2)[0]
        valid_xs = np.where(sub_ink.sum(axis=0) >= 2)[0]
        ink_pixels = int(sub_ink.sum())
        if len(valid_ys) > 4 and len(valid_xs) > 2:
            by1 = max(y_top, y_top + int(valid_ys[0]) - 4)
            by2 = min(y_bot, y_top + int(valid_ys[-1]) + 4)
            bx1 = cx1 + 3 + int(valid_xs[0]) - 3
            bx2 = cx1 + 3 + int(valid_xs[-1]) + 3
        else:
            by1, by2, bx1, bx2 = y_top, y_bot, cx1 + 2, cx2 - 2
        slot_boxes.append((bx1, by1, bx2, by2, ink_pixels))

    n_texts = len(col_texts)
    if n_texts <= n_max_cols:
        if n_texts < n_max_cols:
            ranked_indices = sorted(range(n_max_cols), key=lambda i: slot_boxes[i][4], reverse=True)[:n_texts]
            chosen_indices = sorted(ranked_indices)
        else:
            chosen_indices = list(range(n_max_cols))
    else:
        chosen_indices = [min(i, n_max_cols - 1) for i in range(n_texts)]

    annotations = []
    for idx, txt in enumerate(col_texts):
        s_idx = chosen_indices[idx]
        bx1, by1, bx2, by2, _ = slot_boxes[s_idx]
        in_p = False
        n_cells = 0.0
        for ch in txt:
            if ch in "（(":
                in_p = True
            elif ch in "）)":
                in_p = False
            elif "\u4e00" <= ch <= "\u9fff":
                n_cells += 0.5 if in_p else 1.0
        if n_cells < 33.0:
            max_y2 = int(by1 + (n_cells + 1.0) * char_h)
            by2 = max(by1 + 16, min(by2, max_y2))

        points = [[int(bx1), int(by1)], [int(bx2), int(by1)], [int(bx2), int(by2)], [int(bx1), int(by2)]]
        annotations.append({"transcription": txt, "points": points})

    return annotations


def step1_and_2_export_images_and_ppocr_labels(cfg):
    print("=== BƯỚC 1 & 2: XUẤT HÌNH ẢNH .JPG, PHÂN LOẠI THƯ MỤC & TẠO LABEL.TXT (PPOCRLABEL) ===", flush=True)
    book_dir = cfg["out_book_dir"]
    book_name = cfg["book_name"]

    for sub in ["ch", "vi", "intro", "toc", "blank", "misc"]:
        os.makedirs(book_dir / sub, exist_ok=True)

    zh_doc = pymupdf.open(cfg["zh_pdf_src"])
    vi_doc = pymupdf.open(cfg["vi_pdf_src"])

    ch_labels, ch_states = [], []
    intro_labels, intro_states = [], []
    updated_pdf_images = []

    zh_intro_pages = cfg["zh_intro_pages"]
    zh_blank_pages = cfg["zh_blank_pages"]
    zh_misc_pages = cfg["zh_misc_pages"]

    # 1. Process all pages of Chinese PDF
    for p in range(1, len(zh_doc) + 1):
        img_name = f"{book_name}.{p:03d}.jpg"
        cleaned_png = cfg["cleaned_img_dir"] / f"page_{p:04d}.png"
        if cleaned_png.exists():
            pil_img = Image.open(cleaned_png).convert("RGB")
        else:
            pix = zh_doc[p - 1].get_pixmap(dpi=200)
            pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        updated_pdf_images.append(pil_img)

        raw_txt_path = cfg["raw_han_dir"] / f"page_{p:04d}.txt"
        raw_lines = []
        if raw_txt_path.exists():
            raw_lines = [
                l.strip()
                for l in raw_txt_path.read_text(encoding="utf-8").splitlines()
                if l.strip()
            ]

        if p in zh_misc_pages:
            pil_img.save(book_dir / "misc" / img_name, "JPEG", quality=92)
        elif p in zh_intro_pages:
            pil_img.save(book_dir / "intro" / img_name, "JPEG", quality=92)
            col_texts = split_han_lines_to_columns(raw_lines)
            anns = detect_han_column_boxes(pil_img.convert("L"), col_texts, n_max_cols=11)
            rel_path = f"intro/{img_name}"
            intro_labels.append(f"{rel_path}\t{json.dumps(anns, ensure_ascii=False)}")
            intro_states.append(f"{rel_path}\t1")
        elif p in zh_blank_pages:
            pil_img.save(book_dir / "blank" / img_name, "JPEG", quality=92)
        else:
            pil_img.save(book_dir / "ch" / img_name, "JPEG", quality=92)
            col_texts = split_han_lines_to_columns(raw_lines)
            anns = detect_han_column_boxes(pil_img.convert("L"), col_texts, n_max_cols=13)
            rel_path = f"ch/{img_name}"
            ch_labels.append(f"{rel_path}\t{json.dumps(anns, ensure_ascii=False)}")
            ch_states.append(f"{rel_path}\t1")

    (book_dir / "ch" / "Label.txt").write_text("\n".join(ch_labels) + "\n", encoding="utf-8")
    (book_dir / "ch" / "fileState.txt").write_text("\n".join(ch_states) + "\n", encoding="utf-8")

    if intro_labels:
        (book_dir / "intro" / "Label.txt").write_text("\n".join(intro_labels) + "\n", encoding="utf-8")
        (book_dir / "intro" / "fileState.txt").write_text("\n".join(intro_states) + "\n", encoding="utf-8")

    print(f"-> Đã tạo xong ch/ ({len(ch_labels)} ảnh + Label.txt + fileState.txt)", flush=True)
    print(f"-> Đã tạo xong intro/ ({len(intro_labels)} ảnh), blank/ ({len(zh_blank_pages)} ảnh)", flush=True)

    # Save original PDF and _updated.pdf (merged from preprocessed images without duplicates)
    orig_pdf_dst = book_dir / f"{book_name}.pdf"
    shutil.copy2(cfg["zh_pdf_src"], orig_pdf_dst)
    updated_pdf_dst = book_dir / f"{book_name}_updated.pdf"
    if updated_pdf_images:
        updated_pdf_images[0].save(
            updated_pdf_dst,
            "PDF",
            resolution=200.0,
            save_all=True,
            append_images=updated_pdf_images[1:],
        )
    print(f"-> Đã xuất {orig_pdf_dst.name} và {updated_pdf_dst.name} ({len(updated_pdf_images)} trang, không trùng lặp).", flush=True)

    # 2. Process all pages of Vietnamese PDF
    vi_labels, vi_states = [], []
    toc_labels, toc_states = [], []
    scale = 2.0

    vi_c_start, vi_c_end = cfg["vi_content_start"], cfg["vi_content_end"]
    vi_t_start, vi_t_end = cfg["vi_toc_start"], cfg["vi_toc_end"]

    for p in range(1, len(vi_doc) + 1):
        page = vi_doc[p - 1]
        img_name = f"{book_name}.{p:03d}.jpg"
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale))
        pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        is_vi_content = vi_c_start <= p <= vi_c_end
        is_vi_toc = (vi_t_start > 0) and (vi_t_start <= p <= vi_t_end)

        if not is_vi_content and not is_vi_toc:
            if p in zh_misc_pages or p in zh_intro_pages or p in zh_blank_pages:
                dst = book_dir / "misc" / f"{book_name}.vi_{p:03d}.jpg"
            else:
                dst = book_dir / "misc" / img_name
            pil_img.save(dst, "JPEG", quality=90)
            continue

        # Extract line-level bounding boxes via PyMuPDF (excluding header, page num, footnotes & superscript indices)
        d = page.get_text("dict")
        raw_lines = []
        min_font_size = 12.0 if is_vi_content else 9.0
        for b in d.get("blocks", []):
            if b.get("type") != 0:
                continue
            for l in b.get("lines", []):
                bbox = l["bbox"]
                if bbox[1] < 62 or bbox[1] > 530:
                    continue
                valid_spans = [s for s in l.get("spans", []) if s.get("size", 0) >= min_font_size]
                if not valid_spans:
                    continue
                txt = "".join(s["text"] for s in valid_spans)
                txt_clean = clean_viet_transcription(txt)
                if not txt_clean:
                    continue
                if re.match(r"^\d+$", txt_clean) or "Ấn Quang Pháp Sư Văn Sao" in txt_clean:
                    continue
                x0 = min(s["bbox"][0] for s in valid_spans)
                y0 = min(s["bbox"][1] for s in valid_spans)
                x1 = max(s["bbox"][2] for s in valid_spans)
                y1 = max(s["bbox"][3] for s in valid_spans)
                raw_lines.append((x0, y0, x1, y1, txt_clean))

        raw_lines.sort(key=lambda x: (round(x[1], 1), x[0]))
        merged_lines = []
        for item in raw_lines:
            if merged_lines and abs(item[1] - merged_lines[-1][1]) < 4.0:
                prev = merged_lines[-1]
                merged_lines[-1] = (
                    min(prev[0], item[0]),
                    min(prev[1], item[1]),
                    max(prev[2], item[2]),
                    max(prev[3], item[3]),
                    clean_viet_transcription(prev[4] + " " + item[4]),
                )
            else:
                merged_lines.append(item)

        anns = []
        for x0, y0, x1, y1, txt_clean in merged_lines:
            px1 = max(0, int(round(x0 * scale)) - 2)
            py1 = max(0, int(round(y0 * scale)) - 2)
            px2 = min(pix.width, int(round(x1 * scale)) + 2)
            py2 = min(pix.height, int(round(y1 * scale)) + 2)
            anns.append({"transcription": txt_clean, "points": [[px1, py1], [px2, py1], [px2, py2], [px1, py2]]})

        if is_vi_content:
            pil_img.save(book_dir / "vi" / img_name, "JPEG", quality=90)
            rel_path = f"vi/{img_name}"
            vi_labels.append(f"{rel_path}\t{json.dumps(anns, ensure_ascii=False)}")
            vi_states.append(f"{rel_path}\t1")
        elif is_vi_toc:
            pil_img.save(book_dir / "toc" / img_name, "JPEG", quality=90)
            rel_path = f"toc/{img_name}"
            toc_labels.append(f"{rel_path}\t{json.dumps(anns, ensure_ascii=False)}")
            toc_states.append(f"{rel_path}\t1")

    (book_dir / "vi" / "Label.txt").write_text("\n".join(vi_labels) + "\n", encoding="utf-8")
    (book_dir / "vi" / "fileState.txt").write_text("\n".join(vi_states) + "\n", encoding="utf-8")

    if toc_labels:
        (book_dir / "toc" / "Label.txt").write_text("\n".join(toc_labels) + "\n", encoding="utf-8")
        (book_dir / "toc" / "fileState.txt").write_text("\n".join(toc_states) + "\n", encoding="utf-8")

    print(f"-> Đã tạo xong vi/ ({len(vi_labels)} ảnh + Label.txt + fileState.txt)", flush=True)
    print(f"-> Đã tạo xong toc/ ({len(toc_labels)} ảnh + Label.txt + fileState.txt)", flush=True)


def step3_export_alignment_csv_and_xlsx(cfg):
    print("\n=== BƯỚC 3: XUẤT FILE DÓNG HÀNG <TÊN SÁCH>.CSV VÀ <TÊN SÁCH>.XLSX ===", flush=True)
    book_dir = cfg["out_book_dir"]
    book_name = cfg["book_name"]

    cache = json.loads(cfg["cache_json"].read_text(encoding="utf-8"))
    han_arts = json.loads(cfg["han_articles_json"].read_text(encoding="utf-8"))
    viet_arts = json.loads(cfg["viet_articles_json"].read_text(encoding="utf-8"))

    # Build character stream from Chinese content pages to map each aligned sentence to its exact page
    zh_doc = pymupdf.open(cfg["zh_pdf_src"])
    skip_zh = cfg["zh_misc_pages"] | cfg["zh_intro_pages"] | cfg["zh_blank_pages"]
    content_pages = [p for p in range(1, len(zh_doc) + 1) if p not in skip_zh]

    page_spans = []
    stream_parts = []
    cur_len = 0
    for p in content_pages:
        raw_txt_path = cfg["raw_han_dir"] / f"page_{p:04d}.txt"
        if not raw_txt_path.exists():
            continue
        lines = [
            re.sub(r"\s+", "", l.strip())
            for l in raw_txt_path.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        page_str = "".join(lines)
        page_str = re.sub(
            r"感應之[）\)](?:[（\(])?運、?微妙難思、?略書、?便?概、?以勖來哲、?[）\)]",
            "感應之道、微妙難思、略書梗概、以勖來哲。）",
            page_str,
        )
        start_idx = cur_len
        stream_parts.append(page_str)
        cur_len += len(page_str)
        page_spans.append((start_idx, cur_len, p))

    full_stream = "".join(stream_parts)
    last_content_page = content_pages[-1] if content_pages else 1

    def find_page_for_offset(char_offset):
        for s_idx, e_idx, p_num in page_spans:
            if s_idx <= char_offset < e_idx:
                return p_num
        return last_content_page

    # Map section names to Chinese/Vietnamese headers automatically
    SECTION_HEADER_MAP = {
        "TỰ": ("序", "IV. TỰ"),
        "BẠT": ("跋", "V. BẠT"),
    }

    all_pairs = []
    prev_section = None
    total_articles = min(len(han_arts), len(viet_arts))
    for gid in range(1, total_articles + 1):
        sec = han_arts[gid - 1].get("section", "")
        if sec and sec != prev_section:
            if sec in SECTION_HEADER_MAP:
                all_pairs.append(SECTION_HEADER_MAP[sec])
            prev_section = sec
        h_title = clean_han_transcription(han_arts[gid - 1].get("zh_title", ""))
        v_title = clean_viet_transcription(viet_arts[gid - 1].get("vi_title", ""))
        if h_title and v_title:
            all_pairs.append((h_title, v_title))
        for zh_c, vi_c in cache.get(str(gid), []):
            zh_cl = clean_han_transcription(zh_c)
            vi_cl = clean_viet_transcription(vi_c)
            if zh_cl and vi_cl:
                all_pairs.append((zh_cl, vi_cl))

    rows_3col = []
    rows_4col = []
    search_cursor = 0
    page_sentence_counts = {}

    for zh_clean, vi_clean in all_pairs:
        probe = zh_clean[: min(10, len(zh_clean))]
        probe_noparen = re.sub(r"[（\(].*?[）\)]", "", probe)
        pos = full_stream.find(probe, max(0, search_cursor - 50))
        if pos == -1 and probe_noparen:
            pos = full_stream.find(probe_noparen[:6], max(0, search_cursor - 150))
        if pos != -1 and pos - search_cursor < 1500:
            search_cursor = pos + len(probe_noparen)
        else:
            pos = search_cursor

        p_num = find_page_for_offset(pos)
        page_sentence_counts[p_num] = page_sentence_counts.get(p_num, 0) + 1
        s_idx = page_sentence_counts[p_num]

        img_id = f"{book_name}.{p_num:03d}.jpg"
        sentence_id = f"{book_name}.{p_num:03d}.{s_idx}"

        rows_3col.append([img_id, sentence_id, vi_clean])
        rows_4col.append([img_id, sentence_id, zh_clean, vi_clean])

    # 1. Save <Tên sách>.csv and <Tên sách>.xlsx (3 columns as in Guideline specification)
    csv_path = book_dir / f"{book_name}.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["img_id", "sentence_id", "ChuQN_txt"])
        writer.writerows(rows_3col)

    xlsx_path = book_dir / f"{book_name}.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Align"
    ws.append(["img_id", "sentence_id", "ChuQN_txt"])
    for r in rows_3col:
        ws.append(r)
    wb.save(xlsx_path)

    # 2. Save 4-column backup (with ChuHan_txt) in extras directory
    extras_dir = cfg["extras_dir"]
    os.makedirs(extras_dir, exist_ok=True)
    csv_4col_path = extras_dir / f"{book_name}_4cot_Han_Viet.csv"
    with open(csv_4col_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["img_id", "sentence_id", "ChuHan_txt", "ChuQN_txt"])
        writer.writerows(rows_4col)

    xlsx_4col_path = extras_dir / f"{book_name}_4cot_Han_Viet.xlsx"
    wb4 = openpyxl.Workbook()
    ws4 = wb4.active
    ws4.title = "Align"
    ws4.append(["img_id", "sentence_id", "ChuHan_txt", "ChuQN_txt"])
    for r in rows_4col:
        ws4.append(r)
    wb4.save(xlsx_4col_path)

    print(f"-> Đã xuất {csv_path} ({len(rows_3col)} dòng)", flush=True)
    print(f"-> Đã xuất {xlsx_path} ({len(rows_3col)} dòng)", flush=True)
    print(f"-> Đã xuất bản dự phòng 4 cột (có cột ChuHan_txt) tại {extras_dir}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Build New Guideline Submission Package (PPOCRLabel + Align CSV/XLSX)")
    parser.add_argument("--book-name", default=os.environ.get("OUTPUT_BOOK_NAME", "An Quang Phap Su Van Sao - Q3"))
    parser.add_argument("--src-book-dir", default=os.environ.get("BOOK_DIR_NAME", "CV09_AQPSVS_Q3"))
    parser.add_argument("--zh-pdf", default=os.environ.get("ZH_PDF_PATH", ""))
    parser.add_argument("--vi-pdf", default=os.environ.get("VI_PDF_PATH", ""))
    parser.add_argument("--cleaned-img-dir", default=os.environ.get("CLEANED_DIR", ""))
    parser.add_argument("--zh-misc-pages", default="1", help="Comma-separated Chinese cover/misc pages (e.g. '1')")
    parser.add_argument("--zh-intro-pages", default="2,199", help="Comma-separated Chinese intro/verse pages")
    parser.add_argument("--zh-blank-pages", default="200", help="Comma-separated Chinese blank pages")
    parser.add_argument("--vi-content-start", type=int, default=5)
    parser.add_argument("--vi-content-end", type=int, default=357)
    parser.add_argument("--vi-toc-start", type=int, default=358)
    parser.add_argument("--vi-toc-end", type=int, default=367)
    args = parser.parse_args()

    src_book_dir = Path(args.src_book_dir)
    if not src_book_dir.is_absolute():
        src_book_dir = BASE_DIR / src_book_dir

    zh_pdf = args.zh_pdf or find_first_pdf(src_book_dir / "01_nguon" / "han")
    vi_pdf = args.vi_pdf or find_first_pdf(src_book_dir / "01_nguon" / "viet")
    cleaned_img_dir = Path(args.cleaned_img_dir) if args.cleaned_img_dir else (src_book_dir / "02_ocr_tho" / "cleaned_pages")

    if not zh_pdf or not os.path.exists(zh_pdf):
        raise FileNotFoundError(f"Không tìm thấy file PDF Hán: {zh_pdf}")
    if not vi_pdf or not os.path.exists(vi_pdf):
        raise FileNotFoundError(f"Không tìm thấy file PDF Việt: {vi_pdf}")

    cfg = {
        "book_name": args.book_name,
        "out_book_dir": BASE_DIR / args.book_name,
        "zh_pdf_src": zh_pdf,
        "vi_pdf_src": vi_pdf,
        "raw_han_dir": src_book_dir / "02_ocr_tho" / "han",
        "cleaned_img_dir": cleaned_img_dir,
        "cache_json": METADATA_DIR / "aligned_articles_cache.json",
        "han_articles_json": METADATA_DIR / "han_articles.json",
        "viet_articles_json": METADATA_DIR / "viet_articles.json",
        "extras_dir": BASE_DIR / "extras_q3",
        "zh_misc_pages": parse_page_set(args.zh_misc_pages),
        "zh_intro_pages": parse_page_set(args.zh_intro_pages),
        "zh_blank_pages": parse_page_set(args.zh_blank_pages),
        "vi_content_start": args.vi_content_start,
        "vi_content_end": args.vi_content_end,
        "vi_toc_start": args.vi_toc_start,
        "vi_toc_end": args.vi_toc_end,
    }

    step1_and_2_export_images_and_ppocr_labels(cfg)
    step3_export_alignment_csv_and_xlsx(cfg)
    print(f"\n=== HOÀN TẤT XÂY DỰNG GÓI DỮ LIỆU CHUẨN GUIDELINE MỚI TẠI: {cfg['out_book_dir']} ===", flush=True)


if __name__ == "__main__":
    main()
