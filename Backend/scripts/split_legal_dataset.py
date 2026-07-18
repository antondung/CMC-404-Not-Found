#!/usr/bin/env python3
"""Tách dataset dạng:

--- VĂN BẢN SỐ N ---
TIÊU ĐỀ: ...
SỐ HIỆU: ...
NGÀY BAN HÀNH: ...
CƠ QUAN BAN HÀNH: ...
NỘI DUNG:
...

thành nhiều file .txt (một văn bản / file) để import_split_legal_txt.py nạp.

USAGE:
  python Backend/scripts/split_legal_dataset.py dataset_thue_tai_chinh_2009_2026.txt -o Data/raw/split_thue
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

_SEP = re.compile(r"^---\s*VĂN BẢN SỐ\s+\d+\s*---\s*$", re.MULTILINE | re.IGNORECASE)
_SO_HIEU = re.compile(r"^SỐ HIỆU:\s*(.+)$", re.MULTILINE | re.IGNORECASE)


def _safe_name(so_hieu: str, index: int) -> str:
    stem = re.sub(r"[^\w.\-]+", "_", so_hieu.strip(), flags=re.UNICODE).strip("_")
    if not stem:
        stem = f"vb_{index:05d}"
    return f"{index:05d}_{stem[:80]}.txt"


def main() -> int:
    ap = argparse.ArgumentParser(description="Split mega legal .txt into per-document files.")
    ap.add_argument("input", type=Path, help="dataset_thue_tai_chinh_2009_2026.txt")
    ap.add_argument("-o", "--out", type=Path, required=True, help="Thư mục output")
    ap.add_argument("--limit", type=int, default=0, help="Chỉ tách N văn bản đầu (0 = hết)")
    args = ap.parse_args()

    raw = args.input.read_text(encoding="utf-8-sig", errors="ignore")
    parts = _SEP.split(raw)
    # parts[0] = preamble before first separator (usually empty)
    docs = [p.strip() for p in parts[1:] if p.strip()]
    if args.limit and args.limit > 0:
        docs = docs[: args.limit]

    args.out.mkdir(parents=True, exist_ok=True)
    written = 0
    for i, body in enumerate(docs, start=1):
        m = _SO_HIEU.search(body)
        so_hieu = m.group(1).strip() if m else f"vb_{i}"
        # Keep full block format expected by import_split_legal_txt.parse_file
        text = f"--- VĂN BẢN SỐ {i} ---\n{body}\n"
        if not body.upper().startswith("TIÊU ĐỀ:") and "TIÊU ĐỀ:" not in body[:200].upper():
            # body already starts with TIÊU ĐỀ after split — fine
            pass
        out = args.out / _safe_name(so_hieu, i)
        out.write_text(text, encoding="utf-8")
        written += 1
        if written % 1000 == 0:
            print(f"  … {written}/{len(docs)}")

    print(f"DONE: {written} files → {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
