#!/usr/bin/env python3
"""schema_infer - guess column types from a CSV or JSON file.

I wrote this to answer one question quickly: "what's actually in this dump?"
It reads up to --sample rows (default 1000), reports a type per column, the
null rate, and a couple of examples.

Output is either a markdown table (for pasting into a PR or a doc) or JSON.

Type vocabulary is deliberately small: integer, number, boolean, date,
datetime, string, mixed, empty. If a column is 'mixed' the tool also tells
you which types it saw, because that's usually the interesting part.

Caveat: this is heuristic. Leading-zero IDs ("007") are strings. Numbers with
a comma thousand-separator are strings too. Don't feed the output straight
into a DDL and expect it to be right.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

INT_RE = re.compile(r"^[+-]?\d+$")
NUM_RE = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")
BOOL_RE = re.compile(r"^(true|false|yes|no)$", re.IGNORECASE)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?")

NULLS = {"", "null", "none", "na", "n/a", "nan", "-"}


def classify(value) -> str:
    if value is None:
        return "empty"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    s = str(value).strip()
    if s.lower() in NULLS:
        return "empty"
    if INT_RE.match(s):
        # "007" is a zip code / ID, not an integer. Leading zeros are a
        # deliberate signal that the field is really a string.
        digits = s.lstrip("+-")
        if len(digits) > 1 and digits[0] == "0":
            return "string"
        return "integer"
    if NUM_RE.match(s):
        return "number"
    if BOOL_RE.match(s):
        return "boolean"
    if DATE_RE.match(s):
        return "date"
    if DATETIME_RE.match(s):
        return "datetime"
    return "string"


def merge(types: Counter) -> str:
    real = {t for t in types if t != "empty"}
    if not real:
        return "empty"
    if len(real) == 1:
        return next(iter(real))
    # integer + number is just number, not "mixed".
    if real <= {"integer", "number"}:
        return "number"
    return "mixed"


def load_rows(path: Path) -> tuple[list[dict], str]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh)), "csv"
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped[:1] == "[":
        return json.loads(text), "json"
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    return rows, "jsonl"


def infer(rows: list[dict], sample: int) -> list[dict]:
    rows = rows[:sample]
    columns: list[str] = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                columns.append(key)

    report = []
    for col in columns:
        types: Counter = Counter()
        examples: list[str] = []
        nulls = 0
        for row in rows:
            raw = row.get(col)
            t = classify(raw)
            types[t] += 1
            if t == "empty":
                nulls += 1
            elif len(examples) < 3:
                s = str(raw)
                if s not in examples:
                    examples.append(s[:40])
        total = len(rows) or 1
        report.append({
            "column": col,
            "type": merge(types),
            "null_pct": round(100.0 * nulls / total, 1),
            "examples": examples,
            "breakdown": dict(types) if len({t for t in types if t != "empty"}) > 1 else {},
        })
    return report


def as_markdown(report: list[dict]) -> str:
    lines = ["| column | type | null % | examples |", "| --- | --- | --- | --- |"]
    for r in report:
        ex = ", ".join(f"`{e}`" for e in r["examples"]) or ""
        lines.append(f"| `{r['column']}` | {r['type']} | {r['null_pct']} | {ex} |")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Infer column types from CSV/JSON.")
    p.add_argument("input", type=Path)
    p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p.add_argument("--sample", type=int, default=1000,
                   help="rows to inspect (default: 1000)")
    p.add_argument("-o", "--output", type=Path, default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.input.exists():
        print(f"error: {args.input} not found", file=sys.stderr)
        return 2
    try:
        rows, kind = load_rows(args.input)
    except (json.JSONDecodeError, csv.Error) as exc:
        print(f"error: could not parse {args.input}: {exc}", file=sys.stderr)
        return 1

    if not rows:
        print("error: file has no records", file=sys.stderr)
        return 1

    report = infer(rows, args.sample)
    text = (as_markdown(report) if args.format == "markdown"
            else json.dumps(report, indent=2, ensure_ascii=False))

    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    print(f"# {len(rows)} {kind} records, {len(report)} columns",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
