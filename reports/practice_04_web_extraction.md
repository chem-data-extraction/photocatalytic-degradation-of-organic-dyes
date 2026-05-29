# Practice 4 — Web extraction

> Align with `specs/web_extraction_manifest.json` and `data/extracted/web_extracted_records.csv`.

## Selected web sites

| source_id | page_id | URL |
|-----------|---------|-----|
| db_aptagen | aptagen_thrombin_entries | https://example.org/aptagen/target/thrombin |
| db_aptadb | aptadb_entries | https://example.org/aptamer-db |

## Why these sites were selected

Structured data, license, complement to PDFs, update frequency.

## Page structure

Describe HTML layout: tables, pagination, JSON-LD, iframes.

## Extraction methods

Tool (`requests`, `BeautifulSoup`, etc.), selectors from manifest `parser_plan`, rate limits, `robots.txt` notes.

## Extracted fields

Which DOM fields map to schema columns.

## Extraction problems

Dynamic content, login walls, changed markup, inconsistent units.

## Output files

- `data/extracted/web_extracted_records.csv`
- `data/raw/web/*.html` snapshots
- `data/extracted/extraction_log.jsonl` (web-related lines)
