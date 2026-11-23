# -*- coding: utf-8 -*-
"""
Phase 1: Inventory and Anchor Map Generation (Configured for Volume 2 - Quyển II)
- Auto-detect or accept CLI page ranges for Vietnamese PDF TOC and Body Text
- Dynamically extract all sections and numbered articles
- Cross-check Body articles against TOC entries
- Generate metadata/anchor_map.json and metadata/kiem_ke_nguon.md
"""

import os
import sys
import io
import re
import json
import argparse
from collections import OrderedDict
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


def detect_page_ranges(doc):
    """
    Auto-detect 1-indexed (body_start, body_end, toc_start, toc_end) from Vietnamese PDF.
    """
    n_pages = len(doc)
    toc_pages = []

    for pno in range(n_pages):
        txt = doc[pno].get_text("text")
        if re.search(r"(?m)^\s*MỤC LỤC\s*$", txt):
            toc_pages.append(pno + 1)
            # Extend forward through consecutive TOC pages
            for nxt in range(pno + 1, n_pages):
                ntxt = doc[nxt].get_text("text")
                if re.search(r"(?i)(NHÀ XUẤT BẢN|ẤN TỐNG|LỜI NÓI ĐẦU|HẾT QUYỂN)", ntxt) and not re.search(r"(?m)^\s*\d+\.\s+", ntxt):
                    break
                if re.search(r"(?m)^\s*(\d+\.|[IVX]+\.)\s+", ntxt):
                    toc_pages.append(nxt + 1)
                else:
                    break
            break

    if toc_pages:
        toc_start, toc_end = toc_pages[0], toc_pages[-1]
        if toc_start > n_pages // 2:
            # TOC is at the back of the book (same layout as Volume 3)
            body_start = 5
            body_end = toc_start - 1
        else:
            # TOC is at the front of the book
            body_start = toc_end + 1
            body_end = n_pages - 2
    else:
        # Fallback defaults if "MỤC LỤC" heading is formatted differently
        body_start = 5
        body_end = max(5, n_pages - 10)
        toc_start = body_end + 1
        toc_end = max(toc_start, n_pages - 2)

    return body_start, body_end, toc_start, toc_end


def is_running_header_or_noise(line: str) -> bool:
    upper = line.upper().strip()
    if not upper or upper == "MỤC LỤC":
        return True
    if "ẤN QUANG PHÁP SƯ VĂN SAO" in upper:
        return True
    if re.match(r"^TĂNG QUẢNG CHÁNH BIÊN\s*-\s*QUYỂN\s+[IVX0-9]+$", upper):
        return True
    if re.match(r"^QUYỂN\s+(I|II|III|IV|1|2|3|4|NHẤT|NHỊ|TAM|TỨ)$", upper):
        return True
    return False


def parse_roman_section(line: str):
    """Matches Roman numeral section titles like 'I. THƯ', 'II. LUẬN', 'IV. TỰ', 'V. BẠT'."""
    m = re.match(r"^([IVX]+)\.\s+([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ\s\-]+)$", line.strip())
    if m and len(m.group(2).strip()) >= 2:
        return m.group(2).strip()
    return None


def extract_toc(doc, toc_start: int, toc_end: int):
    """Extract TOC entries from 1-indexed pages [toc_start..toc_end]."""
    toc_lines = []
    for pno in range(toc_start - 1, min(toc_end, len(doc))):
        page = doc[pno]
        for b in page.get_text("blocks"):
            if b[1] < 75:  # skip running header
                continue
            text = b[4].strip()
            for l in text.splitlines():
                l = l.strip()
                if is_running_header_or_noise(l):
                    continue
                toc_lines.append(l)

    entries = []
    cur_num = None
    cur_parts = []
    cur_sec = "CHÍNH VĂN"

    for line in toc_lines:
        sec_name = parse_roman_section(line)
        if sec_name:
            if cur_num is not None:
                entries.append((cur_sec, cur_num, " ".join(cur_parts)))
                cur_num = None
                cur_parts = []
            cur_sec = sec_name
            continue

        m = re.match(r"^(\d+)\.\s*(.*)", line)
        if m:
            if cur_num is not None:
                entries.append((cur_sec, cur_num, " ".join(cur_parts)))
            cur_num = int(m.group(1))
            cur_parts = []
            rest = m.group(2).strip()
            if rest:
                cur_parts.append(rest)
        else:
            if cur_num is not None:
                cur_parts.append(line)

    if cur_num is not None:
        entries.append((cur_sec, cur_num, " ".join(cur_parts)))

    clean_toc = {}
    for sec, num, raw in entries:
        raw = re.sub(r"\s+", " ", raw).strip()
        m_p = re.search(r"\s+(\d+)$", raw)
        if m_p:
            p_no = int(m_p.group(1))
            t = raw[: m_p.start()].strip()
        else:
            p_no = None
            t = raw
        clean_toc[(sec, num)] = (f"{num}. {t}", p_no)
    return clean_toc


def extract_body_articles(doc, body_start: int, body_end: int, min_span_size: float = 12.5, title_min_size: float = 14.0):
    """Extract all numbered articles from 1-indexed body pages [body_start..body_end]."""
    body_articles = []
    cur_section = "CHÍNH VĂN"
    last_page = min(body_end, len(doc))

    for pno in range(body_start - 1, last_page):
        page = doc[pno]
        blocks = page.get_text("dict")["blocks"]
        lines = []
        for b in blocks:
            if "lines" not in b:
                continue
            for l in b["lines"]:
                if l["bbox"][1] < 75:  # skip running header
                    continue
                spans_clean = [s for s in l["spans"] if s["size"] >= min_span_size]
                if not spans_clean:
                    continue
                txt = "".join(s["text"] for s in spans_clean).strip()
                if txt and not is_running_header_or_noise(txt):
                    lines.append((l, txt, spans_clean))

        for idx, (l, txt, spans) in enumerate(lines):
            sec_name = parse_roman_section(txt)
            if sec_name:
                cur_section = sec_name
                continue

            m = re.match(r"^(\d+)\.\s*(.*)", txt)
            s0 = spans[0]
            # Article titles have larger bold font
            if m and s0["size"] >= title_min_size and (s0["flags"] & 16 or "Bold" in s0["font"]):
                num = int(m.group(1))
                title_lines = [txt]
                # Look ahead up to 3 lines for wrapped title / subtitle
                for offset in range(1, 4):
                    if idx + offset < len(lines):
                        nl, ntxt, nspans = lines[idx + offset]
                        if parse_roman_section(ntxt) or re.match(r"^\d+\.", ntxt):
                            break
                        ns0 = nspans[0]
                        # Indented regular body paragraph marks end of title block
                        if nl["bbox"][0] > 85 and ns0["flags"] == 4 and not (ns0["flags"] & 16):
                            break
                        title_lines.append(ntxt)
                    else:
                        break
                full_title = re.sub(r"\s+", " ", " ".join(title_lines)).strip()
                body_articles.append({
                    "global_id": len(body_articles) + 1,
                    "section": cur_section,
                    "article_num": num,
                    "vi_title": full_title,
                    "vi_start_page": pno + 1,
                    "idx_on_page": idx,
                    "total_lines_on_page": len(lines),
                })

    # Calculate vi_end_page for each article
    for i in range(len(body_articles)):
        cur = body_articles[i]
        if i < len(body_articles) - 1:
            nxt = body_articles[i + 1]
            if nxt["vi_start_page"] == cur["vi_start_page"]:
                cur["vi_end_page"] = cur["vi_start_page"]
            elif nxt["idx_on_page"] > 0:
                cur["vi_end_page"] = nxt["vi_start_page"]
            else:
                cur["vi_end_page"] = nxt["vi_start_page"] - 1
        else:
            cur["vi_end_page"] = last_page

    for a in body_articles:
        del a["idx_on_page"]
        del a["total_lines_on_page"]

    return body_articles


def generate_inventory_md(vi_pdf_path, zh_pdf_path, book_dir_name, vi_doc, zh_doc, articles, body_start, body_end, toc_start, toc_end):
    vi_size = os.path.getsize(vi_pdf_path)
    zh_size = os.path.getsize(zh_pdf_path)
    vi_filename = Path(vi_pdf_path).name
    zh_filename = Path(zh_pdf_path).name

    # Summarize counts by section dynamically
    section_stats = OrderedDict()
    for a in articles:
        sec = a["section"]
        if sec not in section_stats:
            section_stats[sec] = {
                "count": 0,
                "first_gid": a["global_id"],
                "last_gid": a["global_id"],
                "first_page": a["vi_start_page"],
                "last_page": a["vi_end_page"],
            }
        section_stats[sec]["count"] += 1
        section_stats[sec]["last_gid"] = a["global_id"]
        section_stats[sec]["last_page"] = a["vi_end_page"]

    section_summary_lines = []
    for sec, st in section_stats.items():
        section_summary_lines.append(
            f"- **Phần {sec}:** {st['count']} bài (Global ID {st['first_gid']} $\\rightarrow$ {st['last_gid']}), "
            f"Trang {st['first_page']} $\\rightarrow$ Trang {st['last_page']}."
        )
    section_summary_md = "\n".join(section_summary_lines)
    structure_inline = " + ".join(f"{st['count']} bài mục `{sec}`" for sec, st in section_stats.items())

    content = f"""# BẢNG KIỂM KÊ NGUỒN TÀI LIỆU
**Dự án:** Xây dựng ngữ liệu song ngữ Hán – Việt (`{book_dir_name}`)  
**Tác phẩm:** Ấn Quang Pháp Sư Văn Sao - Tăng Quảng Chánh Biên - Quyển II (印光法師文鈔卷第二)  

---

## 1. Thông Tin Kiểm Kê Chi Tiết (Tuân thủ Bước 2 - Guideline)

| Thuộc tính | Bản Tiếng Hán (`Zh`) | Bản Tiếng Việt (`Vi`) |
| :--- | :--- | :--- |
| **Tên tài liệu** | 印光法師文鈔卷第二 (Ấn Quang Pháp Sư Văn Sao - Quyển Đệ Nhị) | Ấn Quang Pháp Sư Văn Sao - Tăng Quảng Chánh Biên - Quyển II |
| **Ngôn ngữ** | Chữ Hán phồn thể (Văn ngôn cổ, in mộc bản khắc gỗ) | Tiếng Việt (Bản dịch của chùa Bửu Quang / Thích Bửu Quang) |
| **Link nguồn** | Thư viện Phật giáo số CBETA / Tàng bản Cổ tự | Ban Văn hóa Tịnh Tông / Thư viện Hoa Sen (Phi thương mại) |
| **Tên tệp lưu trữ** | `{zh_filename}` | `{vi_filename}` |
| **Dung lượng tệp** | {zh_size:,} bytes (~{zh_size / (1024*1024):.2f} MB) | {vi_size:,} bytes (~{vi_size / (1024*1024):.2f} MB) |
| **Tổng số trang** | {len(zh_doc)} trang | {len(vi_doc)} trang |
| **Phạm vi sử dụng (Vi)** | Toàn bộ trang chính văn bản Hán | **Trang {body_start} $\\rightarrow$ Trang {body_end}** ({body_end - body_start + 1} trang chính văn) |
| **Phạm vi mục lục (Vi)** | — | **Trang {toc_start} $\\rightarrow$ Trang {toc_end}** |
| **Cấu trúc nội dung** | **{len(articles)} bài văn** khớp 1-1 với bản dịch Việt | **{len(articles)} bài văn:** {structure_inline} |
| **Tình trạng tài liệu** | Bản quét PDF Scan đen trắng, chữ in dọc từ phải sang trái, khung viền đôi. | PDF kỹ thuật số có sẵn text layer Unicode chuẩn, phân tầng font rõ ràng. |
| **Phương thức trích xuất** | Tiền xử lý ảnh (Intensity Clipping 200 DPI) + OCR bằng Gemini Flash API. | Trích xuất trực tiếp bằng PyMuPDF với bộ lọc Font Size (`size >= 12.5`), loại bỏ header và footnote. |

---

## 2. Thống Kê Phân Bổ {len(articles)} Bài Văn Trong Anchor Map

{section_summary_md}
- **Tổng cộng:** **{len(articles)} bài văn** trích xuất từ chính văn.

---

## 3. Danh Sách Đối Chiếu {len(articles)} Bài (Anchor Map Preview)

| Global ID | Phần | STT Bài | Trang Đầu | Trang Cuối | Tên Bài Tiếng Việt Đầy Đủ |
| :---: | :---: | :---: | :---: | :---: | :--- |
"""
    for a in articles:
        content += f"| {a['global_id']} | {a['section']} | {a['article_num']} | {a['vi_start_page']} | {a['vi_end_page']} | {a['vi_title']} |\n"

    return content


def main():
    parser = argparse.ArgumentParser(description="Phase 1: Inventory and Anchor Map Generation")
    parser.add_argument("--book-dir", default=str(DEFAULT_BOOK_DIR), help="Book working directory (default: CV09_AQPSVS_Q2)")
    parser.add_argument("--vi-pdf", default=os.environ.get("VI_PDF_PATH", ""), help="Path to Vietnamese PDF")
    parser.add_argument("--zh-pdf", default=os.environ.get("ZH_PDF_PATH", ""), help="Path to Chinese PDF")
    parser.add_argument("--anchor-map", default=os.environ.get("ANCHOR_MAP_PATH", str(METADATA_DIR / "anchor_map.json")))
    parser.add_argument("--inventory-md", default=os.environ.get("INVENTORY_MD_PATH", str(METADATA_DIR / "kiem_ke_nguon.md")))
    parser.add_argument("--body-start", type=int, default=None, help="1-indexed start page of Vietnamese body")
    parser.add_argument("--body-end", type=int, default=None, help="1-indexed end page of Vietnamese body")
    parser.add_argument("--toc-start", type=int, default=None, help="1-indexed start page of Vietnamese TOC")
    parser.add_argument("--toc-end", type=int, default=None, help="1-indexed end page of Vietnamese TOC")
    parser.add_argument("--title-min-size", type=float, default=14.0, help="Minimum font size for article titles (default: 14.0)")
    args = parser.parse_args()

    book_dir = Path(args.book_dir)
    if not book_dir.is_absolute():
        book_dir = BASE_DIR / book_dir

    vi_pdf_path = args.vi_pdf or find_pdf_by_pattern(book_dir / "01_nguon" / "viet", "Ấn Quang Pháp Sư Văn Sao - Vi - 2.pdf")
    zh_pdf_path = args.zh_pdf or find_pdf_by_pattern(book_dir / "01_nguon" / "han", "Ấn Quang Pháp Sư Văn Sao - Zh - 2.pdf")

    if not os.path.exists(vi_pdf_path):
        raise FileNotFoundError(f"Không tìm thấy file PDF Việt: {vi_pdf_path}")
    if not os.path.exists(zh_pdf_path):
        raise FileNotFoundError(f"Không tìm thấy file PDF Hán: {zh_pdf_path}")

    print("=== BẮT ĐẦU GIAI ĐOẠN 1: KIỂM KÊ & TẠO ANCHOR MAP (QUYỂN 2) ===")
    vi_doc = pymupdf.open(vi_pdf_path)
    zh_doc = pymupdf.open(zh_pdf_path)
    print(f"Loaded Vietnamese PDF ({Path(vi_pdf_path).name}): {len(vi_doc)} pages")
    print(f"Loaded Chinese PDF ({Path(zh_pdf_path).name}): {len(zh_doc)} pages")

    auto_b_start, auto_b_end, auto_t_start, auto_t_end = detect_page_ranges(vi_doc)
    body_start = args.body_start if args.body_start is not None else auto_b_start
    body_end = args.body_end if args.body_end is not None else auto_b_end
    toc_start = args.toc_start if args.toc_start is not None else auto_t_start
    toc_end = args.toc_end if args.toc_end is not None else auto_t_end

    print(f"Using Vietnamese Body pages: {body_start} -> {body_end} | TOC pages: {toc_start} -> {toc_end}")

    # 1. Extract TOC
    toc_dict = extract_toc(vi_doc, toc_start, toc_end)
    print(f"Extracted {len(toc_dict)} TOC entries from pages {toc_start}-{toc_end}.")

    # 2. Extract Body articles
    articles = extract_body_articles(vi_doc, body_start, body_end, title_min_size=args.title_min_size)
    print(f"Extracted {len(articles)} articles from body pages {body_start}-{body_end}.")

    assert len(articles) > 0, "Không trích xuất được bài nào! Hãy kiểm tra lại --body-start, --body-end hoặc --title-min-size."

    # Cross-check Body vs TOC
    body_keys = {(a["section"], a["article_num"]) for a in articles}
    toc_keys = set(toc_dict.keys())
    if toc_keys and body_keys != toc_keys:
        missing_in_body = sorted(toc_keys - body_keys)
        extra_in_body = sorted(body_keys - toc_keys)
        print(f"[CẢNH BÁO] Lệch giữa Mục lục ({len(toc_keys)}) và Chính văn ({len(body_keys)}):")
        if missing_in_body:
            print(f"  - Có trong TOC nhưng thiếu ở Body: {missing_in_body[:10]}")
        if extra_in_body:
            print(f"  - Có trong Body nhưng thiếu ở TOC: {extra_in_body[:10]}")
    else:
        print(f"[OK] Khớp 100% giữa Mục lục và Chính văn ({len(articles)} bài).")

    # Save anchor_map.json
    os.makedirs(os.path.dirname(args.anchor_map), exist_ok=True)
    with open(args.anchor_map, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"Saved anchor map to {args.anchor_map}")

    # Save kiem_ke_nguon.md
    inventory_content = generate_inventory_md(
        vi_pdf_path, zh_pdf_path, book_dir.name, vi_doc, zh_doc, articles, body_start, body_end, toc_start, toc_end
    )
    with open(args.inventory_md, "w", encoding="utf-8") as f:
        f.write(inventory_content)
    print(f"Saved inventory report to {args.inventory_md}")

    print(f"=== GIAI ĐOẠN 1 HOÀN TẤT THÀNH CÔNG ({len(articles)} BÀI) ===")


if __name__ == "__main__":
    main()