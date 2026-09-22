#!/usr/bin/env python3
"""dedup_json - drop duplicate records from a JSON array or JSONL file.

Default behaviour dedupes on the entire record (all keys, values compared
after normalising whitespace in strings). Pass --keys to dedupe on a subset.

--keep first (default) keeps the first occurrence, --keep last keeps the last.
This matters when later records are corrections to earlier ones.

Example:
  dedup_json.py events.jsonl --keys id --keep last -o events.clean.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_rows(path: Path) -> tuple[list, bool]:
    """Return (rows, was_jsonl)."""
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if not stripped:
        return [], path.suffix == ".jsonl"
    if stripped[0] == "[":
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("top-level JSON must be an array")
        return data, False
    rows = []
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {lineno}: invalid JSON ({exc.msg})") from exc
    return rows, True


def normalise(value):
    """Make hashing stable: sort dict keys, strip strings, keep types distinct."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return {k: normalise(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [normalise(v) for v in value]
    return value


def key_for(row, keys: list[str] | None):
    if keys is None:
        return json.dumps(normalise(row), sort_keys=True, ensure_ascii=False)
    return json.dumps({k: normalise(row.get(k)) for k in keys},
                      sort_keys=True, ensure_ascii=False)


def dedupe(rows: list, keys: list[str] | None, keep: str) -> tuple[list, int]:
    if keep == "first":
        seen: dict[str, int] = {}
        for idx, row in enumerate(rows):
            seen.setdefault(key_for(row, keys), idx)
        kept = [rows[i] for i in sorted(seen.values())]
    else:  # keep last
        seen_last: dict[str, int] = {}
        for idx, row in enumerate(rows):
            seen_last[key_for(row, keys)] = idx
        kept = [rows[i] for i in sorted(seen_last.values())]
    return kept, len(rows) - len(kept)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Deduplicate JSON records.")
    p.add_argument("input", type=Path, help="input .json / .jsonl")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="output path (default: stdout)")
    p.add_argument("--keys", default=None,
                   help="comma-separated keys to compare, e.g. id,email")
    p.add_argument("--keep", choices=["first", "last"], default="first",
                   help="which duplicate to keep (default: first)")
    p.add_argument("--indent", type=int, default=None,
                   help="pretty-print JSON with this indent")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.input.exists():
        print(f"error: {args.input} not found", file=sys.stderr)
        return 2

    try:
        rows, was_jsonl = load_rows(args.input)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    keys = [k.strip() for k in args.keys.split(",")] if args.keys else None
    if keys:
        missing = sorted({k for k in keys if rows and k not in rows[0]})
        if missing:
            print(f"warning: keys not present in first record: {', '.join(missing)}",
                  file=sys.stderr)

    kept, removed = dedupe(rows, keys, args.keep)

    # Preserve the input shape: JSONL in -> JSONL out.
    if was_jsonl:
        text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept)
    else:
        text = json.dumps(kept, ensure_ascii=False, indent=args.indent)

    if args.output:
        args.output.write_text(text if text.endswith("\n") else text + "\n",
                               encoding="utf-8")
    else:
        print(text, end="" if text.endswith("\n") else "\n")

    print(f"kept {len(kept)} of {len(rows)} records ({removed} removed)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
