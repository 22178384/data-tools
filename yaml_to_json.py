"""YAML 转 JSON（由 data-tools 补充，需要 PyYAML）。"""

import json
import os
import sys


def yaml_to_json(src: str, dst: str) -> None:
    import yaml
    with open(src, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已写入 {dst}")


if __name__ == "__main__":
    if len(sys.argv) > 2:
        yaml_to_json(sys.argv[1], sys.argv[2])
