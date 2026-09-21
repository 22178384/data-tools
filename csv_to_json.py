#!/usr/bin/env python3
"""CSV 转 JSON。用法：python csv_to_json.py input.csv > output.json"""
import csv
import json
import sys


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data.csv"
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
