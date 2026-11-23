# -*- coding: utf-8 -*-
"""Q2: tách 216 trang OCR Hán thành 112 bài và xuất JSON theo schema dóng hàng.

Nguồn:
  CV09_AQPSVS_Q2/02_ocr_tho/han/page_*.txt   chính văn Hán (mộc bản, ngắt bằng 。)
  metadata/anchor_map.json                    112 bài: section, article_num, vi_title, trang Việt

Ra:
  CV09_AQPSVS_Q2/05_json_tach_bai/articles.json            mảng 112 object
  CV09_AQPSVS_Q2/05_json_tach_bai/articles/article_XXX.json  mỗi bài một file
  CV09_AQPSVS_Q2/05_json_tach_bai/thong_ke_tach_bai.json    thống kê + kiểm tra
"""
import csv
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.environ.get("Q2_OUT_DIR", HERE)
ROOT = os.path.dirname(os.path.dirname(HERE))
HAN_DIR = os.environ.get("Q2_HAN_DIR", os.path.join(ROOT, "CV09_AQPSVS_Q2", "02_ocr_tho", "han"))
ANCHOR = os.environ.get("Q2_ANCHOR", os.path.join(ROOT, "metadata", "anchor_map.json"))

# Tiêu đề bài kết thúc bằng 書/論/疏, có thể kèm số thứ tự và chú thích trong ngoặc.
TITLE = re.compile(r"(?:書|論|疏)[一二三四五六七八九十]*"
                   r"(?:（[^）]*）)?$")
# Dòng chạy đầu trang / tên phần, không thuộc chính văn.
HEADER = re.compile(r"^印光法師文鈔.*$|^書[一二三四五六七八九十]*$|^論$|^疏$")
CLAUSE = re.compile(r"[^。]+。*")


def is_title(text):
    if not text or "。" in text or "、" in text or text.startswith("（"):
        return False
    if len(text) > 40 or "百偈" in text or HEADER.match(text):
        return False
    return bool(TITLE.search(text))


def read_pages():
    pages = []
    for path in sorted(glob.glob(os.path.join(HAN_DIR, "page_*.txt"))):
        name = os.path.basename(path)
        lines = [ln.strip() for ln in open(path, encoding="utf-8").read().splitlines()]
        pages.append((name, [ln for ln in lines if ln]))
    return pages


def segment(pages, max_articles=None):
    articles, cur = [], None
    for name, lines in pages:
        if max_articles is not None and len(articles) >= max_articles:
            break  # đã đủ số bài: bỏ phần đuôi quyển (bài kệ, trang bìa, colophon)
        for text in lines:
            if is_title(text):
                if cur and cur["zh_title"] == text and cur["_pages"][-1] == name:
                    continue  # dòng tiêu đề lặp (page_0126)
                cur = {"zh_title": text, "lines": [], "_pages": [name]}
                articles.append(cur)
            elif HEADER.match(text):
                continue
            elif "百偈" in text:
                # Trang 0002 và 0217 là bài kệ ngoài 112 bài (đầu/cuối quyển).
                cur = None
            elif cur is not None:
                cur["lines"].append(text)
                if cur["_pages"][-1] != name:
                    cur["_pages"].append(name)
    return articles


def split_clauses(content):
    """Tách theo 。, gộp mảnh cuối chỉ gồm dấu đóng ngoặc vào clause trước."""
    clauses = CLAUSE.findall(content)
    if len(clauses) > 1 and clauses[-1].strip() and not re.search(r"[\u4e00-\u9fff]", clauses[-1]):
        tail = clauses.pop()
        clauses[-1] = clauses[-1] + tail
    return clauses


def main():
    anchors = json.load(open(ANCHOR, encoding="utf-8"))
    pages = read_pages()
    segs = segment(pages, max_articles=len(anchors))

    problems = []
    if len(segs) != len(anchors):
        problems.append(f"phát hiện {len(segs)} tiêu đề, anchor_map có {len(anchors)} bài")

    out, stats = [], []
    for idx, (seg, anchor) in enumerate(zip(segs, anchors), 1):
        content = "".join(seg["lines"])
        clauses = split_clauses(content)
        if not content:
            problems.append(f"bài {idx} rỗng")
        if content.startswith("印光法師文鈔"):
            problems.append(f"bài {idx} còn lọt dòng chạy đầu trang")
        if anchor["global_id"] != idx:
            problems.append(f"bài {idx} lệch global_id {anchor['global_id']}")
        out.append({
            "global_id": anchor["global_id"],
            "section": anchor["section"],
            "article_num": anchor["article_num"],
            "vi_title": anchor["vi_title"],
            "zh_title": seg["zh_title"],
            "content": content,
            "clauses": clauses,
        })
        stats.append({
            "global_id": anchor["global_id"],
            "section": anchor["section"],
            "article_num": anchor["article_num"],
            "zh_title": seg["zh_title"],
            "vi_title": anchor["vi_title"],
            "vi_start_page": anchor["vi_start_page"],
            "vi_end_page": anchor["vi_end_page"],
            "zh_pages": f"{seg['_pages'][0]}..{seg['_pages'][-1]}",
            "zh_chars": len(content),
            "zh_clauses": len(clauses),
            "last_clause_open": bool(clauses) and not clauses[-1].endswith("。"),
        })

    # kiểm tra dấu câu: tổng clause phải bằng số 。 trong 112 bài
    dots = sum(len(re.findall("。", a["content"])) for a in out)
    total_dots_all_pages = sum(
        open(p, encoding="utf-8").read().count("。")
        for p in glob.glob(os.path.join(HAN_DIR, "page_*.txt"))
    )
    outside = {}
    for page in ("page_0002.txt", "page_0217.txt"):
        path = os.path.join(HAN_DIR, page)
        outside[page] = open(path, encoding="utf-8").read().count("。")
    excluded = total_dots_all_pages - dots
    text_chars = sum(len(a["content"]) for a in out)

    os.makedirs(os.path.join(OUT_DIR, "articles"), exist_ok=True)
    with open(os.path.join(OUT_DIR, "articles.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    for art in out:
        path = os.path.join(OUT_DIR, "articles", f"article_{art['global_id']:03d}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(art, fh, ensure_ascii=False, indent=2)
            fh.write("\n")

    by_section = {}
    for row in stats:
        s = by_section.setdefault(row["section"], {"bai": 0, "clauses": 0, "chars": 0})
        s["bai"] += 1
        s["clauses"] += row["zh_clauses"]
        s["chars"] += row["zh_chars"]

    report = {
        "so_bai": len(out),
        "so_clause": dots,
        "so_ky_tu_han": sum(a["zh_chars"] for a in stats),
        "theo_phan": by_section,
        "clause_trong_toan_bo_ocr": total_dots_all_pages,
        "clause_khong_thuoc_112_bai": excluded,
        "clause_ngoai_bai": outside,
        "bai_thieu_clause": [r["global_id"] for r in stats if r["zh_clauses"] == 0],
        "bai_clause_cuoi_khong_co_cham": [r["global_id"] for r in stats if r["last_clause_open"]],
        "canh_bao": problems,
        "theo_bai": stats,
    }
    with open(os.path.join(OUT_DIR, "thong_ke_tach_bai.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    with open(os.path.join(OUT_DIR, "danh_sach_bai.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        cols = ["global_id", "section", "article_num", "zh_title", "vi_title",
                "zh_pages", "vi_start_page", "vi_end_page", "zh_chars", "zh_clauses"]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(stats)

    print(json.dumps({k: v for k, v in report.items() if k != "theo_bai"},
                     ensure_ascii=False, indent=2))
    print("OUT:", OUT_DIR)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
