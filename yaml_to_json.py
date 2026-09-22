#!/usr/bin/env python3
"""yaml_to_json - convert YAML to JSON. Supports multi-document YAML.

pyyaml is required. If it's missing you get a one-line hint, not a traceback.

Two output modes:
  --ndjson    one JSON object per line (only makes sense for multi-doc input)
  default     a single JSON value; multi-doc input becomes a JSON array
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - depends on the environment
    yaml = None

MISSING_YAML = "error: pyyaml is not installed. run: pip install pyyaml"


def load_documents(text: str) -> list:
    # safe_load_all handles both single and multi-document files.
    return list(yaml.safe_load_all(text))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert YAML to JSON.")
    p.add_argument("input", type=Path, help="input .yml/.yaml file")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="output file (default: stdout)")
    p.add_argument("--indent", type=int, default=2, help="JSON indent (default: 2)")
    p.add_argument("--sort-keys", action="store_true",
                   help="sort object keys alphabetically")
    p.add_argument("--compact", action="store_true",
                   help="no spaces after separators")
    p.add_argument("--ndjson", action="store_true",
                   help="write one JSON value per line")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if yaml is None:
        print(MISSING_YAML, file=sys.stderr)
        return 2
    if not args.input.exists():
        print(f"error: {args.input} not found", file=sys.stderr)
        return 2

    try:
        docs = load_documents(args.input.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"error: invalid YAML in {args.input}: {exc}", file=sys.stderr)
        return 1

    # A trailing '---' produces a None document. Drop those, they're noise.
    docs = [d for d in docs if d is not None]

    if args.ndjson:
        text = "".join(
            json.dumps(d, ensure_ascii=False, sort_keys=args.sort_keys,
                       separators=(",", ":")) + "\n"
            for d in docs
        )
    else:
        payload = docs[0] if len(docs) == 1 else docs
        if args.compact:
            text = json.dumps(payload, ensure_ascii=False,
                              sort_keys=args.sort_keys,
                              separators=(",", ":"))
        else:
            text = json.dumps(payload, ensure_ascii=False,
                              sort_keys=args.sort_keys, indent=args.indent)

    if args.output:
        args.output.write_text(text + ("" if text.endswith("\n") else "\n"),
                               encoding="utf-8")
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
