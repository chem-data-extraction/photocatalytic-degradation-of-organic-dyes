#!/usr/bin/env python3
"""Validate repository artifacts against specs/validation_rules.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "project.json",
    "specs/dataset_schema.json",
    "specs/source_map.json",
    "specs/pdf_extraction_manifest.json",
    "specs/web_extraction_manifest.json",
    "specs/cleaning_pipeline.json",
    "specs/validation_rules.json",
    "data/extracted/pdf_extracted_records.csv",
    "data/extracted/web_extracted_records.csv",
    "data/processed/dataset.csv",
    "scripts/build_dataset.py",
    "scripts/clean_dataset.py",
]

CONFIDENCE_ALLOWED = {"", "high", "medium", "low", "unknown"}

def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)

def schema_field_names(schema: dict) -> list[str]:
    return [field["name"] for field in schema["fields"]]

def source_ids_from_map(source_map: dict) -> set[str]:
    ids: set[str] = set()
    for group_sources in source_map.get("source_groups", {}).values():
        for entry in group_sources:
            sid = entry.get("source_id")
            if sid:
                ids.add(sid)
    return ids

def check_required_files(root: Path = ROOT) -> list[str]:
    issues = []
    for rel in REQUIRED_FILES:
        if not (root / rel).is_file():
            issues.append(f"Missing required file: {rel}")
    return issues

def check_json_parseable(root: Path = ROOT) -> list[str]:
    issues = []
    for path in root.rglob("*.json"):
        if ".pytest_cache" in path.parts or "venv" in path.parts:
            continue
        try:
            load_json(path)
        except json.JSONDecodeError as exc:
            issues.append(f"Invalid JSON: {path.relative_to(root)} ({exc})")
    return issues

def load_dataset(root: Path = ROOT) -> pd.DataFrame:
    path = root / "data/processed/dataset.csv"
    return pd.read_csv(path)

def check_dataset_columns(df: pd.DataFrame, schema: dict) -> list[str]:
    expected = schema_field_names(schema)
    actual = list(df.columns)
    issues = []
    if actual != expected:
        issues.append(
            f"Dataset columns do not match schema. Expected {expected}, got {actual}"
        )
    return issues

def check_record_id(df: pd.DataFrame) -> list[str]:
    issues = []
    if df["record_id"].isna().any() or (df["record_id"].astype(str).str.strip() == "").any():
        issues.append("record_id contains null or empty values")
    if df["record_id"].duplicated().any():
        dupes = df.loc[df["record_id"].duplicated(), "record_id"].tolist()
        issues.append(f"Duplicate record_id values: {dupes}")
    return issues

def check_source_id(df: pd.DataFrame, source_map: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    valid_ids = source_ids_from_map(source_map)

    if df["source_id"].isna().any() or (df["source_id"].astype(str).str.strip() == "").any():
        errors.append("source_id contains null or empty values")

    unknown = set(df["source_id"].dropna().astype(str)) - valid_ids
    if unknown:
        warnings.append(f"source_id not in source map (warning): {sorted(unknown)}")
    return errors, warnings

def check_degradation_efficiency_percent(df: pd.DataFrame) -> list[str]:
    issues = []
    # If the column is completely missing or renamed, check_dataset_columns will catch it first.
    # We check if it is numeric where it exists.
    if "degradation_efficiency_percent" in df.columns:
        col = df["degradation_efficiency_percent"]
        for idx, val in col.items():
            if pd.isna(val) or val == "":
                continue
            try:
                float(val)
            except (TypeError, ValueError):
                issues.append(f"degradation_efficiency_percent not numeric at row {idx}: {val!r}")
    return issues

def check_extraction_confidence(df: pd.DataFrame) -> list[str]:
    warnings = []
    if "extraction_confidence" not in df.columns:
        return warnings
    for val in df["extraction_confidence"].fillna("").astype(str):
        if val.lower() not in CONFIDENCE_ALLOWED and val not in CONFIDENCE_ALLOWED:
            warnings.append(f"Unexpected extraction_confidence: {val!r}")
            break
    return warnings

def validate(root: Path = ROOT) -> tuple[list[str], list[str]]:
    """Return (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(check_required_files(root))
    errors.extend(check_json_parseable(root))

    dataset_path = root / "data/processed/dataset.csv"
    if not dataset_path.is_file():
        return errors, warnings

    schema = load_json(root / "specs/dataset_schema.json")
    source_map = load_json(root / "specs/source_map.json")
    df = load_dataset(root)

    errors.extend(check_dataset_columns(df, schema))
    errors.extend(check_record_id(df))
    errors.extend(check_degradation_efficiency_percent(df))

    src_errors, src_warnings = check_source_id(df, source_map)
    errors.extend(src_errors)
    warnings.extend(src_warnings)
    warnings.extend(check_extraction_confidence(df))

    return errors, warnings

def main() -> int:
    errors, warnings = validate()
    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    if errors:
        print(f"\nValidation failed with {len(errors)} error(s).")
        return 1
    print("Validation passed.")
    if warnings:
        print(f"({len(warnings)} warning(s))")
    return 0

if __name__ == "__main__":
    sys.exit(main())
