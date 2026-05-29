"""Tests for required template artifacts and core validation checks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_project import (  # noqa: E402
    REQUIRED_FILES,
    check_dataset_columns,
    check_record_id,
    check_required_files,
    load_dataset,
    load_json,
    schema_field_names,
    source_ids_from_map,
    validate,
)


@pytest.fixture
def root() -> Path:
    return ROOT


def test_required_files_exist(root: Path) -> None:
    issues = check_required_files(root)
    assert issues == [], "\n".join(issues)


def test_json_files_parse(root: Path) -> None:
    for path in [
        root / "project.json",
        root / "specs/dataset_schema.json",
        root / "specs/source_map.json",
    ]:
        load_json(path)


def test_csv_files_parse(root: Path) -> None:
    pd.read_csv(root / "data/extracted/pdf_extracted_records.csv")
    pd.read_csv(root / "data/extracted/web_extracted_records.csv")
    pd.read_csv(root / "data/processed/dataset.csv")


def test_dataset_columns_match_schema(root: Path) -> None:
    schema = load_json(root / "specs/dataset_schema.json")
    df = load_dataset(root)
    issues = check_dataset_columns(df, schema)
    assert issues == [], "\n".join(issues)
    assert list(df.columns) == schema_field_names(schema)


def test_record_id_unique(root: Path) -> None:
    df = load_dataset(root)
    issues = check_record_id(df)
    assert issues == [], "\n".join(issues)


def test_source_id_present(root: Path) -> None:
    df = load_dataset(root)
    assert not df["source_id"].isna().any()
    assert (df["source_id"].astype(str).str.strip() != "").all()


def test_source_ids_in_source_map(root: Path) -> None:
    source_map = load_json(root / "specs/source_map.json")
    df = load_dataset(root)
    valid = source_ids_from_map(source_map)
    assert set(df["source_id"].astype(str)).issubset(valid)


def test_validate_project_passes(root: Path) -> None:
    errors, _warnings = validate(root)
    assert errors == [], "\n".join(errors)


def test_extraction_log_jsonl(root: Path) -> None:
    log_path = root / "data/extracted/extraction_log.jsonl"
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1
    for line in lines:
        json.loads(line)
