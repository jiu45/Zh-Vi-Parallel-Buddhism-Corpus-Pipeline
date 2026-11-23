# -*- coding: utf-8 -*-
"""Kiểm tra articles.json sau mỗi lần chạy lại OCR.

Chạy:  python CV09_AQPSVS_Q2/05_json_tach_bai/check_articles_json.py
Thoát 0 nếu đạt hết, 1 nếu có lỗi.
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ARTICLES = os.path.join(HERE, "articles.json")
HAN_DIR = os.environ.get("Q2_HAN_DIR", os.path.join(ROOT, "CV09_AQPSVS_Q2", "02_ocr_tho", "han"))
ANCHOR = os.environ.get("Q2_ANCHOR", os.path.join(ROOT, "metadata", "anchor_map.json"))

SCHEMA = ["global_id", "section", "article_num", "vi_title", "zh_title", "content", "clauses"]
SECTIONS = {"THƯ TỪ": 83, "LUẬN": 8, "SỚ": 21}


def main():
    data = json.load(open(ARTICLES, encoding="utf-8"))
    anchors = json.load(open(ANCHOR, encoding="utf-8"))
    errors, warnings = [], []

    if len(data) != len(anchors):
        errors.append(f"số bài {len(data)} != anchor_map {len(anchors)}")

    for art in data:
        gid = art.get("global_id")
        if list(art) != SCHEMA:
            errors.append(f"bài {gid}: sai khoá/thứ khoá {list(art)}")
            continue
        if "".join(art["clauses"]) != art["content"]:
            errors.append(f"bài {gid}: clauses nối lại không bằng content")
        if not art["content"]:
            errors.append(f"bài {gid}: content rỗng")
        if not art["clauses"]:
            errors.append(f"bài {gid}: clauses rỗng")
        if any(not c.strip() for c in art["clauses"]):
            errors.append(f"bài {gid}: có clause rỗng")
        if any("。" not in c for c in art["clauses"][:-1]):
            errors.append(f"bài {gid}: clause giữa danh sách thiếu 。")
        if art["content"].startswith("印光法師文鈔"):
            errors.append(f"bài {gid}: lọt dòng chạy đầu trang")
        if not art["clauses"][-1].endswith("。"):
            warnings.append(f"bài {gid}: clause cuối không có 。 (ghi chú cuối bài?)")
        if any("百偈" in c for c in art["clauses"]):
            errors.append(f"bài {gid}: lọt bài kệ 百偈")

    # đối chiếu với anchor_map
    for art, anchor in zip(data, anchors):
        for key in ("global_id", "section", "article_num", "vi_title"):
            if art[key] != anchor[key]:
                errors.append(f"bài {art['global_id']}: {key} khác anchor_map")

    # cân đối dấu câu với thư mục OCR
    dots_in_json = sum(len(re.findall("。", a["content"])) for a in data)
    dots_in_ocr = sum(open(p, encoding="utf-8").read().count("。")
                      for p in glob.glob(os.path.join(HAN_DIR, "page_*.txt")))
    outside = dots_in_ocr - dots_in_json

    per_section = {}
    for art in data:
        per_section[art["section"]] = per_section.get(art["section"], 0) + 1
    if per_section != SECTIONS:
        errors.append(f"phân bổ theo phần {per_section} != {SECTIONS}")

    print(f"bài            : {len(data)}")
    print(f"theo phần      : {per_section}")
    print(f"clause         : {sum(len(a['clauses']) for a in data)}")
    print(f"ký tự Hán      : {sum(len(a['content']) for a in data)}")
    print(f"dấu 。 trong JSON: {dots_in_json}")
    print(f"dấu 。 trong OCR : {dots_in_ocr}  (ngoài 112 bài: {outside})")
    for w in warnings:
        print("  [WARN]", w)
    if errors:
        for e in errors[:20]:
            print("  [FAIL]", e)
        print(f"\nKẾT QUẢ: FAIL ({len(errors)} lỗi)")
        return 1
    print("\nKẾT QUẢ: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
