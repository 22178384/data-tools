"""JSON 转 CSV（由 data-tools 补充）。"""

import csv
import json
import sys


def json_to_csv(src: str, dst: str) -> None:
    with open(src, encoding="utf-8") as f:
        rows = json.load(f)
    if not rows:
        print("空数据"); return
    keys = list(rows[0].keys())
    with open(dst, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"已写入 {dst}，共 {len(rows)} 行")


if __name__ == "__main__":
    if len(sys.argv) > 2:
        json_to_csv(sys.argv[1], sys.argv[2])
