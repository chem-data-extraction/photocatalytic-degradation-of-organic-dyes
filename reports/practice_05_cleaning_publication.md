# Practice 5 — Cleaning, normalization and publication

> Follow `specs/cleaning_pipeline.json`. Run `scripts/clean_dataset.py` and `scripts/validate_project.py`.

## Input files

- `data/extracted/pdf_extracted_records.csv`
- `data/extracted/web_extracted_records.csv`
- `data/extracted/downoaded_records.csv`
- (optional) `data/interim/merged_records.csv`

## Cleaning steps

Walk through each step in `specs/cleaning_pipeline.json`: merge, units, sequences, missing values, deduplication, validation, export.

## Normalization rules

Document unit → nM conversion, sequence uppercase rules, and missing-value tokens.

## Deduplication strategy

Keys used to define duplicates (e.g. `record_id`, or sequence + target + value + source_id).

## Validation results

List errors and warnings.

## Final dataset description

Row count, targets covered, date built, path: `data/processed/dataset.csv`.

## Publication readiness checklist

- [ ] `dataset.csv` matches `specs/dataset_schema.json`
- [ ] All `source_id` values documented in source map
- [ ] LICENSE replaced (not placeholder)
- [ ] `CITATION.cff` completed
- [ ] `dataset_card.md` updated
- [ ] `reports/final_report.md` complete
