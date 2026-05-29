#!/usr/bin/env python3
"""
Assembly script.
Combines data/extracted/pdf_extracted_records.csv and data/extracted/web_extracted_records.csv
into data/interim/merged_records.csv.
"""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

PDF_CSV = ROOT / "data/extracted/pdf_extracted_records.csv"
WEB_CSV = ROOT / "data/extracted/web_extracted_records.csv"
SCHEMA_PATH = ROOT / "specs/dataset_schema.json"
MERGED_PATH = ROOT / "data/interim/merged_records.csv"
DATASET_PATH = ROOT / "data/processed/dataset.csv"

def load_schema_columns() -> list[str]:
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        schema = json.load(f)
    return [field["name"] for field in schema["fields"]]

def build() -> pd.DataFrame:
    dfs = []
    if PDF_CSV.is_file():
        dfs.append(pd.read_csv(PDF_CSV))
    else:
        print(f"Warning: PDF records file not found at {PDF_CSV}")
        
    if WEB_CSV.is_file():
        dfs.append(pd.read_csv(WEB_CSV))
    else:
        print(f"Warning: Web records file not found at {WEB_CSV}")
        
    if not dfs:
        raise FileNotFoundError("Neither PDF nor Web extracted CSV files exist.")
        
    # Concatenate dataframes
    merged_df = pd.concat(dfs, ignore_index=True)
    columns = load_schema_columns()
    
    # Ensure all columns exist and are in the correct order
    for col in columns:
        if col not in merged_df.columns:
            merged_df[col] = None
            
    return merged_df[columns]

def main() -> None:
    MERGED_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)

    df = build()
    df.to_csv(MERGED_PATH, index=False)
    # Save a temporary copy to dataset.csv as required by intermediate verification tests
    df.to_csv(DATASET_PATH, index=False)

    print(f"Wrote {len(df)} rows to {MERGED_PATH.relative_to(ROOT)}")
    print(f"Wrote {len(df)} rows to {DATASET_PATH.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
