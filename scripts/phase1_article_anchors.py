"""Cắt nhãn theo tiêu đề của từng bài Quyển IV, giữ liên kết với ảnh trang."""
import csv
from pathlib import Path
import re


def article_groups(records, anchor_path=None, *, volume="Q4"):
    path = anchor_path or Path(__file__).with_name("anchor_map.csv")
    with path.open(encoding="utf-8-sig") as stream:
        anchors = list(csv.DictReader(stream))
    sections = {row["phan"] for row in anchors}
    pages = {(r["lang"], r["page"]): r for r in records}
    groups = {}
    starts = {}
    last_start = {}
    for row in anchors:
        section, number = row["phan"], row["bai"]
        article = f"{section}/{number}"
        if article in groups:
            raise ValueError(f"Mốc bài bị trùng: {article}.")
        groups[article] = []
        for lang in ("han", "viet"):
            if not row[f"trang_{lang}"]:
                continue
            page = int(row[f"trang_{lang}"])
            record = pages.get((lang, page))
            if record is None or (volume == "Q2" and record["part"] != section):
                raise ValueError(f"Mốc bài {article}, trang {lang} {page}: ngoài phạm vi phần.")
            boxes = record["boxes"]
            if lang == "viet":
                title = re.compile(rf"^\s*{number}\.(?:\s|$)")
                matches = [i for i, box in enumerate(boxes) if title.match(box["transcription"])]
            elif row["x_han"]:
                x, y = int(row["x_han"]), int(row["y_han"])
                matches = []
                for i, box in enumerate(boxes):
                    xs, ys = zip(*box["points"])
                    if min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys):
                        matches.append(i)
            elif volume == "Q4":
                # Bài cuối phụ lục bắt đầu ở đầu trang Hán 211.
                matches = [0] if boxes else []
            else:
                raise ValueError(f"Mốc bài {article}, trang Hán {page}: thiếu tọa độ trong {path}.")
            if len(matches) != 1:
                raise ValueError(f"Mốc bài {article}, trang {lang} {page}: tìm thấy {len(matches)} box. "
                                 "Đối chiếu Label.txt và anchor_map.csv.")
            key = (lang, page, matches[0])
            if key in starts:
                raise ValueError(f"Hai đầu bài trùng nhau ở {key}.")
            order = (page, matches[0])
            if volume == "Q2" and order <= last_start.get(lang, (0, 0)):
                raise ValueError(f"Mốc bài {article}, trang {lang} {page}: sai thứ tự đọc.")
            last_start[lang] = order
            starts[key] = article

    active = {}
    for rec in records:
        lang, page, section = rec["lang"], rec["page"], rec["part"]
        if volume == "Q4" and lang == "han" and page in (211, 212):
            section = "phu_luc"
        if section not in sections:
            # Lời hồi hướng của dịch giả và trang thông tin ấn bản là hai văn bản riêng.
            name = f"{section}/{lang}" if section == "cuoi_sach" else section
            groups.setdefault(name, []).append(rec)
            continue
        key = (lang, section)
        active.setdefault(key, f"{section}/dau_{lang}")
        lines = []
        for index, box in enumerate(rec["boxes"]):
            article = starts.get((lang, page, index))
            if article:
                if lines:
                    text = "\n".join(line["transcription"] for line in lines)
                    groups.setdefault(active[key], []).append(dict(rec, boxes=lines, text=text))
                    lines = []
                active[key] = article
            lines.append(box)
        if lines:
            text = "\n".join(line["transcription"] for line in lines)
            groups.setdefault(active[key], []).append(dict(rec, boxes=lines, text=text))
    # Theo thứ tự ấn bản Hán, sau đó là các mục chỉ có ở bản dịch.
    section_order = list(dict.fromkeys(r["part"] for r in records))
    def order(name):
        section, _, number = name.partition("/")
        return (section_order.index(section), int(number) if number.isdecimal() else
                (999 if number == "danh_sach" else 0))
    return {name: groups[name] for name in sorted(groups, key=order)}
