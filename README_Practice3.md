# Practice 3 PDF Extraction

Runnable Python pipeline for Practice 3 of the Extraction and preparation of chemical information course.

## Scope
One record is one independent photocatalytic degradation experiment for one organic dye under one fixed set of conditions. PDF/article/supplement extraction is the primary evidence source.

## Current Status
- selected_sources: 11
- successful_downloads_or_html_saves: 0
- manual_download_queue_rows: 10
- extracted_text_files: 3
- extracted_tables: 6
- figure_inventory_rows: 49
- candidate_snippets: 161
- experiment_record_rows: 142
- ambiguous_cases: 8
- excluded_records: 19

## Run

```bash
pip install -r requirements.txt
python scripts/01_acquire_and_validate.py
python scripts/02_extract_content.py
python scripts/03_mine_candidates.py
python scripts/04_build_workbook.py
# Use practice3_manual_review.xlsx to manually review, edit, and save
python scripts/05_validate_and_report.py
```

## Manual Review
Use `practice3_manual_review.xlsx` to convert candidate snippets into final experiment-level records. Keep time-series points in `extracted_time_series_optional.csv`, not as separate main records.
