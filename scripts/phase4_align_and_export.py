"""OCR, dóng hàng và đóng gói Quyển IV."""
import csv
import hashlib
import json
import re
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.sax.saxutils import escape

import pymupdf
from PIL import Image
from openpyxl import Workbook, load_workbook

from phase1_article_anchors import article_groups
from phase3_render_page_images import page_image, save_jpg
from segment_articles import ARTICLE_FILES, bind_metadata_to_sources, prepare_articles, viet_pdf_lines

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
OUTPUT_DIR = "ket_qua_moi"
ALIGNMENT_METHOD = "phuong_phap_dong.txt"
ALIGNMENT_CACHE = "dong_hang_q3_h_start_v1.json"
ARTICLE_ALIGNMENT = "Dóng theo mốc bắt đầu Hán của Q3."
OCR_METHOD = "phuong_phap_ocr.txt"
GEMINI_OCR_METHOD = "OCR Hán dùng Gemini theo lô"
BODY_PARTS = {"chinh_van", "ky", "tap_truoc", "phu_luc", "thu_tu", "luan", "so"}
REVIEW = ["phan","anh_han","han_den_trang","anh_viet","viet_den_trang","han","viet","trang_thai"]
FINAL = ["img_id","sentence_id","ChuQN_txt"]
LABELED = {"ch","vi","intro","toc","ref"}


def code(book):
    return book.name.rsplit("_", 1)[-1]


def pdf_source(book, language):
    paths = [p for p in (book/"01_nguon"/language).iterdir() if p.is_file() and p.suffix.lower()==".pdf"]
    if len(paths) != 1:
        raise ValueError(f"{code(book)}: cần đúng một PDF trong 01_nguon/{language}")
    return paths[0]


def layout(lang, total, *, book=None):
    folder = SCRIPT_DIR if book is None else SCRIPT_DIR.parent / code(book)
    path = folder / "page_layout.csv"
    table = {}
    with path.open(encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            if r["ban"] not in {"han","viet"}:
                raise ValueError(f"{path}: sai cột ban")
            if r["ban"] != lang:
                continue
            start,end=int(r["tu_trang"]),int(r["den_trang"])
            folder,part=r["thu_muc"],r["phan"].strip()
            if not (1<=start<=end<=total) or not part or folder not in LABELED|{"blank","misc"}:
                raise ValueError(f"{path}: dòng không hợp lệ {r}")
            for n in range(start,end+1):
                if n in table: raise ValueError(f"{path}: trùng trang {lang} {n}")
                table[n]=(folder,part)
    if len(table)!=total:
        raise ValueError(f"{path}: phạm vi {lang} chưa phủ đủ {total} trang")
    return table


def annotation(text, rect):
    x,y,r,b = rect
    return {"transcription":text,"points":[[x,y],[r,y],[r,b],[x,b]],"difficult":False}


def vietnamese(page, image, body):
    boxes = []
    sx,sy = image.width/page.rect.width,image.height/page.rect.height
    for text, rect, _, _ in viet_pdf_lines(page, body):
        boxes.append(annotation(text,[max(0,round(rect.x0*sx)),max(0,round(rect.y0*sy)),
                                      min(image.width,round(rect.x1*sx)),min(image.height,round(rect.y1*sy))]))
    return boxes


def cached_page(loc):
    return (loc / "ocr.json").is_file() and (loc / "page.jpg").is_file()


def save_page(loc, image, folder, boxes):
    loc.mkdir(parents=True, exist_ok=True)
    save_jpg(image, loc / "page.jpg")
    draft = loc / "ocr.tmp"
    draft.write_text(json.dumps([folder, boxes], ensure_ascii=False), encoding="utf-8")
    draft.replace(loc / "ocr.json")


def cache_han_pages(doc, table, src_cache, gemini, *, volume):
    missing = [
        n for n, (folder, _) in table.items()
        if folder in LABELED and not cached_page(src_cache / f"{n:03d}")
    ]
    batch_size = 3
    for start in range(0, len(missing), batch_size):
        batch = missing[start:start + batch_size]
        print(f"OCR Gemini Hán: {', '.join(map(str, batch))}", flush=True)
        images = {n: page_image(doc[n - 1], True) for n in batch}
        # Hai trang đầu của phần cuối sách nối tiếp chính văn Phụ lục.
        body_pages = {
            n for n in batch if table[n][1] in BODY_PARTS or (volume == "Q4" and n in {211, 212})
        }
        for n, boxes in gemini.ocr_pages(images, body_pages):
            save_page(src_cache / f"{n:03d}", images[n], table[n][0], boxes)


def page_data(language, page, n, folder, part, src_cache):
    loc = src_cache / f"{n:03d}"
    if not cached_page(loc):
        if language == "han" and folder in LABELED:
            raise ValueError(f"Thiếu OCR Gemini cho trang Hán {n}.")
        image = page_image(page, language == "han")
        boxes = []
        if language == "viet" and folder in LABELED:
            body = part in BODY_PARTS
            boxes = vietnamese(page, image, body)
            if not boxes and body:
                boxes = vietnamese(page, image, False)
                if boxes:
                    folder = "ref"
        save_page(loc, image, folder, boxes)
    folder,boxes = json.loads((loc/"ocr.json").read_text(encoding="utf8"))
    return loc/"page.jpg",folder,boxes


def write_csv(path,fields,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        writer.writerows(rows)


def pages(book, work, gemini):
    data = work/"sach"
    data.mkdir()
    inventory = []
    for language in ("han","viet"):
        pdf = pdf_source(book,language)
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        shutil.copy2(pdf,data/pdf.name)
        side_text = []
        with pymupdf.open(pdf) as doc, pymupdf.open() as updated:
            total=len(doc)
            table=layout(language,total,book=book)
            profile=hashlib.sha256(json.dumps(table,sort_keys=True).encode()).hexdigest()[:16]
            cache_version = "pdf-text-v1"
            if language == "han":
                model_id = hashlib.sha256(gemini.model.encode()).hexdigest()[:12]
                cache_version = f"ocr-gemini-v2-{model_id}"
            src_cache = book / ".cache" / cache_version / language / digest / profile
            if language == "han":
                cache_han_pages(doc, table, src_cache, gemini, volume=code(book))
            for n,page in enumerate(doc,1):
                folder,part = table[n]
                jpg,folder,boxes = page_data(language, page, n, folder, part, src_cache)
                if folder=="ref": part="chu_thich"
                name = f"{pdf.stem}.{n:03d}.jpg"
                rel = f"{folder}/{name}"
                dst = data/rel
                dst.parent.mkdir(exist_ok=True)
                shutil.copy2(jpg,dst)
                if language=="han":
                    p = updated.new_page(width=page.rect.width,height=page.rect.height)
                    p.insert_image(p.rect,filename=str(dst),keep_proportion=False)
                if folder in LABELED:
                    for filename,payload in [("Label.txt",json.dumps(boxes,ensure_ascii=False)),("fileState.txt","0")]:
                        with (dst.parent/filename).open("a",encoding="utf8") as f: f.write(f"{rel}\t{payload}\n")
                text = "\n".join(b["transcription"] for b in boxes)
                if text: side_text.append(text)
                inventory.append((language,n,rel,part,len(boxes),"kiem_tra_OCR" if not boxes and folder in LABELED else ""))
                if n%25==0: print(f"{language}: {n}/{total}",flush=True)
            if language=="han": updated.save(data/f"{pdf.stem}_updated.pdf")
        (work/f"{language}.txt").write_text("\n\n".join(side_text),encoding="utf8")
    write_csv(work/"trang.csv",["ban","trang","anh","phan","so_box","can_ra_soat"],inventory)


def sentences(pages,lang):
    # Keep a page id per character so a sentence can continue onto the next page.
    parts, origins = [], []
    for rec in pages:
        if rec["lang"]!=lang or not rec["text"]: continue
        value = ("".join(rec["text"].split()) if lang=="han" else " ".join(rec["text"].split())+" ")
        parts.append(value)
        origins.extend([rec]*len(value))
    text = "".join(parts)
    stop = r"[。！？!?；;]+" if lang=="han" else r"(?<!\d)[.!?;]+(?=\s|$)|[!?]+"
    units = []
    def emit(start,end):
        while start<end and text[start].isspace(): start+=1
        while end>start and text[end-1].isspace(): end-=1
        if start==end: return
        # Sparse historical punctuation: break excessively long runs at commas
        # or whitespace, and leave the original characters in reading order.
        limit = 120 if lang=="han" else 650
        while end-start > limit:
            tail = text[start:start+limit]
            cut = max(tail.rfind(x) for x in ("、","，",","," "))
            size = cut+1 if cut>=limit//2 else limit
            units.append((text[start:start+size], origins[start],origins[start+size-1]))
            start += size
        if start<end: units.append((text[start:end],origins[start],origins[end-1]))
    begin = 0
    for mark in re.finditer(stop,text):
        emit(begin,mark.end())
        begin=mark.end()
    emit(begin,len(text))
    return units


def review_row(section, han, viet):
    return [
        section, han[0][1]["img"] if han else "", han[-1][2]["page"] if han else "",
        viet[0][1]["img"] if viet else "", viet[-1][2]["page"] if viet else "",
        "".join(unit[0] for unit in han), " ".join(unit[0] for unit in viet),
        "cho_ra_soat" if han and viet else "chua_co_cap",
    ]


def alignment_fingerprint(han_texts, viet_texts):
    return hashlib.sha256(json.dumps([han_texts, viet_texts]).encode()).hexdigest()


def make_review(work, groups, prepared, gemini, cache_file):
    try:
        checkpoints = json.loads(cache_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        checkpoints = {}
    except ValueError:
        print(f"Cache dóng hàng không đọc được: {cache_file}", flush=True)
        checkpoints = {}
    if not isinstance(checkpoints, dict):
        checkpoints = {}

    result = []
    models = []
    for section, article in groups.items():
        if section in prepared:
            han_title, viet_title, h, v = prepared[section]
            result.append(review_row(section, [han_title] if han_title else [], [viet_title]))
        else:
            h, v = (sentences(article, lang) for lang in ("han", "viet"))
        if h and v:
            han_texts = [unit[0] for unit in h]
            viet_texts = [unit[0] for unit in v]
            fingerprint = alignment_fingerprint(han_texts, viet_texts)
            saved = checkpoints.get(section)
            if (isinstance(saved, dict) and saved.get("input") == fingerprint
                    and valid_alignment(saved.get("ranges"), len(h), len(v))):
                path = saved["ranges"]
                model = saved.get("model")
                print(f"Dùng lại kết quả phần {section} ({len(path)} cặp).", flush=True)
            else:
                print(f"Dóng phần {section} ({len(h)} đoạn Hán, {len(v)} đoạn Việt)", flush=True)
                path = gemini.align(section, han_texts, viet_texts)
                if not valid_alignment(path, len(h), len(v)):
                    raise ValueError(f"Phần {section}: chỉ số dóng chưa phủ kín văn bản hai vế.")
                model = gemini.last_alignment_model
                checkpoints[section] = {"input": fingerprint, "ranges": path, "model": model}
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                draft = cache_file.with_suffix(".tmp")
                draft.write_text(json.dumps(checkpoints, ensure_ascii=False), encoding="utf-8")
                draft.replace(cache_file)
                print(f"Đã lưu tiến độ phần {section} ({len(path)} cặp).", flush=True)
            if isinstance(model, str) and model not in models:
                models.append(model)
        else:
            path = [(i,i+1,0,0) for i in range(len(h))]+[(0,0,j,j+1) for j in range(len(v))]
        for a,b,c,d in path:
            result.append(review_row(section, h[a:b], v[c:d]))
    write_csv(work/"sua.csv",REVIEW,result)
    return models


def valid_alignment(path, han_count, viet_count):
    if not isinstance(path, list) or not path:
        return False
    han_end = viet_end = 0
    for span in path:
        if (not isinstance(span, (list, tuple)) or len(span) != 4
                or any(type(index) is not int for index in span)):
            return False
        h_start, h_end, v_start, v_end = span
        if (h_start != han_end or v_start != viet_end
                or not h_start < h_end <= han_count or not v_start < v_end <= viet_count):
            return False
        han_end, viet_end = h_end, v_end
    return (han_end, viet_end) == (han_count, viet_count)


def check_pages(volume):
    out = volume / OUTPUT_DIR
    book = out/"sach"
    with (out/"trang.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    known = {}
    for lang in ("han","viet"):
        pdf = pdf_source(volume,lang)
        if hashlib.sha256(pdf.read_bytes()).digest() != hashlib.sha256((book/pdf.name).read_bytes()).digest():
            raise ValueError(f"{pdf.name}: PDF nguồn đã thay đổi so với bản đã OCR.")
        with pymupdf.open(pdf) as original: count = len(original)
        with pymupdf.open(book/pdf.name) as doc:
            if len(doc)!=count: raise ValueError(pdf.name)
        subset = [r for r in rows if r["ban"]==lang]
        if [int(r["trang"]) for r in subset]!=list(range(1,count+1)): raise ValueError(f"Thiếu trang {lang}")
        for r in subset:
            key=r["anh"]
            expected=f"{pdf.stem}.{int(r['trang']):03d}.jpg"
            if Path(key).name!=expected or Path(key).parent.as_posix() not in LABELED|{"misc","blank"}:
                raise ValueError(key)
            with Image.open(book/key) as image:
                if image.format!="JPEG": raise ValueError(key)
                known[key] = image.size
                image.verify()
    if set(known)!={p.relative_to(book).as_posix() for p in book.rglob("*.jpg")} or len(rows)!=len(known):
        raise ValueError("Danh sách ảnh khác bảng trang.csv")
    unverified = empty = 0
    for folder in LABELED:
        expected={k for k in known if k.startswith(folder+"/")}
        if not expected: continue
        for file in ("Label.txt","fileState.txt"):
            seen=set()
            for line in (book/folder/file).read_text(encoding="utf8").splitlines():
                key,val=line.split("\t",1)
                if key not in expected or key in seen: raise ValueError(key)
                seen.add(key)
                if file=="fileState.txt":
                    if val not in {"0","1"}: raise ValueError(key)
                    unverified += val=="0"
                    continue
                boxes=json.loads(val)
                if not isinstance(boxes,list): raise ValueError(key)
                empty += not boxes
                w,h=known[key]
                for box in boxes:
                    pts=box["points"]
                    if (not box["transcription"].strip() or len(pts)!=4 or len(set(map(tuple,pts)))!=4
                            or not all(0<=x<=w and 0<=y<=h for x,y in pts)):
                        raise ValueError(key)
            if seen!=expected: raise ValueError(f"{folder}/{file} thiếu ảnh")
    han=pdf_source(volume,"han")
    with pymupdf.open(book/f"{han.stem}_updated.pdf") as doc:
        if len(doc)!=sum(r["ban"]=="han" for r in rows): raise ValueError("PDF updated sai số trang")
        for page,r in zip(doc,(r for r in rows if r["ban"]=="han")):
            imgs=page.get_images()
            if len(imgs)!=1 or doc.extract_image(imgs[0][0])["image"]!=(book/r["anh"]).read_bytes():
                raise ValueError(f"PDF updated sai ảnh {r['anh']}")
    return rows,unverified,empty


def safe_name(value):
    if not value.strip() or value in {".",".."} or re.search(r'[\\/:*?"<>|\x00-\x1f]',value):
        raise ValueError(f"Tên file không hợp lệ: {value!r}")
    return value


def reviewed_pairs(out,pages, *, details=None):
    sources = {
        (row["ban"], Path(row["anh"]).name): (int(row["trang"]), row["phan"])
        for row in pages
    }
    sections = {(row["ban"], int(row["trang"])): row["phan"] for row in pages}
    counts=Counter()
    pairs=[]
    skipped=0
    article_pages = None
    with (out/"sua.csv").open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=REVIEW: raise ValueError("Sai tiêu đề trong sua.csv")
        for row in reader:
            if row["trang_thai"]=="bo_qua" or not row["han"].strip() or not row["viet"].strip():
                skipped+=1
                continue
            img=row["anh_han"]
            article_id = row["phan"]
            if "/" in article_id and article_pages is None:
                article_pages = {
                    (name, lang): {r["page"] for r in article if r["lang"] == lang}
                    for name, article in volume_groups(out.parent).items()
                    for lang in ("han", "viet")
                }
            for lang in ("han", "viet"):
                start = sources.get((lang, row[f"anh_{lang}"]))
                end = row[f"{lang}_den_trang"]
                if not start or not end.isdecimal() or int(end) < start[0]:
                    raise ValueError(f"Dòng {reader.line_num}: sai ảnh hoặc phạm vi trang {lang}.")
                if "/" in article_id:
                    allowed = article_pages.get((article_id, lang), set())
                    valid = start[0] in allowed and int(end) in allowed
                else:
                    valid = start[1] == article_id == sections.get((lang, int(end)))
                if not valid:
                    raise ValueError(f"Dòng {reader.line_num}: phạm vi trang ngoài bài {article_id}.")
            counts[img]+=1
            pairs.append((img,f"{Path(img).stem}.{counts[img]}",row["viet"]))
            if details is not None:
                fields = ("anh_han", "han_den_trang", "han", "anh_viet", "viet_den_trang", "viet")
                details.append((pairs[-1][1], *(row[field] for field in fields)))
    if not pairs: raise ValueError(f"{out}: chưa có cặp Hán–Việt để xuất")
    return pairs, skipped


def export_tables(dest,title,pairs):
    csv_file=dest/f"{title}.csv"
    xlsx_file=dest/f"{title}.xlsx"
    write_csv(csv_file,FINAL,pairs)
    wb=Workbook()
    ws=wb.active
    ws.title="Dóng hàng"
    ws.append(FINAL)
    for n,row in enumerate(pairs,2):
        ws.append(row)
        for col in range(1,4): ws.cell(n,col).data_type="s"
    wb.save(xlsx_file)
    with csv_file.open(encoding="utf-8-sig",newline="") as f:
        wb=load_workbook(xlsx_file,read_only=True)
        try:
            if list(csv.reader(f))!=[list(r) for r in wb.active.values]:
                raise ValueError("CSV và Excel khác nhau")
        finally: wb.close()


def report(path, group, volumes, totals, count, skipped, unverified, empty, methods):
    doc=pymupdf.open()
    page=doc.new_page(width=595,height=842)
    html=f"""<h1>Báo cáo xử lý {escape(volumes)}</h1><p>Nhóm: {escape(group)}</p>
    <p>Nguồn gồm {totals['han']} trang Hán và {totals['viet']} trang Quốc ngữ. Ảnh xuất ở 200 DPI.
    Bản Hán được chỉnh tương phản và ghép lại theo thứ tự PDF gốc.</p>
    <p>{escape(methods)} Bản Việt ưu tiên lớp chữ trong PDF. Văn bản được nối qua
    trang và dóng theo từng phần. Mã câu lấy theo ảnh Hán đầu câu.</p>
    <p>Đã xuất {count} cặp. Có {skipped} dòng chỉ có một vế hoặc được đánh dấu bỏ qua trong sua.csv.
    Có {unverified} ảnh mang trạng thái nhãn 0, {empty} ảnh thuộc thư mục nhãn chưa có box.</p>
    <p>Đã kiểm tra tên ảnh, cấu trúc nhãn, thứ tự PDF và nội dung CSV/XLSX.</p>
    <p>Chưa đánh giá độ tương đồng theo quy định. Để nộp chính thức, bổ sung họ tên,
    MSSV, email thành viên, kết quả đánh giá và bốn ảnh minh chứng (PPOCRLabel Hán và Việt,
    Excel và CSV).</p>"""
    page.insert_htmlbox(pymupdf.Rect(42,40,552,800),html)
    doc.save(path)
    doc.close()


def read_records(out):
    # Read the latest PPOCRLabel edits before creating the sentence table.
    with (out/"trang.csv").open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    texts={}
    for folder in LABELED:
        label=out/"sach"/folder/"Label.txt"
        if label.is_file():
            for line in label.read_text(encoding="utf8").splitlines():
                name,payload=line.split("\t",1)
                texts[name]=json.loads(payload)
    records = []
    for r in rows:
        boxes = texts[r["anh"]] if Path(r["anh"]).parent.name in LABELED else []
        records.append(dict(lang=r["ban"],page=int(r["trang"]),img=Path(r["anh"]).name,
                            part=r["phan"], boxes=boxes, text="\n".join(b["transcription"] for b in boxes)))
    return records


def volume_groups(book):
    records = read_records(book / OUTPUT_DIR)
    if code(book) == "Q2":
        from q2_anchors import validate_anchors, write_anchors

        path = book / "metadata" / "anchor_map.csv"
        if not path.is_file():
            path = write_anchors(book, records)
        return validate_anchors(records, path)
    return article_groups(records)


def needs_ocr(output):
    method = output / OCR_METHOD
    return (not (output / "trang.csv").is_file()
            or not method.is_file()
            or not method.read_text(encoding="utf-8").startswith(GEMINI_OCR_METHOD))


def article_metadata(book):
    return tuple((book / "metadata" / name).read_bytes() for name in ARTICLE_FILES)


def alignment_marker(metadata):
    fingerprint = hashlib.sha256(b"\0".join(metadata)).hexdigest()
    return f"{ARTICLE_ALIGNMENT}\nMetadata SHA-256: {fingerprint}\n"


def needs_alignment(output):
    method = output / ALIGNMENT_METHOD
    if not (output / "sua.csv").is_file() or not method.is_file():
        return True
    try:
        marker = alignment_marker(article_metadata(output.parent))
    except FileNotFoundError:
        return True
    return not method.read_text(encoding="utf-8").startswith(marker)


def prepare_volume(book, step, gemini=None):
    out = book / OUTPUT_DIR
    if step in {"ocr", "all"} and needs_ocr(out):
        with tempfile.TemporaryDirectory(dir=book,prefix=".xu-ly-") as tmp:
            stage=Path(tmp)/"ket_qua"
            stage.mkdir()
            pages(book, stage, gemini)
            (stage / OCR_METHOD).write_text(
                f"{GEMINI_OCR_METHOD} (ưu tiên {gemini.model}, có model dự phòng). "
                "Bản Việt lấy từ lớp chữ PDF.", encoding="utf-8")
            backup = None
            if out.exists():
                backup = Path(tempfile.mkdtemp(dir=book, prefix=f"{OUTPUT_DIR}_sao_luu_")) / OUTPUT_DIR
                out.rename(backup)
            try:
                stage.rename(out)
            except OSError:
                if backup is not None:
                    backup.rename(out)
                raise
            if backup is not None:
                print(f"Đã sao lưu kết quả trước tại {backup}", flush=True)
    if not (out/"trang.csv").is_file():
        raise ValueError(f"{code(book)}: thiếu trang.csv. Chạy bước ocr trước.")
    if step == "tach":
        check_pages(book)
        prepare_articles(book, volume_groups(book), pdf_source(book, "viet"))
    if step in {"ghep","all"}:
        if not needs_alignment(out):
            print(f"{code(book)}: giữ nguyên sua.csv đã có.")
        else:
            with tempfile.TemporaryDirectory(dir=out) as tmp:
                stage=Path(tmp)
                print("Đang kiểm tra ảnh, nhãn và PDF trước khi dóng...", flush=True)
                check_pages(book)
                groups = volume_groups(book)
                viet_pdf = pdf_source(book, "viet")
                if step == "all" and not any((book / "metadata" / name).exists() for name in ARTICLE_FILES):
                    prepare_articles(book, groups, viet_pdf)
                try:
                    metadata = article_metadata(book)
                except FileNotFoundError as error:
                    raise ValueError("Cần hai file metadata Hán và Việt. Chạy bước tach-cau trước.") from error
                prepared = bind_metadata_to_sources(*metadata, groups, viet_pdf)
                models = make_review(
                    stage, groups, prepared, gemini, book / ".cache" / ALIGNMENT_CACHE,
                )
                review = out / "sua.csv"
                if review.exists():
                    with tempfile.NamedTemporaryFile(dir=out, prefix="sua_truoc_", suffix=".csv", delete=False) as old:
                        shutil.copyfile(review, old.name)
                    print(f"Đã lưu bản dóng trước tại {old.name}", flush=True)
                if models:
                    method = f"Gemini: {', '.join(models)}."
                else:
                    method = "Dùng nhánh một câu Việt của Q3 hoặc xuất một vế."
                (stage / ALIGNMENT_METHOD).write_text(alignment_marker(metadata) + method, encoding="utf-8")
                (stage / "sua.csv").replace(review)
                (stage / ALIGNMENT_METHOD).replace(out / ALIGNMENT_METHOD)


def package(volume,args):
    volume_code=code(volume)
    output = volume / OUTPUT_DIR
    title=safe_name(args.ten_sach or pdf_source(volume,"han").stem)
    group=safe_name(args.nhom or volume_code)
    if group.casefold() in {"source","extras"} or title.casefold() in {"trang","sua"}:
        raise ValueError("Tên trùng với file dành riêng cho pipeline.")
    print("Đang kiểm tra dữ liệu và đóng gói ZIP...", flush=True)
    rows,unverified,empty=check_pages(volume)
    details = [] if volume_code == "Q2" else None
    pairs,skipped=reviewed_pairs(output,rows,details=details)
    totals=Counter(r["ban"] for r in rows)
    with tempfile.TemporaryDirectory(dir=output,prefix=".dong-goi-") as tmp:
        dest=Path(tmp)
        archive=dest/f"{group}.zip"
        export_tables(dest,title,pairs)
        rich_table = None
        if details is not None:
            rich_table = dest / "Dóng hàng Hán - Quốc ngữ.csv"
            if rich_table.stem == title:
                raise ValueError("Tên sách trùng tên bảng song ngữ chi tiết.")
            write_csv(rich_table, ("sentence_id", "anh_han", "han_den_trang", "han",
                                   "anh_viet", "viet_den_trang", "viet"), details)
        report_file=dest/f"{group}_report.pdf"
        if args.bao_cao:
            with pymupdf.open(args.bao_cao) as doc:
                if not doc.is_pdf or not len(doc): raise ValueError("Báo cáo PDF không hợp lệ")
            shutil.copyfile(args.bao_cao,report_file)
        else:
            methods = " ".join(
                path.read_text(encoding="utf-8") for path in (
                    output / OCR_METHOD, output / ALIGNMENT_METHOD,
                ) if path.is_file()
            )
            report(report_file, group, volume_code, totals, len(pairs), skipped, unverified, empty, methods)
        with ZipFile(dest/"extras.zip","w",ZIP_DEFLATED) as extra:
            for name in ("trang.csv","sua.csv","han.txt","viet.txt"):
                extra.write(output/name,name)
            if volume_code == "Q2":
                for name in ("anchor_map.csv", *ARTICLE_FILES, "thong_ke_tach_cau.json"):
                    path = volume / "metadata" / name
                    if path.is_file():
                        extra.write(path, f"metadata/{name}")
        with ZipFile(dest/"source.zip","w",ZIP_DEFLATED) as source:
            for path in sorted(SCRIPT_DIR.iterdir()):
                if path.suffix in {".py", ".sh", ".csv", ".md", ".txt"}:
                    source.write(path, path.relative_to(ROOT))
            if volume_code == "Q2":
                for path in sorted((SCRIPT_DIR.parent / volume_code).iterdir()):
                    if path.suffix in {".csv", ".md"}:
                        source.write(path, path.relative_to(ROOT))
            for name in ("build_new_guideline_submission.py", "phase2_extract_and_clean_viet.py",
                         "phase3_ocr_han.py", "phase4_align_and_export.py"):
                path = SCRIPT_DIR.parent / "Q3" / name
                source.write(path, path.relative_to(ROOT))
        with ZipFile(archive,"w",ZIP_DEFLATED) as z:
            for p in sorted((output/"sach").rglob("*")):
                if p.is_file() and (p.suffix.lower() in {".jpg",".pdf"} or p.name in {"Label.txt","fileState.txt"}):
                    z.write(p,f"{title}/{p.relative_to(output/'sach').as_posix()}")
            for ext in ("csv","xlsx"):
                z.write(dest/f"{title}.{ext}",f"{title}/{title}.{ext}")
            if rich_table is not None:
                z.write(rich_table, f"{title}/{rich_table.name}")
            for p in [report_file,dest/"extras.zip",dest/"source.zip"]:
                z.write(p,p.name)
        with ZipFile(archive) as z:
            if z.testzip(): raise ValueError("Lỗi khi đọc lại ZIP")
        for p in (dest/f"{title}.csv",dest/f"{title}.xlsx",report_file,archive):
            p.replace(output/p.name)
        if rich_table is not None:
            rich_table.replace(output / rich_table.name)
    print(f"{volume_code}: {len(pairs)} cặp; {skipped} dòng riêng; {unverified} ảnh chưa duyệt.\n{output/archive.name}")
