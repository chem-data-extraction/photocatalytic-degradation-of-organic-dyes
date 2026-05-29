# Practice 4 — Web extraction

> Align with `specs/web_extraction_manifest.json` and `data/extracted/web_extracted_records.csv`.

## Selected web sites

| source_id | page_id | URL |
|-----------|---------|-----|
| zenodo_16640173 | zenodo_16640173_dye_degradation | https://zenodo.org/records/16640173 |

## Why these sites were selected

- **High Data Density & Structure:** The selected site (Zenodo) hosts open-access databases. Record `16640173` contains a clean, pre-packaged spreadsheet containing experimental results on photocatalytic dye degradation of Rhodamine B using various nanoparticles under different conditions. This provides a much higher volume of structured data points (30 records in our sub-dataset) than manual PDF parsing.
- **Open Access License:** Zenodo records are published with clear licensing metadata. The chosen record is licensed under CC-BY 4.0, which allows for legal extraction, transformation, and distribution of the data.
- **Complementarity to PDFs:** Literature PDFs frequently omit negative results, control runs, or step-by-step kinetic parameters. Zenodo repositories often contain full raw experimental sheets, which capture complete experimental steps and timelines, offering a highly valuable complement to the summaries in scientific papers.
- **Programmatic Accessibility:** Zenodo provides a public, robust REST API that allows searching, inspecting metadata (including related publications or datasets), and downloading files programmatically.

## Page structure

- **API and Metadata Structure:** Programmatic access is performed via Zenodo's records endpoint (`https://zenodo.org/api/records/{record_id}`). The API response is a rich JSON object listing metadata (title, description, creators, license, keywords) and `files` metadata (filenames, sizes, direct download links).
- **Relational Structure (`related_identifiers`):** The record page contains relationships linking the raw data sheet with its corresponding experimental protocol or metadata sheet. Specifically, the JSON response includes a `related_identifiers` section that links to a separate metadata record containing the protocol definition.
- **File Structure:** 
  - **Data File (`LC1_φ_NMs_data.xlsx`):** An Excel workbook. The sheet of interest is `9. Descriptors`, which contains a flat table structure with columns mapping to experimental descriptors and the target variable (`Eff_%`).
  - **Metadata File (`LC1_φ_NMs_metadata.xlsx`):** Contains supplementary context such as descriptions of the catalysts, exposure configurations, and standard experimental protocol values (e.g., initial concentrations and dosages) which are constant across the runs.

## Extraction methods

- **Pipeline script:** [extract_web.py](../scripts/extract_web.py).
- **Core Libraries:**
  - `requests`: Used to query the Zenodo API and download the raw files and related metadata context files.
  - `pandas` with `openpyxl`: Used to parse the Excel files (`.xlsx`) and CSV files.
  - `google-genai` client: Integrates Gemini models for filtering and automated mapping.
- **Orchestrated Extraction Pipeline:**
  1. **API Metadata Querying:** The script queries the Zenodo API with the query `"photocatalytic degradation dye dataset"` to retrieve relevant open-access database records.
  2. **LLM-Based Relevance Filter:** Metadata fields (title, description, filenames) are evaluated by `gemini-2.5-flash` using a strict schema to filter out records that contain only raw physical characterizations (like XRD/BET) instead of degradation kinetics.
  3. **Relational Protocol Extraction:** Using Zenodo's `related_identifiers`, the script checks for related metadata files, downloads them, and parses them to extract the context (e.g. description files, readme text, configuration tables).
  4. **LLM-Based Mapping generation:** The dataset file's structure preview (first 6 rows of each sheet) is sent to `gemini-3.1-flash-lite` along with the protocol/metadata text. The LLM acts as a strict mapper and generates a JSON schema map. If a target field is not a column but is defined as a constant in the protocol, the LLM maps it to that constant value (e.g. `"7.0"` for dye concentration, `"0.1"` for catalyst dosage).
  5. **Data Consolidation:** The mapping is applied to the data table, generating records with standardized keys and data types, which are saved to `data/extracted/web_extracted_records.csv`.
- **Rate Limits & API Guidelines:** The extraction script implements retry loops with exponential backoff (`MAX_RETRIES = 5`, `RETRY_DELAY = 5`) to respect Zenodo API limits and LLM request quotas. Zenodo allows public access to its metadata and downloads without strict login requirements, making the scraping fully compliant.

## Extracted fields

The fields from `LC1_φ_NMs_data.xlsx` sheet `9. Descriptors` map to `dataset_schema.json` via the generated mapping schema [LC1_φ_NMs_data.xlsx_mapping.json](../data/raw/external/zenodo_16640173/LC1_%CF%86_NMs_data.xlsx_mapping.json):
- `record_id`: Systematic UUID mapping `rec_photo_web_zenodo_16640173_{index:05d}`.
- `source_id`: Set to folder/record name: `zenodo_16640173`.
- `catalyst`: Mapped from Excel column `NMs_ID` (values include `TiO2_SiO2`, `TiO2_N_col`).
- `dye_name`: Mapped from Excel column `Reactive  Molecule ` (value is `RhB`).
- `initial_dye_concentration_value`: Constant `"7.0"` mapped from the protocol metadata.
- `initial_dye_concentration_unit`: Constant `"mg/L"` mapped from the protocol metadata.
- `catalyst_dosage_value`: Constant `"0.1"` mapped from the protocol metadata.
- `catalyst_dosage_unit`: Constant `"g/L"` mapped from the protocol metadata.
- `light_type`: Mapped from Excel column ` Light Condition` (values like `UV_LIGHT`, `Visible_LIGHT`).
- `irradiation_time_value`: Mapped from Excel column `Exposure duration_min`.
- `irradiation_time_unit`: Constant `"min"`.
- `degradation_efficiency_percent`: Mapped from Excel column `Eff_%`.
- `catalyst_band_gap_ev`, `catalyst_surface_area_m2g`, `catalyst_particle_size_nm`: Set to `None` in raw extraction; to be populated in the cleaning/normalization phase.

## Extraction problems

- **Implicit Protocol Constraints:** The main dataset table did not have columns for dye concentration and catalyst dosage because they were fixed parameters. Standard tabular scraping would miss these values, producing incomplete records. We resolved this by extracting related metadata objects via `related_identifiers` and supplying them as context to the LLM mapper.
- **Inconsistent/Messy Column Names:** Excel column headers contained double spaces and trailing whitespaces (`'Reactive  Molecule '`, `' Light Condition'`). Case-sensitive or exact-string mappings would fail. The LLM mapper successfully resolved this by locating the semantic equivalent column names.
- **Context Size Constraints for Large Tables:** Reading entire Excel spreadsheets with hundreds of rows exceeds API payload limits and is cost-prohibitive. We bypassed this by extracting a limited row-level preview (top 6 rows) of each sheet to determine column layout and mapping schemas.

## Output files

- `data/extracted/web_extracted_records.csv` — consolidated table containing 30 records.
- `data/extracted/extraction_log.jsonl` — audit logs containing web extraction events.
- Raw files under `data/raw/external/zenodo_16640173/`:
  - `LC1_φ_NMs_data.xlsx` (raw data spreadsheet)
  - `LC1_φ_NMs_metadata.xlsx` (raw protocol/metadata context sheet)
  - `LC1_φ_NMs_data.xlsx_mapping.json` (LLM-generated column mapping mapping file)
