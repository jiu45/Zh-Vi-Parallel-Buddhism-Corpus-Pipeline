"""Find the Q2 opening boxes using article titles and pages from the prior Q2 data."""
import csv
from difflib import SequenceMatcher
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unicodedata

from phase1_article_anchors import article_groups
from segment_articles import viet_pdf_lines

CONFIG = Path(__file__).resolve().parents[1] / "Q2"
FIELDS = ("phan", "bai", "trang_viet", "trang_han", "x_han", "y_han")
CJK = re.compile(r"[\u3400-\u9fff\U00020000-\U000323af]")
VARIANTS = str.maketrans("敎淸眞爲啓衆羣", "教清真為啟眾群")


def references():
    with (CONFIG / "article_references.csv").open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def check_viet_anchors(doc, table):
    rows = references()
    for row in rows:
        page = int(row["trang_viet"])
        title = re.compile(rf"^\s*{row['bai']}\.(?:\s|$)")
        matches = [line for line, _, _, _ in viet_pdf_lines(doc[page - 1], True) if title.match(line)]
        if table[page][1] != row["phan"] or len(matches) != 1:
            raise ValueError(f"Mốc Việt {row['phan']}/{row['bai']}, trang {page}: {len(matches)} dòng khớp.")
    print(f"Mốc Việt Q2: đã kiểm tra {len(rows)} đầu bài.", flush=True)


def validate_anchors(records, path):
    expected = [(r["phan"], r["bai"], r["trang_viet"]) for r in references()]
    with path.open(encoding="utf-8-sig", newline="") as stream:
        actual = [(r["phan"], r["bai"], r["trang_viet"]) for r in csv.DictReader(stream)]
    if actual != expected:
        raise ValueError(f"{path}: thiếu, sai thứ tự hoặc sai trang Việt của các bài Q2.")
    return article_groups(records, path, volume="Q2")


def normalized_title(text):
    text = unicodedata.normalize("NFKC", text).split("(", 1)[0].translate(VARIANTS)
    return "".join(CJK.findall(text))


def find_box(boxes, title, first_index):
    target = normalized_title(title)
    matches = []
    for index in range(first_index, len(boxes)):
        text = re.split(r"[（(]", boxes[index]["transcription"], maxsplit=1)[0]
        if "。" in text or "、" in text:
            continue
        candidate = normalized_title(text)
        score = SequenceMatcher(None, target, candidate, autojunk=False).ratio()
        if score == 1 or (len(target) >= 6 and score >= 0.83):
            matches.append((score, index))
    if not matches:
        return None
    matches.sort(reverse=True)
    if len(matches) > 1 and matches[0][0] - matches[1][0] < 0.08:
        return None
    return matches[0][1]


def write_anchors(book, records):
    metadata = book / "metadata"
    path = metadata / "anchor_map.csv"
    if path.is_file():
        validate_anchors(records, path)
        print(f"Đã kiểm tra bảng mốc Q2: {path}", flush=True)
        return path

    pages = {record["page"]: record["boxes"] for record in records if record["lang"] == "han"}
    rows = []
    previous = {}
    unresolved = []
    for reference in references():
        row = {field: reference[field] for field in FIELDS[:4]}
        page = int(row["trang_han"])
        boxes = pages[page]
        index = find_box(boxes, reference["tieu_de_han"], previous.get(page, -1) + 1)
        if index is None:
            unresolved.append(
                f"{row['phan']}/{row['bai']} · Hán {page} · {reference['tieu_de_han']}"
            )
            row.update(x_han="", y_han="")
        else:
            previous[page] = index
            xs, ys = zip(*boxes[index]["points"])
            row.update(x_han=(min(xs) + max(xs)) // 2, y_han=(min(ys) + max(ys)) // 2)
        rows.append(row)

    metadata.mkdir(exist_ok=True)
    destination = metadata / "anchor_map_can_sua.csv" if unresolved else path
    with TemporaryDirectory(dir=metadata) as tmp:
        draft = Path(tmp) / destination.name
        with draft.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        if not unresolved:
            validate_anchors(records, draft)
        draft.replace(destination)
    if unresolved:
        raise ValueError(
            f"Có {len(unresolved)} mốc Hán chưa xác định được. Điền tọa độ trong {destination}, "
            "lưu thành anchor_map.csv và chạy lại moc-bai.\n" + "\n".join(unresolved)
        )
    print(f"Đã tạo {len(rows)} mốc Q2: {path}", flush=True)
    return path
