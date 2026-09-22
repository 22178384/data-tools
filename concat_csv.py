#!/usr/bin/env python3
"""concat_csv - stack a bunch of CSVs into one.

The annoying part of this is columns that don't line up. Options:

  default     union of all columns; missing values become empty
  --intersect only keep columns present in every file
  --add-source append a column with the originating filename

Header comparison is exact (whitespace stripped). If your exports have
" Name" vs "Name", fix it upstream, don't make this tool guess.

Example:
  concat_csv.py exports/*.csv -o all.csv --add-source --dedupe
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def read_header(path: Path, delimiter: str) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh, delimiter=delimiter)
        try:
            return [h.strip() for h in next(reader)]
        except StopIteration:
            return []


def iter_rows(path: Path, delimiter: str, columns: list[str],
              source: str | None) -> list[dict]:
    out = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh, delimiter=delimiter)
        try:
            header = [h.strip() for h in next(reader)]
        except StopIteration:
            return out
        for values in reader:
            if not values:
                continue
            # Pad short rows so zip() doesn't silently truncate.
            if len(values) < len(header):
                values = values + [""] * (len(header) - len(values))
            row = dict(zip(header, values))
            record = {c: row.get(c, "") for c in columns}
            if source is not None:
                record[source] = path.name
            out.append(record)
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Concatenate CSV files.")
    p.add_argument("inputs", nargs="+", type=Path, help="input CSV files")
    p.add_argument("-o", "--output", type=Path, required=True, help="output CSV")
    p.add_argument("--delimiter", default=",", help="CSV delimiter (default: ,)")
    p.add_argument("--intersect", action="store_true",
                   help="keep only columns common to all files")
    p.add_argument("--add-source", action="store_true",
                   help="add a _source column with the filename")
    p.add_argument("--dedupe", action="store_true",
                   help="drop exact duplicate rows")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    files = [p for p in args.inputs if p.exists()]
    missing = [str(p) for p in args.inputs if not p.exists()]
    for m in missing:
        print(f"warning: skipping missing file {m}", file=sys.stderr)
    if not files:
        print("error: no readable input files", file=sys.stderr)
        return 2

    headers = {p: read_header(p, args.delimiter) for p in files}
    all_cols: list[str] = []
    seen = set()
    for p in files:
        for col in headers[p]:
            if col not in seen:
                seen.add(col)
                all_cols.append(col)

    if args.intersect:
        common = set(headers[files[0]])
        for p in files[1:]:
            common &= set(headers[p])
        columns = [c for c in all_cols if c in common]
        dropped = [c for c in all_cols if c not in common]
        if dropped:
            print(f"note: dropping {len(dropped)} non-common column(s): "
                  f"{', '.join(dropped)}", file=sys.stderr)
    else:
        columns = all_cols

    source_col = "_source" if args.add_source else None
    rows: list[dict] = []
    for p in files:
        rows.extend(iter_rows(p, args.delimiter, columns, source_col))

    if args.dedupe:
        before = len(rows)
        uniq: list[dict] = []
        seen_rows = set()
        for r in rows:
            key = tuple(r.get(c, "") for c in columns)
            if key not in seen_rows:
                seen_rows.add(key)
                uniq.append(r)
        rows = uniq
        print(f"dedupe: removed {before - len(rows)} duplicate row(s)",
              file=sys.stderr)

    fieldnames = columns + ([source_col] if source_col else [])
    with args.output.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {len(rows)} rows x {len(fieldnames)} cols to {args.output}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
