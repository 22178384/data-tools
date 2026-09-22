#!/usr/bin/env python3
"""csv_to_parquet - CSV to Parquet via pandas + pyarrow.

Nothing clever here, this is a thin wrapper. The reason it exists: I got
tired of remembering the right engine / compression incantation, and of
pyarrow silently reinterpreting my integer columns as strings.

Options I actually use:
  --dtypes dtypes.json   force column types, e.g. {"zip": "string"}
  --compression          snappy (default), gzip, zstd, none
  --index                keep the pandas index (off by default)

pyarrow is a heavy dependency. I do NOT import it at module load so that
--help still works on a box where it isn't installed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None

MISSING_PANDAS = "error: pandas is not installed. run: pip install pandas"
MISSING_PYARROW = ("error: pyarrow is not installed (needed to write Parquet). "
                   "run: pip install pyarrow")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert CSV to Parquet.")
    p.add_argument("input", type=Path, help="input .csv file")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="output .parquet path (default: input stem + .parquet)")
    p.add_argument("--delimiter", default=",", help="CSV delimiter (default: ,)")
    p.add_argument("--compression", default="snappy",
                   choices=["snappy", "gzip", "zstd", "none", "brotli"],
                   help="Parquet compression (default: snappy)")
    p.add_argument("--dtypes", type=Path, default=None,
                   help="JSON file mapping column -> dtype")
    p.add_argument("--index", action="store_true", help="write the pandas index")
    p.add_argument("--chunk", type=int, default=0,
                   help="read in chunks of N rows (0 = all at once)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if pd is None:
        print(MISSING_PANDAS, file=sys.stderr)
        return 2
    if not args.input.exists():
        print(f"error: {args.input} not found", file=sys.stderr)
        return 2

    dtypes = None
    if args.dtypes:
        dtypes = json.loads(args.dtypes.read_text(encoding="utf-8"))

    read_kwargs = {"sep": args.delimiter, "dtype": dtypes}
    try:
        if args.chunk and args.chunk > 0:
            parts = [chunk for chunk in
                     pd.read_csv(args.input, chunksize=args.chunk, **read_kwargs)]
            if not parts:
                print("error: no data read", file=sys.stderr)
                return 1
            df = pd.concat(parts, ignore_index=True)
        else:
            df = pd.read_csv(args.input, **read_kwargs)
    except Exception as exc:  # pandas raises a zoo of exceptions
        print(f"error: could not read CSV: {exc}", file=sys.stderr)
        return 1

    out = args.output or args.input.with_suffix(".parquet")
    try:
        df.to_parquet(out, engine="pyarrow", index=args.index,
                      compression=args.compression)
    except ImportError:
        print(MISSING_PYARROW, file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"error: could not write Parquet: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {len(df)} rows x {len(df.columns)} cols to {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
