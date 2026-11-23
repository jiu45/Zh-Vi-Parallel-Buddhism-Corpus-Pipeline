"""Chạy từng bước xử lý Quyển IV."""
import argparse
import fcntl
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BOOK = ROOT / "CV09_AQPSVS_Q4"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("buoc", choices=["kiem-tra", "anh", "ocr", "dong-hang", "dong-goi", "all"],
                        help="Kiểm tra PDF, xuất ảnh, OCR, dóng hàng, đóng gói hoặc chạy từ OCR đến ZIP")
    parser.add_argument("--gemini", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--model", default=os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"),
                        help="Tên model Gemini dùng để dóng hàng hoặc OCR")
    parser.add_argument("--nhom", help="Tên ZIP theo MSSV nhóm")
    parser.add_argument("--ten-sach", help="Tên thư mục sách và các bảng dóng trong ZIP")
    parser.add_argument("--bao-cao", type=Path, help="PDF báo cáo đã hoàn thiện")
    args = parser.parse_args()

    try:
        run(args)
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        parser.exit(1, f"Q4: {error}\n")


def run(args):
    import pymupdf
    from phase3_render_page_images import export
    from phase4_align_and_export import (
        OUTPUT_DIR, layout, needs_alignment, needs_ocr, package, pdf_source, prepare_volume,
    )

    output = BOOK / OUTPUT_DIR
    sources = {language: pdf_source(BOOK, language) for language in ("han", "viet")}
    for language, path in sources.items():
        with pymupdf.open(path) as doc:
            layout(language, len(doc))
            print(f"{language}: {len(doc)} trang | {path.name}")
    if args.buoc == "kiem-tra":
        return

    cache = BOOK / ".cache"
    cache.mkdir(exist_ok=True)
    with (cache / "run-q4.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.buoc == "anh":
            destination = BOOK / "anh_trang"
            if destination.exists():
                raise ValueError(f"Đã có ảnh ở {destination}.")
            with tempfile.TemporaryDirectory(dir=BOOK) as tmp:
                export(sources, Path(tmp))
                Path(tmp).rename(destination)
            print(destination)
            return

        step = {"ocr": "ocr", "dong-hang": "ghep", "dong-goi": "goi", "all": "all"}[args.buoc]
        if step in {"ghep", "goi"} and not (output / "trang.csv").is_file():
            raise ValueError("Chạy bước ocr trước.")
        if step in {"ghep", "goi"} and needs_ocr(output):
            raise ValueError("Chạy bước ocr để tạo OCR Hán bằng Gemini trước.")
        if step == "goi" and not (output / "sua.csv").is_file():
            raise ValueError("Chạy bước dong-hang trước.")
        if step == "goi" and needs_alignment(output):
            raise ValueError("Bảng dóng hiện tại thuộc phương pháp cũ. Chạy dong-hang trước khi đóng gói.")
        use_gemini_ocr = step in {"ocr", "all"} and needs_ocr(output)
        use_gemini_alignment = step in {"ghep", "all"} and (use_gemini_ocr or needs_alignment(output))
        gemini = None
        if use_gemini_ocr or use_gemini_alignment:
            from phase3_ocr_han import GeminiQ4
            gemini = GeminiQ4(args.model)
        prepare_volume(BOOK, step, gemini)
        if step in {"goi", "all"}:
            package(BOOK, args)


if __name__ == "__main__":
    main()
