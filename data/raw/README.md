# Raw data

Store **unaltered** source files here. Do not edit files in this folder after download; add new versions with clear names instead.

## What belongs here

| Subfolder | Contents |
|-----------|----------|
| `pdf/` | Original PDF papers and supplementary files referenced in `specs/pdf_extraction_manifest.json` |
| `web/` | HTML snapshots, saved pages, or API JSON responses referenced in `specs/web_extraction_manifest.json` |
| `external/` | Third-party CSV, ZIP, or database exports (with license notes in `specs/source_map.json`) |

## What does not belong here

- Cleaned or merged tables (use `data/interim/` or `data/processed/`)
- Extracted record CSVs (use `data/extracted/`)

Document each file’s `source_id`, download date, and license in your source map and practice reports.
