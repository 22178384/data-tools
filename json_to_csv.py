#!/usr/bin/env python3
"""json_to_csv - flatten a JSON array (or JSONL file) into CSV.

Design notes / decisions I made:

* Nested dicts are flattened with dot notation: {"a": {"b": 1}} -> a.b
* Lists are dumped back to a JSON string in a single cell. Exploding arrays
  into columns sounds nice until the arrays have different lengths, then it's
  a mess. If you want one row per array element, that's a different tool.
* Input is auto-detected: a file starting with '[' is parsed as a JSON array,
  anything else is treated as JSON Lines.
* Output is UTF-8 with a BOM by default on Windows because Excel mangles
  non-ASCII otherwise. Pass --no-bom to turn that off.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def flatten(obj: dict, prefix: str = "", sep: str = ".") -> dict:
    out: dict = {}
    for key, value in obj.items():
        name = f"{prefix}{sep}{key}" if prefix else str(key)
        if isinstance(value, dict):
            out.update(flatten(value, name, sep))
        elif isinstance(value, list):
            out[name] = json.dumps(value, ensure_ascii=False)
        else:
            out[name] = value
    return out


def load_rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if not stripped:
        return []
    if stripped[0] == "[":
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("top-level JSON must be an array")
        return data
    rows = []
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {lineno}: invalid JSON ({exc.msg})") from exc
    return rows


def write_csv(rows: list[dict], out_path: Path | None, delimiter: str,
              bom: bool, do_flatten: bool, sep: str) -> int:
    if do_flatten:
        rows = [flatten(r, sep=sep) if isinstance(r, dict) else {"value": r}
                for r in rows]

    # Column order: first-seen wins. This keeps the output stable-ish and
    # matches the file, which is what people actually want when eyeballing it.
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                columns.append(key)

    if not columns:
        columns = []

    encoding = "utf-8-sig" if bom else "utf-8"
    handle = (out_path.open("w", encoding=encoding, newline="")
              if out_path else sys.stdout)
    try:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter=delimiter,
                                extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})
    finally:
        if out_path:
            handle.close()
    return len(rows)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert JSON/JSONL to CSV.")
    p.add_argument("input", type=Path, help="input .json or .jsonl file")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="output CSV path (default: stdout)")
    p.add_argument("--delimiter", default=",",
                   help="CSV delimiter, e.g. ';' (default: ,)")
    p.add_argument("--sep", default=".", help="separator for flattened keys")
    p.add_argument("--no-flatten", action="store_true",
                   help="leave nested objects as JSON strings")
    p.add_argument("--no-bom", action="store_true",
                   help="do not write a UTF-8 BOM")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.input.exists():
        print(f"error: {args.input} not found", file=sys.stderr)
        return 2
    try:
        rows = load_rows(args.input)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"error: could not parse {args.input}: {exc}", file=sys.stderr)
        return 1
    if not rows:
        print("warning: no rows found", file=sys.stderr)

    n = write_csv(rows, args.output, args.delimiter,
                  bom=not args.no_bom, do_flatten=not args.no_flatten,
                  sep=args.sep)
    if args.output:
        print(f"wrote {n} rows to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
