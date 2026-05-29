# Practice 5 — Cleaning, normalization and publication

> Follow `specs/cleaning_pipeline.json`. Run `scripts/clean_dataset.py` and `scripts/validate_project.py`.

## Input files

- `data/extracted/pdf_extracted_records.csv` (contains 6 data rows extracted from scientific publications)
- `data/extracted/web_extracted_records.csv` (contains 30 data rows extracted from the Zenodo dataset)
- `data/interim/merged_records.csv` (interim merged table containing 36 data rows)

## Cleaning steps

Walk through each step in `specs/cleaning_pipeline.json`:

1. **Merge Sources (`merge_sources`)**: 
   Concatenates raw extracted rows from the scientific papers CSV (`pdf_extracted_records.csv`) and the Zenodo dataset CSV (`web_extracted_records.csv`) into a single table at `data/interim/merged_records.csv`.
2. **Normalize Units (`normalize_units`)**:
   Converts units of dye concentration (`initial_dye_concentration_unit`), catalyst dosage (`catalyst_dosage_unit`), and irradiation time (`irradiation_time_unit`) into standard values defined in `specs/units.json`.
3. **Enrich Dye Info via PubChem (`enrich_dye_pubchem`)**:
   Dye names are resolved using the vocabulary mapping in `specs/vocabularies.json` (e.g., mapping `"RhB"` to `"rhodamine b"`). The script queries the PubChem REST API using a cached lookup (`data/interim/pubchem_cache.json`) to retrieve the official preferred name, PubChem Compound ID (CID), and molecular formula, writing these to the columns `dye_name`, `dye_pubchem_cid`, and `dye_molecular_formula`.
4. **Standardize Missing Values (`standardize_missing_values`)**:
   Missing or empty values (such as `NaN`, `N/A`, `None`) are mapped to actual null values for fields like `catalyst_band_gap_ev`, `catalyst_surface_area_m2g`, and `catalyst_particle_size_nm`. For Zenodo records, the script also aligns the `light_type` based on descriptions from `data/raw/external/zenodo_16640173/LC1_φ_NMs_data.xlsx` (mapping `'UV_LIGHT'` -> `'UV'`, `'Visible_LIGHT'` -> `'Visible'`) with a default fallback of `'UV'`.
5. **Schema Validation (`validate_schema`)**:
   Dynamically compiles a JSON schema from the fields and types specified in `specs/dataset_schema.json`. Validates every row of the dataset using `jsonschema`.
6. **PubChem filtering & Column Reordering**:
   Drops any rows that could not be resolved on PubChem (where `dye_pubchem_cid` is null). Reorders columns to match the schema field order.
7. **Deduplication**:
   Removes duplicate rows based on the `record_id` column, keeping only the first occurrence.
8. **Export Final Dataset (`export_final_dataset`)**:
   Writes the validated, cleaned, and normalized records to `data/processed/dataset.csv`.

## Normalization rules

- **Unit Conversion**:
  - Concentration: `mgl-1`, `ppm`, `mg/l`, `mgl^-1`, `mg L^-1`, and `mg L-1` are converted to `mg/L`.
  - Dosage: `gl-1`, `g/l`, and `gl^-1` are converted to `g/L`.
  - Time: Replaces empty or non-standard time units, defaulting/standardizing to `min`.
- **Text & Sequence Standardization**:
  - Dye names are normalized to match PubChem's preferred terms:
    - `"methylene blue"` / `"Methylene blue"` -> `"Methylene Blue"`
    - `"rhodamine b"` / `"rhodamine B"` / `"RhB"` -> `"Rhodamine B"`
    - `"methyl orange"` / `"Methyl Orange"` -> `"C.I. Acid Orange 52"`
  - Light types are mapped to standard category names: `"Visible_LIGHT"` -> `"Visible"`, `"UV_LIGHT"` -> `"UV"`.
- **Missing-Value Tokens**:
  - Empty fields, `NaN`, `N/A`, and `None` strings are normalized to actual empty cells (`null`/`None` values in python/pandas) in the output CSV.

## Deduplication strategy

- The cleaning pipeline deduplicates records using `record_id` as the unique key (`cleaned_df.drop_duplicates(subset=["record_id"], keep="first")`).
- All 36 rows generated in this run had unique `record_id` values, so no records were dropped during deduplication.

## Validation results

- **Scripts Execution (`scripts/validate_project.py`)**:
  - **Status**: Validation passed.
  - **Errors**: 0
  - **Warnings**: 0
- **Unit Tests Execution (`pytest`)**:
  - **Status**: 9 passed (100% success rate).
  - Verified:
    - Existence of all required files (rules in `specs/validation_rules.json`).
    - Parseability of all JSON and CSV configuration and data files.
    - Column match between `data/processed/dataset.csv` and `specs/dataset_schema.json`.
    - Uniqueness of `record_id`.
    - Completeness and validity of `source_id` referencing entries in the source map.

## Final dataset description

- **Row Count**: 36 rows
- **Date Built**: 2026-05-29
- **Output Path**: `data/processed/dataset.csv`
- **Dyes/Pollutants Covered (3 unique)**:
  - `Methylene Blue` (CID: 6099)
  - `C.I. Acid Orange 52` (Methyl Orange) (CID: 23673835)
  - `Rhodamine B` (CID: 6694)
- **Catalysts Covered (8 unique)**:
  - `MicNo-ZnO`
  - `Mg-doped Ag2O`
  - `Mg-Al LDH@g-C3N430@Ag3PO45`
  - `5% BiVO4/UU-200`
  - `Co3O4-Bi2O3`
  - `5% ZnO/WO3`
  - `TiO2_SiO2`
  - `TiO2_N_col`
- **Sources Tracked (7 unique)**:
  - 6 journal article publications (extracted via PDF pipeline)
  - 1 database source (zenodo_16640173, extracted via Web/API pipeline)

## Publication readiness checklist

- [x] `dataset.csv` matches `specs/dataset_schema.json`
- [x] All `source_id` values documented in source map
- [x] LICENSE replaced (standard license template populated)
- [x] `CITATION.cff` completed
- [x] `dataset_card.md` updated
- [x] `reports/final_report.md` complete (reserved for the final overall summary submission)