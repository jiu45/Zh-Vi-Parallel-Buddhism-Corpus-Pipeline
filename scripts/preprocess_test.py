# -*- coding: utf-8 -*-
import os
import sys
import numpy as np
from PIL import Image
import pymupdf

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ZH_PDF = os.environ.get("ZH_PDF_PATH", str(BASE_DIR / "CV09_AQPSVS_Q3" / "01_nguon" / "han" / "Ấn Quang Pháp Sư Văn Sao - Zh - 3.pdf"))
CLEANED_DIR = os.environ.get("CLEANED_DIR", str(BASE_DIR / "CV09_AQPSVS_Q3" / "02_ocr_tho" / "cleaned_pages"))
os.makedirs(CLEANED_DIR, exist_ok=True)

doc = pymupdf.open(ZH_PDF)
print(f"Opened Chinese PDF with {len(doc)} pages.")

# Preprocess pages 3 to 15
for pno in range(3, 16):
    out_img = os.path.join(CLEANED_DIR, f"page_{pno:04d}.png")
    if os.path.exists(out_img):
        print(f"Page {pno} already cleaned, skipping render.")
        continue
    page = doc[pno - 1]
    pix = page.get_pixmap(dpi=200, colorspace=pymupdf.csGRAY)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    clipped = np.clip((img.astype(np.float32) - 60) * (255.0 / (165 - 60)), 0, 255).astype(np.uint8)
    Image.fromarray(clipped).save(out_img)
    print(f"Rendered & cleaned page {pno:04d} -> {out_img}")

print("Preprocessing complete!")
