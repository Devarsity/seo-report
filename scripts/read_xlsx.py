#!/usr/bin/env python3
"""
read_xlsx.py — Dump an Excel workbook to JSON so the model can read a
user-supplied SEO checklist without guessing its layout.

Checklists vary wildly: different sheet names, column orders, extra notes.
Rather than hard-code a parser, this prints every sheet's rows as JSON and lets
the model map them into the report's `checklist` block. It flags the sheet whose
rows look most like a status/checklist (has a column resembling status / result
/ pass-fail) to save the model a scan.

Usage:
    python read_xlsx.py checklist.xlsx            # human-readable to stdout
    python read_xlsx.py checklist.xlsx -o wb.json # also write JSON
"""

import argparse
import json
import sys

try:
    import openpyxl
except ImportError:
    sys.exit("Install openpyxl:\n  pip install --break-system-packages openpyxl")

STATUS_HINTS = ("status", "result", "pass", "fail", "check", "outcome")
LINK_HINTS = ("url", "link", "http")


def row_vals(row):
    return ["" if c is None else (c if isinstance(c, (int, float)) else str(c).strip())
            for c in row]


def dump(path):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    out = {"file": path, "sheets": []}
    for ws in wb.worksheets:
        rows = [row_vals(r) for r in ws.iter_rows(values_only=True)]
        rows = [r for r in rows if any(str(c).strip() for c in r)]  # drop blank rows
        header = rows[0] if rows else []
        header_l = " ".join(str(h).lower() for h in header)
        sheet = {
            "name": ws.title,
            "looks_like_checklist": any(h in header_l for h in STATUS_HINTS),
            "looks_like_links": any(h in header_l for h in LINK_HINTS),
            "header": header,
            "rows": rows[1:] if rows else [],
            "row_count": max(0, len(rows) - 1),
        }
        out["sheets"].append(sheet)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("-o", "--output")
    args = ap.parse_args()

    data = dump(args.path)

    # Compact, readable summary to stdout.
    for s in data["sheets"]:
        tags = []
        if s["looks_like_checklist"]:
            tags.append("CHECKLIST")
        if s["looks_like_links"]:
            tags.append("LINKS")
        print(f"\n=== Sheet: {s['name']} ({s['row_count']} rows) "
              f"{' '.join(tags)} ===")
        print("Header:", s["header"])
        for r in s["rows"][:40]:
            print("  ", r)
        if s["row_count"] > 40:
            print(f"   ... {s['row_count'] - 40} more rows")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()
