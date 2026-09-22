"""Tests for the data-tools converters.

I call the modules' functions directly instead of shelling out, except for a
couple of end-to-end checks that go through main(). Run with:

    python -m pytest tests/ -q
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import concat_csv  # noqa: E402
import dedup_json  # noqa: E402
import json_to_csv  # noqa: E402
import schema_infer  # noqa: E402
import yaml_to_json  # noqa: E402

SAMPLE = ROOT / "examples" / "sample.json"


# --- json_to_csv ---------------------------------------------------------

def test_flatten_nested_dicts():
    flat = json_to_csv.flatten({"a": {"b": {"c": 1}}, "d": 2})
    assert flat == {"a.b.c": 1, "d": 2}


def test_flatten_keeps_lists_as_json_strings():
    flat = json_to_csv.flatten({"tags": ["x", "y"]})
    assert json.loads(flat["tags"]) == ["x", "y"]


def test_json_to_csv_end_to_end(tmp_path):
    out = tmp_path / "sample.csv"
    assert json_to_csv.main([str(SAMPLE), "-o", str(out)]) == 0
    with out.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 4
    # Nested key got flattened.
    assert "plan.tier" in rows[0]
    assert rows[0]["plan.tier"] == "pro"
    # The list column survived as JSON.
    assert json.loads(rows[0]["tags"]) == ["analytics", "beta"]


def test_jsonl_input_is_detected(tmp_path):
    src = tmp_path / "in.jsonl"
    src.write_text('{"a": 1}\n{"a": 2}\n\n{"a": 3}\n', encoding="utf-8")
    out = tmp_path / "out.csv"
    assert json_to_csv.main([str(src), "-o", str(out)]) == 0
    with out.open(encoding="utf-8-sig", newline="") as fh:
        assert len(list(csv.DictReader(fh))) == 3


def test_missing_file_returns_2(tmp_path):
    assert json_to_csv.main([str(tmp_path / "nope.json")]) == 2


# --- yaml_to_json --------------------------------------------------------

def test_yaml_single_document(tmp_path):
    if yaml_to_json.yaml is None:
        pytest.skip("pyyaml not installed")
    src = tmp_path / "a.yml"
    src.write_text("name: demo\nreplicas: 3\n", encoding="utf-8")
    out = tmp_path / "a.json"
    assert yaml_to_json.main([str(src), "-o", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {"name": "demo", "replicas": 3}


def test_yaml_multi_document_becomes_array(tmp_path):
    if yaml_to_json.yaml is None:
        pytest.skip("pyyaml not installed")
    src = tmp_path / "multi.yml"
    src.write_text("---\na: 1\n---\nb: 2\n", encoding="utf-8")
    out = tmp_path / "multi.json"
    assert yaml_to_json.main([str(src), "-o", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == [{"a": 1}, {"b": 2}]


def test_yaml_invalid_returns_1(tmp_path):
    if yaml_to_json.yaml is None:
        pytest.skip("pyyaml not installed")
    src = tmp_path / "bad.yml"
    # Unbalanced bracket.
    src.write_text("a: [1, 2\n", encoding="utf-8")
    assert yaml_to_json.main([str(src)]) == 1


# --- dedup_json ----------------------------------------------------------

def test_dedupe_full_record():
    rows = [{"id": 1}, {"id": 2}, {"id": 1}]
    kept, removed = dedup_json.dedupe(rows, None, "first")
    assert kept == [{"id": 1}, {"id": 2}]
    assert removed == 1


def test_dedupe_on_key_keeps_last():
    rows = [{"id": 1, "v": "old"}, {"id": 1, "v": "new"}, {"id": 2, "v": "x"}]
    kept, removed = dedup_json.dedupe(rows, ["id"], "last")
    assert [r["v"] for r in kept] == ["new", "x"]
    assert removed == 1


def test_normalise_strips_strings():
    a = {"name": " Ada "}
    b = {"name": "Ada"}
    assert dedup_json.key_for(a, None) == dedup_json.key_for(b, None)


# --- concat_csv ----------------------------------------------------------

def test_concat_union_of_columns(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("id,name\n1,ada\n", encoding="utf-8")
    b.write_text("id,email\n2,grace@example.org\n", encoding="utf-8")
    out = tmp_path / "all.csv"
    assert concat_csv.main([str(a), str(b), "-o", str(out)]) == 0
    with out.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    assert set(rows[0]) == {"id", "name", "email"}


def test_concat_intersect_drops_extra_columns(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("id,name\n1,ada\n", encoding="utf-8")
    b.write_text("id,name,extra\n2,grace,zzz\n", encoding="utf-8")
    out = tmp_path / "all.csv"
    assert concat_csv.main([str(a), str(b), "-o", str(out), "--intersect"]) == 0
    with out.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        assert next(reader) == ["id", "name"]


def test_concat_add_source_and_dedupe(tmp_path):
    a = tmp_path / "a.csv"
    a.write_text("id\n1\n1\n", encoding="utf-8")
    out = tmp_path / "all.csv"
    assert concat_csv.main([str(a), "-o", str(out), "--add-source", "--dedupe"]) == 0
    with out.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["_source"] == "a.csv"


# --- schema_infer --------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (1, "integer"),
    ("42", "integer"),
    ("3.14", "number"),
    ("1e6", "number"),
    ("true", "boolean"),
    ("2024-01-01", "date"),
    ("2024-01-01T10:00", "datetime"),
    ("", "empty"),
    ("null", "empty"),
    ("007", "string"),  # leading zeros stay strings on purpose
    ("hello", "string"),
])
def test_classify(value, expected):
    assert schema_infer.classify(value) == expected


def test_merge_integer_and_number_is_number():
    from collections import Counter
    assert schema_infer.merge(Counter({"integer": 3, "number": 1})) == "number"


def test_infer_on_sample():
    rows = json.loads(SAMPLE.read_text(encoding="utf-8"))
    report = {r["column"]: r for r in schema_infer.infer(rows, 1000)}
    assert report["id"]["type"] == "integer"
    assert report["active"]["type"] == "boolean"
    assert report["signup_date"]["type"] == "date"
    assert report["monthly_spend"]["type"] == "number"


# --- csv_to_parquet (optional) -------------------------------------------

def test_csv_to_parquet_if_pyarrow(tmp_path):
    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    import csv_to_parquet

    src = tmp_path / "t.csv"
    src.write_text("a,b\n1,x\n2,y\n", encoding="utf-8")
    out = tmp_path / "t.parquet"
    assert csv_to_parquet.main([str(src), "-o", str(out)]) == 0
    assert out.exists()

    import pandas as pd
    df = pd.read_parquet(out)
    assert list(df.columns) == ["a", "b"]
    assert len(df) == 2
