# -*- coding: utf-8 -*-
"""Count Vietnamese sentences in CV09_AQPSVS_Q2/02_ocr_tho/viet.

A sentence is a run of text closed by . ! or ?, optionally followed by a closing
quote. OCR/typographic patterns that are NOT sentence ends are neutralised first:

  thousands separators   1.773  2.500  024.39260024
  abbreviation           v.v.   v.v..  tr.CN  tr. CN  TP.HCM  P. Bình Tân
  roman-numeral headings I. THƯ TỪ   II. LUẬN
  ellipsis runs          ...  (… stays an ellipsis: 43 cases, name masking)
"""
import csv
import glob
import os
import re

DIR = os.path.join("CV09_AQPSVS_Q2", "02_ocr_tho", "viet")
OUT = "count_viet_sentences.csv"

RULES = [
    (re.compile(r"(?<=\d)\.(?=\d)"), ""),          # thousands separators, phones
    (re.compile(r"v\.v\.(?=\.)"), "vv"),           # v.v.. -> vv.
    (re.compile(r"v\.v\."), "vv"),                 # v.v.  -> vv
    (re.compile(r"\btr\.(?=\s*(?:CN|cn)\b)"), "tr"),   # tr.CN / tr. CN
    (re.compile(r"\b(?:TP|TT|TS|GS|P|Q|X)\.(?=\s*[A-ZĐ])"), lambda m: m.group(0)[:-1]),
    (re.compile(r"(?<=\s)(?:I{1,3}|IV)\.(?=\s[A-ZĐ])"), lambda m: m.group(0)[:-1]),
    (re.compile(r"\.{2,}"), "\u2026"),
]
WS = re.compile(r"\s+")
TERM = re.compile(r"[.!?]+(?=[ \t]*[\u201d\u2019\"'\)\]]*(?:\s|$))")


def clean(text):
    t = text
    for pat, repl in RULES:
        t = pat.sub(repl, t)
    return WS.sub(" ", t).strip()


def main():
    files = sorted(glob.glob(os.path.join(DIR, "*.txt")))
    rows = []
    totals = {"sentences": 0, "dots": 0, "excl": 0, "quest": 0, "ellipsis": 0}
    for path in files:
        raw = open(path, encoding="utf-8").read()
        t = clean(raw)
        n = len(TERM.findall(t))
        n_dot = len(re.findall(r"\.+(?=[ \t]*[\u201d\u2019\"'\)\]]*(?:\s|$))", t))
        n_excl = len(re.findall(r"!+(?=[ \t]*[\u201d\u2019\"'\)\]]*(?:\s|$))", t))
        n_quest = len(re.findall(r"\?+(?=[ \t]*[\u201d\u2019\"'\)\]]*(?:\s|$))", t))
        rows.append(
            {
                "file": os.path.basename(path),
                "chars": len(WS.sub("", raw)),
                "sentences": n,
                "end_dot": n_dot,
                "end_excl": n_excl,
                "end_quest": n_quest,
                "ellipsis": raw.count("\u2026"),
                "ends_mid_sentence": not bool(
                    re.search(r"[.!?][\u201d\u2019\"'\)\]]*\s*$", raw.rstrip())
                ),
            }
        )
        totals["sentences"] += n
        totals["dots"] += n_dot
        totals["excl"] += n_excl
        totals["quest"] += n_quest
        totals["ellipsis"] += raw.count("\u2026")

    counts = sorted(r["sentences"] for r in rows)
    n_pages = len(rows)
    chars = sum(r["chars"] for r in rows)
    with open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    print(f"files                      : {n_pages}")
    print(f"empty files                : {sum(1 for r in rows if r['chars'] == 0)}")
    print(f"chars (no whitespace)      : {chars}")
    print(f"sentences                  : {totals['sentences']}")
    print(f"  end with .               : {totals['dots']}")
    print(f"  end with !               : {totals['excl']}")
    print(f"  end with ?               : {totals['quest']}")
    print(f"  ellipsis …, not counted  : {totals['ellipsis']}")
    print(f"mean / median per page     : {totals['sentences'] / n_pages:.2f} / "
          f"{counts[n_pages // 2] if n_pages % 2 else (counts[n_pages // 2 - 1] + counts[n_pages // 2]) / 2}")
    print(f"min / max per page         : {counts[0]} / {counts[-1]}")
    print(f"chars / sentence           : {chars / totals['sentences']:.1f}")
    print(f"pages ending mid-sentence  : {sum(1 for r in rows if r['ends_mid_sentence'])}")
    print(f"csv                        : {OUT}")


if __name__ == "__main__":
    main()
