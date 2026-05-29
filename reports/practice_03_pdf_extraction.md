# Practice 3 — PDF extraction

> Align with `specs/pdf_extraction_manifest.json` and `data/extracted/pdf_extracted_records.csv`.

## Selected PDF sources

| source_id | pdf_id | Year (approx.) | Path |
|-----------|--------|----------------|------|
| paper_green_2018 | green_2018_thrombin_aptamer | 2018 | data/raw/pdf/ |
| paper_lee_2020 | lee_2020_multiplex_panel | 2020 | data/raw/pdf/ |
| paper_kim_2015 | kim_2015_lysozyme_aptamer | 2015 | data/raw/pdf/ |

## Why these PDFs were selected

Explain relevance, open access, table quality, and overlap with your research question.

## Pages used

List page numbers per PDF and what appears on each (tables, figures, methods).

## Extraction methods

Tools considered: PyMuPDF, pdfplumber, Camelot, Tabula, manual entry. What you actually used and why.

## Extracted fields

Map PDF content to schema fields. Note manual corrections.

## Extraction problems

Scanned PDFs, merged cells, units in captions, ambiguous sequences, etc.

## Output files

- `data/extracted/pdf_extracted_records.csv`
- `data/extracted/extraction_log.jsonl` (PDF-related lines)
- Raw PDFs under `data/raw/pdf/`
