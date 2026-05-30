# Photocatalytic dye degradation dataset
Publication-ready **dataset project** focused on the extraction, cleanup, and curation of chemical degradation information.

**Project topic:** Photocatalytic degradation of organic dyes (defined in `project.json`).

## Scientific task

Collect experimentally reported photocatalytic degradation measurements of organic dyes (catalyst formula, band gap, surface area, particle size, dye details, degradation efficiency, and experimental conditions) so they can be compared across literature and database sources.

## What is one record?

One **record** = one experimentally reported photocatalytic degradation efficiency measurement at a specific point in time within one experiment from a specific source (one row in `data/processed/dataset.csv`). See `project.json` and `reports/practice_01_record_and_schema.md`.

## Repository structure

| Path | Role |
|------|------|
| `project.json` | Machine-readable project metadata |
| `specs/` | JSON schemas, source map, manifests, pipeline, validation rules |
| `data/raw/` | Unmodified PDFs, web snapshots, external exports |
| `data/extracted/` | Extraction outputs (CSV + `extraction_log.jsonl`) |
| `data/interim/` | Merged table before final cleaning |
| `data/processed/` | Publication dataset (`dataset.csv`) |
| `scripts/` | Reproducible extract, build, clean, validate |
| `reports/` | Technical and final reports |
| `notebooks/` | Optional exploration only |
| `tests/` | Pytest checks for required artifacts |

**Formats:** JSON for specs and manifests; CSV for tabular data; Python for pipelines; Markdown for reports and documentation only. Notebooks are optional.

## Data pipeline

```text
raw (PDF / web / external)
  → extract (pdf + web scripts) → data/extracted/*.csv
  → build (merge) → data/interim/merged_records.csv
  → clean → data/processed/dataset.csv
  → validate (rules + pytest)
```

## How to run validation

```bash
pip install -r requirements.txt
python scripts/validate_project.py
pytest
```

## How to build the dataset

```bash
python scripts/build_dataset.py    # merge extracts → interim + processed
python scripts/clean_dataset.py    # normalize and write processed dataset
```

To run the data extraction (requires configuring `.env` with `GEMINI_API_KEY` and `MINERU_TOKEN`):

```bash
python scripts/extract_pdf.py
python scripts/extract_web.py
```