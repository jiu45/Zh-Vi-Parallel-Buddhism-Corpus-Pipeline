# -*- coding: utf-8 -*-
"""
Phase 2: Raw Extraction & Complete Cleaning of Vietnamese Text (Configured for Volume 2)
- Step 2.1: Extract raw text of all pages to 02_ocr_tho/viet/page_XXXX.txt
- Step 2.2: Extract & clean main body using font size, coordinates, and anchor_map.json
- Step 2.3: Structure into articles in metadata/viet_articles.json & 03_text_sach/viet.txt
- Step 2.4: Automated QA and verification against anchor_map.json
"""

import os
import sys
import io
import re
import json
import argparse
from collections import Counter
from pathlib import Path
import pymupdf

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Dynamic project paths
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_BOOK_DIR = BASE_DIR / os.environ.get("BOOK_DIR_NAME", "CV09_AQPSVS_Q2")
METADATA_DIR = BASE_DIR / "metadata"


def find_pdf_by_pattern(directory: Path, preferred_name: str) -> str:
    preferred = directory / preferred_name
    if preferred.exists():
        return str(preferred)
    if directory.exists():
        pdfs = sorted(directory.glob("*.pdf"))
        if pdfs:
            return str(pdfs[0])
    return str(preferred)


def is_running_header(line: str) -> bool:
    upper = line.upper().strip()
    if "ẤN QUANG PHÁP SƯ VĂN SAO" in upper:
        return True
    if re.match(r"^TĂNG QUẢNG CHÁNH BIÊN\s*-\s*QUYỂN\s+[IVX0-9]+$", upper):
        return True
    if re.match(r"^QUYỂN\s+(I|II|III|IV|1|2|3|4|NHẤT|NHỊ|TAM|TỨ)$", upper):
        return True
    return False


def parse_section_header(line: str, known_sections: set):
    """
    Matches Roman numeral section headers (e.g. 'I. THƯ TỪ', 'II. THƯ TỪ (Tiếp theo)')
    or standalone known section headers from anchor_map.
    """
    clean = line.strip()
    m = re.match(r"^([IVX]+)\.\s+([^\d\(\)]+?)(?:\s*\(.*\))?$", clean)
    if m and len(m.group(2).strip()) >= 2:
        sec_norm = m.group(2).strip().upper()
        if len(sec_norm) <= 30:
            return sec_norm, clean
    upper = re.sub(r"\s*\(.*\)$", "", clean).strip().upper()
    if upper in known_sections:
        return upper, clean
    return None, None


def step2_1_extract_raw_pages(doc, raw_viet_dir: str):
    """Step 2.1: Extract raw text of all pages into 02_ocr_tho/viet/page_XXXX.txt."""
    total_pages = len(doc)
    print(f"--- Bước 2.1: Trích xuất thô {total_pages} trang tiếng Việt ---")
    os.makedirs(raw_viet_dir, exist_ok=True)
    for pno in range(total_pages):
        page = doc[pno]
        raw_text = page.get_text("text")
        out_path = os.path.join(raw_viet_dir, f"page_{pno + 1:04d}.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(raw_text)
    print(f"-> Đã lưu thành công {total_pages} file thô vào {raw_viet_dir}")


def clean_spacing(text: str) -> str:
    """Normalize whitespace and punctuation spacing, protecting numbers and abbreviations."""
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    # Normalize v.v. and v.v..
    text = re.sub(r"\bv\.\s*v\.\s*\.", "v.v..", text)
    text = re.sub(r"\bv\.\s*v\.", "v.v.", text)
    # Remove space before punctuation
    text = re.sub(r'\s+([,.;:!?\)\]”"’\'])', r"\1", text)
    # Comma spacing: only when followed by letter or quote, not between digits
    text = re.sub(r',(?=[a-zA-ZÀ-ỹ“"\'])', ", ", text)
    # Period spacing: only when followed by uppercase letter or quote/bracket, NOT digit or lowercase
    text = re.sub(r'(?<!\d)\.(?=[A-ZÀ-Ỹ“"\'\(\[])', ". ", text)
    # Semicolon spacing
    text = re.sub(r';(?=[a-zA-ZÀ-ỹ0-9“"\'])', "; ", text)
    # Colon spacing (not between digits)
    text = re.sub(r':(?=[a-zA-ZÀ-ỹ“"\'])', ": ", text)
    # Exclamation and question mark
    text = re.sub(r'([!?])(?=[a-zA-ZÀ-ỹ0-9“"\'])', r"\1 ", text)
    # Remove space after opening quotes/brackets
    text = re.sub(r'([\(“"‘\[])\s+', r"\1", text)
    # Re-normalize v.v.
    text = re.sub(r"\bv\.\s*v\.", "v.v.", text)
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    return text.strip()


def split_sentences_viet(text: str):
    """Split Vietnamese paragraph into clean sentences, protecting decimal/thousand numbers and v.v."""
    text = text.strip()
    if not text:
        return []

    # 1. Protect numbers with dots (e.g. 1.300, 1.800, 2.000)
    text = re.sub(r"(\d+)\.(\d+)", r"\1@NUMDOT@\2", text)

    # 2. Protect v.v. inside sentence
    text = re.sub(r"\bv\.v\.(?=\s+[a-zà-ỹ])", "@VV_LOWER@", text)
    text = re.sub(r"\bv\.v\.(?=,)", "@VV_COMMA@", text)
    text = re.sub(r"\bv\.v\.(?=;)", "@VV_SEMI@", text)
    text = re.sub(r'\bv\.v\.(?=\s*[\)\]”"’\']\s+[a-zà-ỹ])', "@VV_CLOSE_LOWER@", text)

    # 3. Handle double-dot v.v.. at end of sentence
    text = re.sub(r"\bv\.v\.\.", "@VV_END@.", text)

    pattern = r'([.?!]+[”"\'\)\]]*)(?=\s+[A-ZÀ-Ỹ“"\'\(]|$)'
    parts = re.split(pattern, text)
    sentences = []
    i = 0
    while i < len(parts):
        chunk = parts[i].strip()
        if not chunk:
            i += 1
            continue
        punct = ""
        if i + 1 < len(parts):
            punct = parts[i + 1].strip()
            i += 2
        else:
            i += 1

        sent = (chunk + (" " + punct if punct and not chunk.endswith(punct) else punct)).strip()
        sent = sent.replace("@NUMDOT@", ".")
        sent = sent.replace("@VV_LOWER@", "v.v.")
        sent = sent.replace("@VV_COMMA@", "v.v.")
        sent = sent.replace("@VV_SEMI@", "v.v.")
        sent = sent.replace("@VV_CLOSE_LOWER@", "v.v.")
        sent = sent.replace("@VV_END@", "v.v.")
        sent = clean_spacing(sent)
        if sent:
            sentences.append(sent)

    return sentences


def join_lines_to_para(lines):
    """Join physical lines in paragraph, respecting hyphenation."""
    if not lines:
        return ""
    result = lines[0].strip()
    for l in lines[1:]:
        l_str = l.strip()
        if not l_str:
            continue
        if result.endswith("-"):
            if result.endswith(" -"):
                result = result + " " + l_str
            else:
                result = result + l_str
        else:
            result = result + " " + l_str
    return clean_spacing(result)


def step2_2_and_2_3_clean_and_structure(
    doc,
    anchor_map,
    viet_articles_json: str,
    clean_viet_txt: str,
    body_start: int,
    body_end: int,
):
    """Step 2.2 & 2.3: Clean main text and structure into articles matching anchor_map."""
    expected_count = len(anchor_map)
    print(f"--- Bước 2.2 & 2.3: Làm sạch và cấu trúc {expected_count} bài văn tiếng Việt (Trang {body_start} -> {body_end}) ---")

    anchor_lookup = {(a["section"], a["article_num"]): a for a in anchor_map}
    num_lookup = {a["article_num"]: a for a in anchor_map}
    known_sections = {a["section"] for a in anchor_map}

    cur_section = anchor_map[0]["section"] if anchor_map else "THƯ TỪ"
    section_display_headers = {}

    all_pages_lines = []
    for pno in range(body_start - 1, min(body_end, len(doc))):
        page = doc[pno]
        blocks = page.get_text("dict")["blocks"]
        page_lines = []
        for b in blocks:
            if "lines" not in b:
                continue
            for l in b["lines"]:
                if l["bbox"][1] < 75:  # skip running header
                    continue
                # Skip footnote spans and superscript index numbers (size < 12.5)
                spans = [s for s in l["spans"] if s["size"] >= 12.5]
                if not spans:
                    continue
                txt = "".join(s["text"] for s in spans).strip()
                if not txt or is_running_header(txt):
                    continue

                sec_norm, raw_header = parse_section_header(txt, known_sections)
                if sec_norm:
                    cur_section = sec_norm
                    if sec_norm not in section_display_headers:
                        section_display_headers[sec_norm] = raw_header
                    continue

                s0 = spans[0]
                is_bold = bool(s0["flags"] & 16 or "Bold" in s0["font"])
                m = re.match(r"^(\d+)\.\s*(.*)", txt)
                is_title = bool(m and s0["size"] >= 14.0 and is_bold)
                num = int(m.group(1)) if is_title else None

                page_lines.append({
                    "pno": pno + 1,
                    "x0": l["bbox"][0],
                    "y0": l["bbox"][1],
                    "text": txt,
                    "is_title_start": is_title,
                    "title_num": num,
                    "section": cur_section,
                    "is_bold": is_bold,
                    "flags": s0["flags"],
                })
        all_pages_lines.append(page_lines)

    flat_lines = [l for pl in all_pages_lines for l in pl]

    articles = []
    cur_article = None
    cur_para_lines = []

    idx = 0
    while idx < len(flat_lines):
        line = flat_lines[idx]

        if line["is_title_start"]:
            if cur_para_lines:
                para_text = join_lines_to_para(cur_para_lines)
                if para_text and cur_article:
                    cur_article["paragraphs"].append(para_text)
                cur_para_lines = []

            sec = line["section"]
            num = line["title_num"]
            anchor = anchor_lookup.get((sec, num)) or num_lookup.get(num)
            if anchor is None:
                raise KeyError(f"Không tìm thấy điểm neo trong anchor_map cho section='{sec}', article_num={num} (trang {line['pno']})")

            cur_article = {
                "global_id": anchor["global_id"],
                "section": anchor["section"],
                "article_num": num,
                "vi_title": anchor["vi_title"],
                "vi_start_page": anchor["vi_start_page"],
                "vi_end_page": anchor["vi_end_page"],
                "paragraphs": [],
                "sentences": [],
            }
            articles.append(cur_article)

            # Skip title and subtitle lines
            idx += 1
            while idx < len(flat_lines):
                nline = flat_lines[idx]
                if nline["is_title_start"]:
                    break
                if nline["text"].strip() in anchor["vi_title"]:
                    idx += 1
                    continue
                if nline["x0"] > 85 and nline["flags"] == 4:
                    break
                if nline["flags"] == 6 or nline["text"].startswith("("):
                    if nline["text"].strip("()") in anchor["vi_title"]:
                        idx += 1
                        continue
                idx += 1
            continue

        # Check for verse lines (kệ/tụng/thơ indented > 130 and len < 60)
        is_verse = line["x0"] > 130 and len(line["text"]) < 60 and not line["is_bold"]
        if is_verse:
            if cur_para_lines:
                para_text = join_lines_to_para(cur_para_lines)
                if para_text and cur_article:
                    cur_article["paragraphs"].append(para_text)
                cur_para_lines = []
            if cur_article:
                cur_article["paragraphs"].append(clean_spacing(line["text"]))
            idx += 1
            continue

        if line["x0"] > 85 and line["flags"] == 4:  # Indented regular line: start of new paragraph
            if cur_para_lines:
                para_text = join_lines_to_para(cur_para_lines)
                if para_text and cur_article:
                    cur_article["paragraphs"].append(para_text)
                cur_para_lines = []
            cur_para_lines.append(line["text"])
        else:
            cur_para_lines.append(line["text"])

        idx += 1

    # Close last paragraph
    if cur_para_lines and cur_article:
        para_text = join_lines_to_para(cur_para_lines)
        if para_text:
            cur_article["paragraphs"].append(para_text)

    # Post-processing: Remove duplicate subtitles and split into sentences
    for art in articles:
        cleaned_paras = []
        for p in art["paragraphs"]:
            p_clean = clean_spacing(p)
            if p_clean in art["vi_title"] or p_clean.strip("()") in art["vi_title"]:
                print(f"-> Đã loại bỏ dòng phụ đề trùng lặp trong Bài {art['global_id']}: '{p_clean}'")
                continue
            cleaned_paras.append(p_clean)
        art["paragraphs"] = cleaned_paras

        art["sentences"] = []
        for p in art["paragraphs"]:
            sents = split_sentences_viet(p)
            art["sentences"].extend(sents)

    total_paragraphs = sum(len(a["paragraphs"]) for a in articles)
    total_sentences = sum(len(a["sentences"]) for a in articles)
    print(f"-> Tổng số bài trích xuất: {len(articles)}")
    print(f"-> Tổng số đoạn văn sạch: {total_paragraphs}")
    print(f"-> Tổng số câu sạch: {total_sentences}")

    # Save viet_articles.json
    os.makedirs(os.path.dirname(viet_articles_json), exist_ok=True)
    with open(viet_articles_json, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"-> Đã lưu cấu trúc chi tiết {len(articles)} bài vào {viet_articles_json}")

    # Save 03_text_sach/viet.txt
    os.makedirs(os.path.dirname(clean_viet_txt), exist_ok=True)
    with open(clean_viet_txt, "w", encoding="utf-8") as f:
        prev_sec = None
        for a_idx, art in enumerate(articles):
            sec = art["section"]
            if sec != prev_sec:
                header_txt = section_display_headers.get(sec, sec)
                f.write(f"{header_txt}\n\n")
                prev_sec = sec
            f.write(f"{art['vi_title']}\n\n")
            for para in art["paragraphs"]:
                f.write(f"{para}\n\n")
            if a_idx < len(articles) - 1:
                f.write("\n")
    print(f"-> Đã lưu văn bản sạch hoàn chỉnh vào {clean_viet_txt}")

    return articles


def step2_4_automated_qa(articles, anchor_map, clean_viet_txt: str):
    """Step 2.4: Automated QA and verification checks."""
    print("--- Bước 2.4: Kiểm tra chất lượng tự động (QA) ---")

    expected_count = len(anchor_map)
    assert len(articles) == expected_count, f"Lỗi: Số bài là {len(articles)}, không khớp anchor_map ({expected_count})!"

    sec_counts = Counter(a["section"] for a in articles)
    sec_summary = ", ".join(f"{k}: {v}" for k, v in sec_counts.items())

    empty_arts = [a["global_id"] for a in articles if len(a["paragraphs"]) == 0]
    assert len(empty_arts) == 0, f"Lỗi: Có bài rỗng: {empty_arts}"
    min_sentences = min(len(a["sentences"]) for a in articles)
    print(f"  [QA 1] Đạt: Đúng {len(articles)} bài ({sec_summary}). Không có bài rỗng. Min câu/bài = {min_sentences}.")

    # QA 2: Superscript footnote attachment check
    footnote_hits = []
    for a in articles:
        for s in a["sentences"]:
            matches = re.findall(r"\b([a-zA-ZÀ-ỹ]+)(\d+)\b", s)
            if matches:
                footnote_hits.append((a["global_id"], matches))
    if footnote_hits:
        print(f"  [QA 2 - CẢNH BÁO] Phát hiện {len(footnote_hits)} câu có chữ dính số (kiểm tra xem có phải số chú thích sót): {footnote_hits[:5]}")
    else:
        print("  [QA 2] Đạt tuyệt đối: 0% số chú thích sót (không còn chữ dính số).")

    # QA 3: Header leakage
    header_hits = []
    for a in articles:
        for p in a["paragraphs"]:
            if "ẤN QUANG PHÁP SƯ VĂN SAO" in p.upper() or "TĂNG QUẢNG CHÁNH BIÊN" in p.upper():
                header_hits.append(a["global_id"])
    assert len(header_hits) == 0, f"Lỗi: Phát hiện dòng header lọt vào chính văn: {header_hits}"
    print("  [QA 3] Đạt tuyệt đối: 0% dòng header lọt vào văn bản sạch.")

    # QA 4: Broken numbers check
    broken_number_sents = []
    for a in articles:
        for s in a["sentences"]:
            if re.search(r'\b(hơn|gần|khoảng|đến|là)\s+\d+\s*[.?!][”"\'\)\]]*$', s, re.IGNORECASE):
                broken_number_sents.append((a["global_id"], s))
    assert len(broken_number_sents) == 0, f"Lỗi: Phát hiện câu bị cắt cụt ở số: {broken_number_sents}"
    print("  [QA 4] Đạt tuyệt đối: 0 câu bị cắt cụt ở số hàng nghìn.")

    # QA 5: Check file existence and size
    assert os.path.exists(clean_viet_txt), f"Lỗi: Không tìm thấy {clean_viet_txt}!"
    txt_size = os.path.getsize(clean_viet_txt)
    assert txt_size > 100000, f"Lỗi: Dung lượng viet.txt bất thường: {txt_size} bytes"
    print(f"  [QA 5] Đạt: File {clean_viet_txt} tồn tại hợp lệ ({txt_size:,} bytes).")

    print("=== TOÀN BỘ CÁC HẠNG MỤC QA ĐÃ ĐẠT TIÊU CHUẨN ===")


def main():
    parser = argparse.ArgumentParser(description="Phase 2: Extract & Clean Vietnamese Text")
    parser.add_argument("--book-dir", default=str(DEFAULT_BOOK_DIR), help="Book working directory (default: CV09_AQPSVS_Q2)")
    parser.add_argument("--vi-pdf", default=os.environ.get("VI_PDF_PATH", ""), help="Path to Vietnamese PDF")
    parser.add_argument("--anchor-map", default=os.environ.get("ANCHOR_MAP_PATH", str(METADATA_DIR / "anchor_map.json")))
    parser.add_argument("--viet-articles", default=os.environ.get("VIET_ARTICLES_JSON", str(METADATA_DIR / "viet_articles.json")))
    parser.add_argument("--body-start", type=int, default=None, help="1-indexed start page of Vietnamese body")
    parser.add_argument("--body-end", type=int, default=None, help="1-indexed end page of Vietnamese body")
    args = parser.parse_args()

    book_dir = Path(args.book_dir)
    if not book_dir.is_absolute():
        book_dir = BASE_DIR / book_dir

    vi_pdf_path = args.vi_pdf or find_pdf_by_pattern(book_dir / "01_nguon" / "viet", "Ấn Quang Pháp Sư Văn Sao - Vi - 2.pdf")
    raw_viet_dir = os.environ.get("RAW_VIET_DIR", str(book_dir / "02_ocr_tho" / "viet"))
    clean_viet_txt = os.environ.get("CLEAN_VIET_TXT", str(book_dir / "03_text_sach" / "viet.txt"))

    if not os.path.exists(vi_pdf_path):
        raise FileNotFoundError(f"Không tìm thấy file PDF Việt: {vi_pdf_path}")
    if not os.path.exists(args.anchor_map):
        raise FileNotFoundError(f"Không tìm thấy anchor_map.json: {args.anchor_map}")

    with open(args.anchor_map, "r", encoding="utf-8") as f:
        anchor_map = json.load(f)

    body_start = args.body_start if args.body_start is not None else min(a["vi_start_page"] for a in anchor_map)
    body_end = args.body_end if args.body_end is not None else max(a["vi_end_page"] for a in anchor_map)

    print("=== BẮT ĐẦU GIAI ĐOẠN 2: TRÍCH XUẤT THÔ & LÀM SẠCH BẢN TIẾNG VIỆT (QUYỂN 2) ===")
    doc = pymupdf.open(vi_pdf_path)
    print(f"Đã mở PDF: {vi_pdf_path} ({len(doc)} trang)")

    step2_1_extract_raw_pages(doc, raw_viet_dir)
    articles = step2_2_and_2_3_clean_and_structure(
        doc, anchor_map, args.viet_articles, clean_viet_txt, body_start, body_end
    )
    step2_4_automated_qa(articles, anchor_map, clean_viet_txt)
    print("=== GIAI ĐOẠN 2 HOÀN TẤT THÀNH CÔNG ===")


if __name__ == "__main__":
    main()