#!/usr/bin/env python3
"""Stage 2: Parse PDFs to extract text, tables, and render figures."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import helpers

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", default=str(helpers.DEFAULT_SOURCES_CSV))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()

def assert_inputs_ready_for_extraction() -> None:
    missing = [
        path for path in [
            helpers.PRACTICE1_SCHEMA_MD,
            helpers.PRACTICE2_SOURCE_MAP_MD,
            helpers.PRACTICE3_SOURCE_MANIFEST_CSV,
            helpers.MANUAL_DOWNLOAD_QUEUE_CSV,
            helpers.INPUT_INVENTORY_REPORT_MD,
        ] if not path.exists()
    ]
    if missing:
        missing_text = ", ".join(str(path.relative_to(helpers.PROJECT_ROOT)) for path in missing)
        raise SystemExit(
            "Input inventory is not prepared. Run `python scripts/01_acquire_and_validate.py` first. "
            f"Missing: {missing_text}"
        )
    manifest = helpers.read_csv_or_empty(helpers.PRACTICE3_SOURCE_MANIFEST_CSV, helpers.MANIFEST_COLUMNS)
    usable_sources = [sid for sid in manifest["source_id"] if helpers.has_usable_input(sid)]
    if not usable_sources:
        raise SystemExit(
            "No local article PDF or HTML inputs are available for extraction. "
            "Place files at the expected paths and run `python scripts/01_acquire_and_validate.py` again."
        )

def resolve_pdf(path_value: str) -> Path | None:
    if not str(path_value).strip():
        return None
    path = Path(str(path_value).strip())
    if not path.is_absolute():
        path = helpers.PROJECT_ROOT / path
    return path

def main() -> int:
    args = parse_args()
    helpers.setup_logging(args.verbose)
    helpers.ensure_directories()
    assert_inputs_ready_for_extraction()

    sources_path = Path(args.sources)
    if not sources_path.is_absolute():
        sources_path = helpers.PROJECT_ROOT / sources_path

    sources = helpers.read_csv_or_empty(sources_path, helpers.SOURCE_COLUMNS)
    ambiguous: list[dict[str, str]] = []
    all_table_rows: list[dict[str, Any]] = []
    all_figure_rows: list[dict[str, Any]] = []
    
    processed_count = 0

    for _, row in sources.iterrows():
        source_id = row["source_id"]
        pdf_path = resolve_pdf(row.get("local_pdf_path", ""))
        
        if pdf_path is None or not pdf_path.exists():
            ambiguous.append(
                helpers.ambiguous_case(
                    f"{source_id}-text-missing-pdf",
                    source_id,
                    pdf_path or "",
                    "missing_local_pdf",
                    "Extraction skipped because local PDF was not found.",
                    affected_fields="local_pdf_path"
                )
            )
            continue
            
        print(f"Parsing {source_id}...")
        
        # 1. Extract Text
        try:
            pages = helpers.extract_pages(pdf_path, source_id)
            helpers.write_text(helpers.pages_to_markdown(source_id, pages), helpers.EXTRACTED_TEXT_DIR / f"{source_id}.md", overwrite=args.overwrite)
            helpers.write_json(pages, helpers.INTERMEDIATE_JSON_DIR / f"{source_id}_pages.json", overwrite=args.overwrite)
            processed_count += 1
        except Exception as exc:
            ambiguous.append(
                helpers.ambiguous_case(
                    f"{source_id}-text-error",
                    source_id,
                    pdf_path,
                    "pdf_text_extraction_error",
                    str(exc),
                    affected_fields="extracted_text"
                )
            )

        # 2. Extract Tables
        try:
            table_rows = helpers.extract_pdfplumber_tables(pdf_path, source_id, helpers.EXTRACTED_TABLES_DIR)
            all_table_rows.extend(table_rows)
        except Exception as exc:
            ambiguous.append(
                helpers.ambiguous_case(
                    f"{source_id}-tables-error",
                    source_id,
                    pdf_path,
                    "pdf_table_extraction_error",
                    str(exc),
                    affected_fields="extracted_tables"
                )
            )

        # 3. Extract Figures
        try:
            figure_rows = helpers.extract_page_figures(pdf_path, source_id, helpers.EXTRACTED_FIGURES_DIR)
            all_figure_rows.extend(figure_rows)
        except Exception as exc:
            ambiguous.append(
                helpers.ambiguous_case(
                    f"{source_id}-figures-error",
                    source_id,
                    pdf_path,
                    "pdf_figure_extraction_error",
                    str(exc),
                    affected_fields="extracted_figures"
                )
            )

    # Write indices
    helpers.write_csv(pd.DataFrame(all_table_rows, columns=helpers.TABLE_INDEX_COLUMNS), helpers.TABLES_INDEX_CSV)
    helpers.write_csv(pd.DataFrame(all_figure_rows, columns=helpers.FIGURE_INDEX_COLUMNS), helpers.FIGURES_INDEX_CSV)

    if ambiguous:
        existing = helpers.read_csv_or_empty(helpers.AMBIGUOUS_CASES_CSV, helpers.AMBIGUOUS_COLUMNS)
        pd.concat([existing, pd.DataFrame(ambiguous)], ignore_index=True).drop_duplicates().to_csv(helpers.AMBIGUOUS_CASES_CSV, index=False)

    print(f"Content extraction complete. Processed {processed_count} PDFs.")
    print(f"Tables index rows: {len(all_table_rows)}, Figures index rows: {len(all_figure_rows)}")
    print(f"Ambiguous cases registered: {len(ambiguous)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
