#!/usr/bin/env python3
"""Stage 4: Compile all indices and candidates into a single Excel Workbook for manual review."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import helpers

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(helpers.PROJECT_ROOT / "practice3_manual_review.xlsx"))
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()

def schema_reference() -> pd.DataFrame:
    rows = [{"field": column, "controlled_values": ""} for column in helpers.EXPERIMENT_COLUMNS]
    for field, values in helpers.CONTROLLED_VOCABS.items():
        rows.append({"field": f"vocab:{field}", "controlled_values": "; ".join(sorted(values))})
    return pd.DataFrame(rows)

def main() -> int:
    args = parse_args()
    helpers.setup_logging(args.verbose)
    
    output = Path(args.out)
    if not output.is_absolute():
        output = helpers.PROJECT_ROOT / output
        
    sheets = {
        "candidate_records": helpers.read_csv_or_empty(helpers.EXPERIMENT_RECORDS_CSV, helpers.EXPERIMENT_COLUMNS),
        "relevant_tables": helpers.read_csv_or_empty(helpers.TABLES_INDEX_CSV, helpers.TABLE_INDEX_COLUMNS),
        "relevant_figures": helpers.read_csv_or_empty(helpers.FIGURES_INDEX_CSV, helpers.FIGURE_INDEX_COLUMNS),
        "ambiguous_cases": helpers.read_csv_or_empty(helpers.AMBIGUOUS_CASES_CSV, helpers.AMBIGUOUS_COLUMNS),
        "excluded_candidates": helpers.read_csv_or_empty(helpers.EXCLUDED_RECORDS_CSV, helpers.EXCLUDED_COLUMNS),
        "schema_reference": schema_reference(),
    }
    
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
            
    print(f"Manual review workbook successfully written to: {output}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
