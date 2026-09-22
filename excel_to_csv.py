#!/usr/bin/env python3
"""excel_to_csv - one sheet (or all sheets) from an .xlsx to CSV.

Uses openpyxl under the hood via pandas.read_excel. Formulas are NOT
evaluated: openpyxl reads the cached value, and if the file was never opened
by Excel the cache can be empty (you get NaN). Nothing I can do about that
without a real Excel engine. Save from Excel/LibreOffice first if it matters.

Examples:
  excel_to_csv.py book.xlsx                    # first sheet
  excel_to_csv.py book.xlsx --sheet "Q3 2024"
  excel_to_csv.py book.xlsx --all-sheets -d out/
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None

MISSING = ("error: pandas + openpyxl are required. "
           "run: pip install pandas openpyxl")


def safe_name(name: str) -> str:
    # Sheet names can contain '/', ':' etc. which are illegal in filenames.
    cleaned = re.sub(r"[^\w\-. ]+", "_", str(name)).strip(" .")
    return cleaned or "sheet"


def export(df, dest: Path, delimiter: str) -> None:
    df.to_csv(dest, index=False, sep=delimiter, encoding="utf-8-sig")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert Excel sheets to CSV.")
    p.add_argument("input", type=Path, help="input .xlsx / .xlsm file")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="output CSV path (single-sheet mode only)")
    p.add_argument("--sheet", default=None,
                   help="sheet name or 0-based index (default: first sheet)")
    p.add_argument("--all-sheets", action="store_true",
                   help="export every sheet, one CSV each")
    p.add_argument("-d", "--outdir", type=Path, default=Path("."),
                   help="directory for --all-sheets output (default: .)")
    p.add_argument("--header-row", type=int, default=0,
                   help="0-based row to use as the header (default: 0)")
    p.add_argument("--delimiter", default=",", help="CSV delimiter (default: ,)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if pd is None:
        print(MISSING, file=sys.stderr)
        return 2
    if not args.input.exists():
        print(f"error: {args.input} not found", file=sys.stderr)
        return 2

    sheet_arg = args.sheet
    if sheet_arg is not None and sheet_arg.isdigit():
        sheet_arg = int(sheet_arg)

    try:
        book = pd.ExcelFile(args.input, engine="openpyxl")
    except ImportError:
        print(MISSING, file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"error: could not open {args.input}: {exc}", file=sys.stderr)
        return 1

    if args.all_sheets:
        args.outdir.mkdir(parents=True, exist_ok=True)
        count = 0
        for name in book.sheet_names:
            try:
                df = book.parse(name, header=args.header_row)
            except Exception as exc:
                print(f"warning: skipped sheet {name!r}: {exc}", file=sys.stderr)
                continue
            dest = args.outdir / f"{args.input.stem}__{safe_name(name)}.csv"
            export(df, dest, args.delimiter)
            print(f"{name} -> {dest} ({len(df)} rows)", file=sys.stderr)
            count += 1
        if count == 0:
            print("error: no sheets exported", file=sys.stderr)
            return 1
        return 0

    try:
        df = book.parse(sheet_arg if sheet_arg is not None else 0,
                        header=args.header_row)
    except Exception as exc:
        print(f"error: could not read sheet {sheet_arg!r}: {exc}", file=sys.stderr)
        return 1

    dest = args.output or args.input.with_suffix(".csv")
    export(df, dest, args.delimiter)
    print(f"wrote {len(df)} rows x {len(df.columns)} cols to {dest}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
