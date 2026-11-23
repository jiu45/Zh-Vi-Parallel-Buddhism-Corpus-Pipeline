# -*- coding: utf-8 -*-
"""Count clauses delimited by the round dot (。 U+3002) in 02_ocr_tho/han.

Each 。 closes exactly one clause, so clauses == number of 。.
Also reports 、 (U+3001) which some pages use as an extra pause mark.
"""
import csv
import glob
import os
import sys

DIR = os.path.join("CV09_AQPSVS_Q2", "02_ocr_tho", "han")
OUT = "count_han_clauses.csv"

files = sorted(glob.glob(os.path.join(DIR, "*.txt")))
rows = []
for path in files:
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    body = "".join(text.split("\n"))
    rows.append(
        {
            "file": os.path.basename(path),
            "chars": len(body),
            "clauses": text.count("。"),
            "pause_ideo_comma": text.count("、"),
            "lines_without_dot": sum(1 for ln in text.splitlines() if ln.strip() and "。" not in ln),
            "ends_with_dot": text.rstrip().endswith("。"),
        }
    )

total_clauses = sum(r["clauses"] for r in rows)
total_chars = sum(r["chars"] for r in rows)
total_pause = sum(r["pause_ideo_comma"] for r in rows)
counts = sorted(r["clauses"] for r in rows)
n = len(rows)

with open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

print(f"files                     : {n}")
print(f"total chars (no newlines) : {total_chars}")
print(f"total clauses by 。       : {total_clauses}")
print(f"mean clauses / page       : {total_clauses / n:.2f}")
print(f"median clauses / page     : {counts[n // 2] if n % 2 else (counts[n // 2 - 1] + counts[n // 2]) / 2}")
print(f"min / max per page        : {counts[0]} / {counts[-1]}")
print(f"mean chars / clause       : {total_chars / total_clauses:.2f}")
print(f"pages ending with 。      : {sum(1 for r in rows if r['ends_with_dot'])} / {n}")
print(f"pages that also use 、    : {sum(1 for r in rows if r['pause_ideo_comma'])} , total 、 = {total_pause}")
print(f"clauses if 、 counted too : {total_clauses + total_pause}")
print(f"csv                       : {OUT}")
