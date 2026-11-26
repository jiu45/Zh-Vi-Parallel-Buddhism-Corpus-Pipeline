"""Xem những cặp đã lưu trong khi tiến trình dóng Q4 đang chạy."""
import json
import tempfile
import time
from pathlib import Path

from phase4_align_and_export import (
    ALIGNMENT_CACHE,
    OUTPUT_DIR,
    REVIEW,
    alignment_fingerprint,
    article_metadata,
    needs_alignment,
    pdf_source,
    review_row,
    valid_alignment,
    volume_groups,
    write_csv,
)
from segment_articles import bind_metadata_to_sources


def write_preview(output, articles, checkpoints):
    rows = []
    completed = []
    for name, (han, viet, fingerprint) in articles.items():
        saved = checkpoints.get(name)
        if not isinstance(saved, dict) or saved.get("input") != fingerprint:
            continue
        ranges = saved.get("ranges")
        if not valid_alignment(ranges, len(han), len(viet)):
            continue
        completed.append(name)
        for a, b, c, d in ranges:
            rows.append(review_row(name, han[a:b], viet[c:d]))

    preview = output / "sua_tam.csv"
    with tempfile.TemporaryDirectory(dir=output) as tmp:
        draft = Path(tmp) / preview.name
        write_csv(draft, REVIEW, rows)
        draft.replace(preview)
    print(f"Đã lưu {len(completed)}/{len(articles)} bài đủ hai vế, {len(rows)} cặp chính văn.", flush=True)
    if completed:
        print(f"Bài cuối có kết quả theo thứ tự sách: {completed[-1]}", flush=True)
    print(preview, flush=True)


def show_progress(book, *, follow):
    output = book / OUTPUT_DIR
    cache_file = book / ".cache" / ALIGNMENT_CACHE
    metadata = article_metadata(book)
    groups = volume_groups(book)
    prepared = bind_metadata_to_sources(*metadata, groups, pdf_source(book, "viet"))
    articles = {
        name: (han, viet, alignment_fingerprint([unit[0] for unit in han], [unit[0] for unit in viet]))
        for name, (_, _, han, viet) in prepared.items() if han and viet
    }

    previous = None
    while True:
        try:
            snapshot = cache_file.read_bytes()
        except FileNotFoundError:
            snapshot = b"{}"
        if snapshot != previous:
            checkpoints = json.loads(snapshot)
            if not isinstance(checkpoints, dict):
                raise ValueError(f"Cache dóng không hợp lệ: {cache_file}")
            write_preview(output, articles, checkpoints)
            previous = snapshot
        if not needs_alignment(output):
            print(f"Bảng dóng hoàn chỉnh: {output / 'sua.csv'}", flush=True)
            return
        if not follow:
            return
        time.sleep(4)
