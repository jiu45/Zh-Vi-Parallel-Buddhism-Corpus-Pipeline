"""Tách chính văn Q4 theo bài để thống kê và chuẩn bị dóng hàng."""
import json
import re
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pymupdf

from phase3_render_page_images import DPI

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from Q3.phase2_extract_and_clean_viet import clean_spacing, join_lines_to_para, split_sentences_viet

SECTION_NAMES = {
    "ky": "KÝ", "tap_truoc": "TẠP TRƯỚC", "phu_luc": "PHỤ LỤC",
    "thu_tu": "THƯ TỪ", "luan": "LUẬN", "so": "SỚ",
}
ARTICLE_FILES = ("han_articles.json", "viet_articles.json")


def viet_pdf_lines(page, body):
    """Lấy chữ, tọa độ và kiểu chữ của mỗi dòng được giữ trong nhãn Việt."""
    flags = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES
    for block in page.get_text("dict", flags=flags)["blocks"]:
        for line in block.get("lines", []):
            spans = [
                span for span in line["spans"]
                if span["text"].strip()
                and not ("MyriadPro" in span["font"] and span["bbox"][1] < 75)
                and (not body or span["size"] >= 12.5)
            ]
            if not spans:
                continue
            text = " ".join("".join(span["text"] for span in spans).split())
            rect = pymupdf.Rect(spans[0]["bbox"])
            for span in spans[1:]:
                rect |= span["bbox"]
            first = spans[0]
            yield text, rect, first["flags"], "Bold" in first["font"]


def compact(text):
    return "".join(text.split())


def source_units(lines, texts):
    """Gắn từng câu hoặc mệnh đề với trang đầu và cuối của nguyên văn."""
    pieces = []
    origins = []
    for text, record in lines:
        piece = compact(text)
        pieces.append(piece)
        origins.extend([record] * len(piece))
    stream = "".join(pieces)
    units = []
    offset = 0
    for text in texts:
        piece = compact(text)
        end = offset + len(piece)
        if stream[offset:end] != piece:
            raise ValueError(f"Đơn vị sau khi tách khác văn bản nguồn: {text[:80]!r}")
        units.append((text, origins[offset], origins[end - 1]))
        offset = end
    if offset != len(stream):
        raise ValueError("Còn chữ chưa được đưa vào các đơn vị đã tách.")
    return units


def han_title_and_body(name, lines):
    if not lines:
        return None, []
    first_text, first_page = lines[0]
    if name == "tap_truoc/35" and first_text.startswith("維年月日"):
        # Ảnh trang 144 có tiêu đề ngay trước cột mở đầu, OCR đã bỏ sót cột tiêu đề.
        title = ("祭盛寅懷文（代了餘師作）", first_page, first_page)
        body = lines
    else:
        title_end = 1
        balance = first_text.count("（") - first_text.count("）")
        while balance > 0 and title_end < len(lines):
            continuation = lines[title_end][0]
            balance += continuation.count("（") - continuation.count("）")
            title_end += 1
        if balance > 0:
            raise ValueError(f"Bài {name}: chú thích trong tiêu đề Hán chưa đóng ngoặc.")
        title_text = compact("".join(text for text, _ in lines[:title_end]))
        title = (title_text, first_page, lines[title_end - 1][1])
        body = lines[title_end:]
    return title, body


def vietnamese_lines(records, doc, pdf_layout):
    for record in records:
        pno = record["page"]
        if pno not in pdf_layout:
            pdf_layout[pno] = list(viet_pdf_lines(doc[pno - 1], body=True))
        for box in record["boxes"]:
            text = box["transcription"]
            xs, ys = zip(*box["points"])
            x0, y0 = min(xs) * 72 / DPI, min(ys) * 72 / DPI
            candidates = pdf_layout[pno]
            _, rect, flags, bold_font = min(
                candidates,
                key=lambda item: abs(item[1].x0 - x0) + abs(item[1].y0 - y0),
                default=("", pymupdf.Rect(), 4, False),
            )
            if abs(rect.y0 - y0) > 3:
                flags, bold_font = 4, False
            yield text, record, x0, flags, bool(flags & 16 or bold_font)


def vietnamese_title_and_paragraphs(name, lines):
    title_end = 1
    first = lines[0][0]
    balance = first.count("(") - first.count(")")
    subtitle = False
    for text, _, x0, flags, bold in lines[1:]:
        starts_subtitle = not subtitle and text.startswith("(") and balance == 0
        if not (bold or re.match(r"^[-–]\s*Bài\s+\d", text)
                or starts_subtitle or (balance > 0 and (x0 <= 85 or flags & 2))):
            break
        title_end += 1
        subtitle |= starts_subtitle
        balance += text.count("(") - text.count(")")

    title_text = clean_spacing(" ".join(line[0] for line in lines[:title_end]))
    title = (title_text, lines[0][1], lines[title_end - 1][1])
    paragraphs = []
    paragraph_lines = []
    # Các dòng thơ của Phụ lục 8 nằm ở x ≈ 127 pt trong bản PDF Q4.
    verse_indent = 125 if name == "phu_luc/8" else 130
    for text, record, x0, flags, bold in lines[title_end:]:
        verse = x0 > verse_indent and len(text) < 60 and not bold
        if paragraph_lines and (verse or (x0 > 85 and flags == 4)):
            paragraphs.append(paragraph_lines)
            paragraph_lines = []
        if verse:
            paragraphs.append([(text, record)])
        else:
            paragraph_lines.append((text, record))
    if paragraph_lines:
        paragraphs.append(paragraph_lines)
    return title, paragraphs


def article_sources(groups, viet_pdf):
    pdf_layout = {}
    with pymupdf.open(viet_pdf) as doc:
        for name, records in groups.items():
            section, _, number = name.partition("/")
            if section not in SECTION_NAMES or not number.isdecimal():
                continue
            v_records = [record for record in records if record["lang"] == "viet"]
            v_lines = list(vietnamese_lines(v_records, doc, pdf_layout))
            if not v_lines:
                raise ValueError(f"Bài {name}: thiếu văn bản Việt sau khi chia bài.")
            v_title, paragraphs = vietnamese_title_and_paragraphs(name, v_lines)
            h_lines = [
                (box["transcription"], record) for record in records if record["lang"] == "han"
                for box in record["boxes"]
            ]
            h_title, h_body = han_title_and_body(name, h_lines)
            v_pages = (v_records[0]["page"], v_records[-1]["page"])
            yield name, h_title, v_title, h_body, paragraphs, v_pages


def prepare_articles(book, groups, viet_pdf):
    han_articles, viet_articles, article_stats = [], [], []
    for name, h_title, v_title, h_body, v_paragraphs, v_pages in article_sources(groups, viet_pdf):
        section, _, number = name.partition("/")
        paragraphs = [join_lines_to_para([line for line, _ in para]) for para in v_paragraphs]
        v_units = [sentence for para in paragraphs for sentence in split_sentences_viet(para)]
        source_units([line for para in v_paragraphs for line in para], v_units)
        content = compact("".join(text for text, _ in h_body))
        # Theo Q3, chỉ tách ở 。. Giữ nguyên cả cụm dấu nếu OCR ghi hai dấu liền nhau.
        h_units = re.findall(r"[^。]+。*|^。+", content)
        if not v_units or (h_title and not h_units):
            raise ValueError(f"Bài {name}: chính văn bị rỗng sau khi tách.")
        common = {
            "global_id": len(viet_articles) + 1,
            "section": SECTION_NAMES[section],
            "article_num": int(number),
            "vi_title": v_title[0],
        }
        viet_articles.append({
            **common, "vi_start_page": v_pages[0], "vi_end_page": v_pages[1],
            "paragraphs": paragraphs, "sentences": v_units,
        })
        if h_title:
            han_articles.append({
                **common, "zh_title": h_title[0], "content": content, "clauses": h_units,
            })
        article_stats.append({
            "bai": name, "global_id": common["global_id"], "section": common["section"],
            "co_han": bool(h_units), "co_hai_ve": bool(h_units and v_units),
            "so_menh_de_han": len(h_units), "so_doan_viet": len(paragraphs),
            "so_cau_viet": len(v_units),
            "menh_de_han_qua_120_ky_tu": sum(len(unit) > 120 for unit in h_units),
        })

    def summarize(rows):
        return {
            "so_bai_viet": len(rows),
            "so_bai_han": sum(row["co_han"] for row in rows),
            "so_bai_co_hai_ve": sum(row["co_hai_ve"] for row in rows),
            **{key: sum(row[key] for row in rows) for key in (
                "so_menh_de_han", "so_doan_viet", "so_cau_viet", "menh_de_han_qua_120_ky_tu",
            )},
        }

    totals = summarize(article_stats)
    stats = {
        "tong": totals,
        "theo_phan": {
            section: summarize([row for row in article_stats if row["section"] == section])
            for section in dict.fromkeys(row["section"] for row in article_stats)
        },
        "bai_chua_co_ve_han": [row["bai"] for row in article_stats if not row["co_han"]],
        "theo_bai": article_stats,
    }
    metadata = book / "metadata"
    metadata.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=metadata) as tmp:
        for filename, data in (
            (ARTICLE_FILES[0], han_articles), (ARTICLE_FILES[1], viet_articles),
            ("thong_ke_tach_cau.json", stats),
        ):
            (Path(tmp) / filename).write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
            )
        for file in Path(tmp).iterdir():
            file.replace(metadata / file.name)

    print(f"{book.name}: {totals['so_bai_han']} bài Hán, {totals['so_bai_viet']} bài Việt", flush=True)
    print(f"{totals['so_menh_de_han']} mệnh đề Hán, {totals['so_cau_viet']} câu Việt", flush=True)
    print(metadata, flush=True)


def read_article_metadata(data, filename, units_key, title_key):
    articles = json.loads(data)
    if not isinstance(articles, list) or not articles:
        raise ValueError(f"{filename}: cần danh sách bài không rỗng.")
    by_article = {}
    seen_ids = set()
    for article in articles:
        if not isinstance(article, dict):
            raise ValueError(f"{filename}: bài phải là một đối tượng JSON.")
        gid, section, number = (article.get(key) for key in ("global_id", "section", "article_num"))
        key = (section, number)
        if (type(gid) is not int or gid < 1 or type(number) is not int or number < 1
                or section not in SECTION_NAMES.values() or gid in seen_ids or key in by_article):
            raise ValueError(f"{filename}: mã bài không hợp lệ hoặc bị trùng: {gid}, {section}, {number}.")
        title = article.get(title_key)
        units = article.get(units_key)
        if (not isinstance(title, str) or not title.strip() or not isinstance(units, list) or not units
                or any(not isinstance(unit, str) or not unit.strip() for unit in units)):
            raise ValueError(f"{filename}: bài {section} {number} thiếu tiêu đề hoặc {units_key}.")
        seen_ids.add(gid)
        by_article[key] = article
    return by_article


def bind_metadata_to_sources(han_json, viet_json, groups, viet_pdf):
    """Đọc đơn vị từ JSON và tra ảnh nguồn mà không tách lại câu hay ghi đè metadata."""
    han = read_article_metadata(han_json, ARTICLE_FILES[0], "clauses", "zh_title")
    viet = read_article_metadata(viet_json, ARTICLE_FILES[1], "sentences", "vi_title")
    prepared = {}
    for name, h_title, v_title, h_body, v_paragraphs, _ in article_sources(groups, viet_pdf):
        section, _, number = name.partition("/")
        key = (SECTION_NAMES[section], int(number))
        h_article = han.pop(key, None)
        v_article = viet.pop(key, None)
        if v_article is None or (h_title is None) != (h_article is None):
            raise ValueError(f"Bài {name}: phạm vi hai file metadata khác mốc bài. Chạy tach-cau để cập nhật.")
        if h_article and h_article["global_id"] != v_article["global_id"]:
            raise ValueError(f"Bài {name}: global_id Hán và Việt khác nhau.")
        viet_title = v_article["vi_title"]
        han_title = h_article["zh_title"] if h_article else ""
        if (compact(v_title[0]) != compact(viet_title)
                or (h_title and compact(h_title[0]) != compact(han_title))):
            raise ValueError(f"Bài {name}: tiêu đề JSON khác nhãn nguồn. Chạy tach-cau để cập nhật.")
        try:
            h_units = source_units(h_body, h_article["clauses"]) if h_article else []
            v_units = source_units([line for para in v_paragraphs for line in para], v_article["sentences"])
        except ValueError as error:
            raise ValueError(
                f"Bài {name}: văn bản metadata khác nhãn nguồn. Chạy tach-cau để cập nhật. {error}"
            ) from error
        prepared[name] = (
            (han_title, h_title[1], h_title[2]) if h_title else None,
            (viet_title, v_title[1], v_title[2]),
            h_units, v_units,
        )
    if han or viet:
        raise ValueError(f"Metadata còn bài ngoài mốc: {list(han or viet)}.")
    return prepared
