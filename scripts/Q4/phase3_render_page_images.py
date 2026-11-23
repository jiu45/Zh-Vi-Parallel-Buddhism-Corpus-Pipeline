"""Render both source PDFs to named page JPEGs without OCR or alignment."""
import csv
from pathlib import Path

import pymupdf
from PIL import Image

DPI = 200


def page_image(page, han):
    colors = pymupdf.csGRAY if han else pymupdf.csRGB
    pix = page.get_pixmap(dpi=DPI, colorspace=colors, alpha=False)
    image = Image.frombytes("L" if han else "RGB", (pix.width, pix.height), pix.samples)
    if han:
        # Same intensity clipping used by phase3_ocr_han.py on the scanned volume.
        image = image.point([max(0, min(255, int((i - 60) * 255 / 105))) for i in range(256)])
    return image


def save_jpg(image, path):
    image.save(path, "JPEG", quality=92, dpi=(DPI, DPI))


def export(sources, dest):
    with (dest/"doi_chieu_trang.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(("source_pdf", "page", "image_path", "width", "height"))
        for lang, folder in (("han", "ch"), ("viet", "vi")):
            pdf = sources[lang]
            (dest/folder).mkdir()
            with pymupdf.open(pdf) as doc:
                for number, page in enumerate(doc, 1):
                    name = Path(folder)/f"{pdf.stem}.{number:03d}.jpg"
                    image = page_image(page, lang == "han")
                    save_jpg(image, dest/name)
                    writer.writerow((pdf.name, number, name.as_posix(), *image.size))
                print(f"{folder}: {len(doc)} JPG")

