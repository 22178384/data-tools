#!/usr/bin/env python3
"""JSON 美化或压缩。用法：python json_pretty.py -i ugly.json -o pretty.json"""
import json
import sys


def main():
    in_path = None
    out_path = None
    compact = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "-i":
            in_path = args[i + 1]; i += 2
        elif args[i] == "-o":
            out_path = args[i + 1]; i += 2
        elif args[i] == "--compact":
            compact = True; i += 1
        else:
            i += 1
    data = json.load(sys.stdin if in_path is None else open(in_path, encoding="utf-8"))
    text = json.dumps(data, ensure_ascii=False, indent=None if compact else 2)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
