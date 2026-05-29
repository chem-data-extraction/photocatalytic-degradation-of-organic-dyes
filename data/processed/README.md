# Processed data

This folder holds the **publication-ready** dataset: one row per record, columns aligned with `specs/dataset_schema.json`.

## Main file

- `dataset.csv` — final dataset produced by `scripts/build_dataset.py` and `scripts/clean_dataset.py`, validated with `scripts/validate_project.py`

## Guidelines

- Regenerate this file from scripts; avoid hand-editing except for small template fixes during setup.
- Before submission, replace example rows with your project records.
- Record the dataset version or commit hash in `reports/final_report.md` and `dataset_card.md`.
