#!/usr/bin/env python3
"""XML 转 JSON（由 @c991china 贡献）。用法：python xml_to_json.py in.xml > out.json"""
import json
import sys
import xml.etree.ElementTree as ET


def elem_to_dict(el):
    d = {}
    for child in el:
        d[child.tag] = elem_to_dict(child) if len(list(child)) else (child.text or "")
    return d


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data.xml"
    tree = ET.parse(path)
    result = {tree.getroot().tag: elem_to_dict(tree.getroot())}
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
