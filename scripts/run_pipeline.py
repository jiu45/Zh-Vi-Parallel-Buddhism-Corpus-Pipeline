"""Chạy từng bước xử lý Quyển II hoặc Quyển IV."""
import argparse
import fcntl
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("buoc", choices=[
        "kiem-tra", "anh", "ocr", "moc-bai", "tach-cau", "dong-hang", "tien-do", "dong-goi", "all",
    ], help="Kiểm tra PDF, xuất ảnh, OCR, tách câu, dóng hàng, xem tiến độ, đóng gói hoặc chạy từ OCR đến ZIP")
    parser.add_argument("--gemini", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--quyen", choices=("Q2", "Q4"), default="Q4", help="Quyển cần xử lý")
    parser.add_argument("--model", default=os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"),
                        help="Tên model Gemini dùng để dóng hàng hoặc OCR")
    parser.add_argument("--nhom", help="Tên ZIP theo MSSV nhóm")
    parser.add_argument("--ten-sach", help="Tên thư mục sách và các bảng dóng trong ZIP")
    parser.add_argument("--bao-cao", type=Path, help="PDF báo cáo đã hoàn thiện")
    parser.add_argument("--theo-doi", action="store_true", help="Cập nhật tiến độ khi cache dóng thay đổi")
    args = parser.parse_args()
    if args.theo_doi and args.buoc != "tien-do":
        parser.error("--theo-doi dùng với bước tien-do.")

    try:
        run(args)
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        parser.exit(1, f"{args.quyen}: {error}\n")


def run(args):
    book = ROOT / f"CV09_AQPSVS_{args.quyen}"
    if args.buoc == "tien-do":
        from alignment_progress import show_progress

        try:
            show_progress(book, follow=args.theo_doi)
        except KeyboardInterrupt:
            print("\nĐã dừng xem tiến độ.")
        return

    import pymupdf
    from phase3_render_page_images import export
    from phase4_align_and_export import (
        OUTPUT_DIR, layout, needs_alignment, needs_ocr, package, pdf_source, prepare_volume,
    )
    from segment_articles import ARTICLE_FILES

    output = book / OUTPUT_DIR
    sources = {language: pdf_source(book, language) for language in ("han", "viet")}
    for language, path in sources.items():
        with pymupdf.open(path) as doc:
            table = layout(language, len(doc), book=book)
            print(f"{language}: {len(doc)} trang | {path.name}")
            if args.buoc == "kiem-tra" and language == "viet" and args.quyen == "Q2":
                from q2_anchors import check_viet_anchors
                check_viet_anchors(doc, table)
    if args.buoc == "kiem-tra":
        return

    cache = book / ".cache"
    cache.mkdir(exist_ok=True)
    with (cache / f"run-{args.quyen.lower()}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.buoc == "anh":
            destination = book / "anh_trang"
            if destination.exists():
                raise ValueError(f"Đã có ảnh ở {destination}.")
            with tempfile.TemporaryDirectory(dir=book) as tmp:
                export(sources, Path(tmp))
                Path(tmp).rename(destination)
            print(destination)
            return

        if args.buoc == "moc-bai":
            from phase4_align_and_export import read_records
            from q2_anchors import write_anchors

            if args.quyen != "Q2":
                raise ValueError("Q4 đã có bảng mốc trong scripts/Q4/anchor_map.csv.")
            if needs_ocr(output):
                raise ValueError("Chạy bước ocr trước khi tìm mốc Q2.")
            write_anchors(book, read_records(output))
            return

        step = {"ocr": "ocr", "tach-cau": "tach", "dong-hang": "ghep", "dong-goi": "goi", "all": "all"}[args.buoc]
        if step in {"tach", "ghep", "goi"} and needs_ocr(output):
            raise ValueError("Chạy bước ocr để tạo OCR Hán bằng Gemini trước.")
        if step == "ghep" and not all((book / "metadata" / name).is_file() for name in ARTICLE_FILES):
            raise ValueError("Cần hai file metadata Hán và Việt. Chạy bước tach-cau trước.")
        if step == "goi" and not (output / "sua.csv").is_file():
            raise ValueError("Chạy bước dong-hang trước.")
        if step == "goi" and needs_alignment(output):
            raise ValueError("Bảng dóng chưa khớp phương pháp hoặc metadata hiện tại. Chạy dong-hang trước.")
        use_gemini_ocr = step in {"ocr", "all"} and needs_ocr(output)
        use_gemini_alignment = step in {"ghep", "all"} and (use_gemini_ocr or needs_alignment(output))
        gemini = None
        if use_gemini_ocr or use_gemini_alignment:
            from phase3_ocr_han import GeminiQ4
            gemini = GeminiQ4(args.model, volume=args.quyen)
        prepare_volume(book, step, gemini)
        if step in {"goi", "all"}:
            package(book, args)


if __name__ == "__main__":
    main()
