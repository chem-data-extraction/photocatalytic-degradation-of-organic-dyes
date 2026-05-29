# Final report

This report summarizes the completed Photocatalytic Dye Degradation Dataset project, documenting the goals, source map, extraction pipeline, cleaning process, validation status, limitations, and final artifacts.

## Project summary

- **Dataset Title:** Photocatalytic dye degradation dataset
- **Author:** Aleksandr Artamonov
- **Current Version:** 0.1.0
- **Release Date:** 2026-05-29

## Dataset goal

The dataset supports research in environmental engineering and green chemistry by enabling the comparative analysis of organic dye degradation efficiency across different experimental settings. Specifically, it aims to answer:
1. Which semiconductor photocatalysts perform best for specific organic dyes (Methylene Blue, Rhodamine B, Methyl Orange) under visible, UV, or solar light?
2. How do reaction conditions (e.g., initial dye concentration, catalyst dosage, and irradiation time) influence degradation efficiency?

The intended audience includes researchers working on wastewater treatment materials, chemical engineering modelers, and data scientists developing machine learning algorithms for predicting chemical degradation kinetics.

## Source summary

A total of 7 unique sources were tracked, categorized into three distinct groups:
- **Group A: Scientific Papers (Primary Sources)** — 6 open-access journal articles describing specific primary experimental results:
  1. *Improved photocatalytic degradation of methylene blue by novel hexagonal ZnO particles* (ZnO catalyst)
  2. *Kinetic Investigation of Photocatalytic Degradation of Methyl Orange Dye Using Mg-Doped Ag2O Nanoparticles* (Mg-Ag2O catalyst)
  3. *Visible Light-Driven Photocatalytic Degradation of Methylene Blue Dye Using a Highly Efficient Mg-Al LDH@g-C3N4@Ag3PO4 Nanocomposite*
  4. *A BiVO4/UU-200 heterojunction for efficient visible-light photocatalytic degradation of rhodamine B*
  5. *Co3O4-Bi2O3 heterojunction: An effective photocatalyst for photodegradation of rhodamine B dye*
  6. *ZnO/WO composite for efficient photocatalytic degradation of methylene blue dye under solar light*
- **Group B: Aggregated Datasets** — 1 open database source (Zenodo Record ID: 16640173), which provided 30 high-density experimental rows.
- **Group C: Reference Data & Regulators** — The PubChem REST API was integrated as an external reference database for resolving, validating, and enriching chemical identifiers (preferred names, CIDs, and molecular formulas).

All sources and the compiled dataset are licensed under the Creative Commons Attribution 4.0 International (**CC-BY-4.0**) license, permitting open reuse and distribution.

## Extraction summary

Data extraction was executed using automated, reproducible scripts:
- **PDF Extraction (6 records):**
  - *Methods:* Layout parsing using the MinerU framework to convert multi-column PDF layouts and tables into structured Markdown/HTML. A Python script ([extract_pdf.py](../scripts/extract_pdf.py)) then sent the parsed content to the `gemini-2.5-flash` model using structured JSON output mode under strict guidelines (no internal calculations permitted).
  - *Issues:* Reconstructing multi-component chemical formulas without layout errors, handling diverse input unit scales without introducing hallucinated conversion values.
- **Web Extraction (30 records):**
  - *Methods:* A Python script ([extract_web.py](../scripts/extract_web.py)) scraped data files and protocol metadata from the Zenodo API (Record 16640173) and utilized `gemini-3.1-flash-lite` to automatically map source Excel columns to target database columns.
  - *Issues:* Extracting implicit parameters (e.g., initial concentration and catalyst dosage) that were omitted from the main data sheets because they were defined as fixed constants in separate protocol metadata spreadsheets.
- **Links to practice reports:** See [Practice 3 — PDF extraction](practice_03_pdf_extraction.md) and [Practice 4 — Web extraction](practice_04_web_extraction.md) for deeper details.

## Cleaning and normalization summary

The data cleaning pipeline ([clean_dataset.py](../scripts/clean_dataset.py)) executes steps mapped in [cleaning_pipeline.json](../specs/cleaning_pipeline.json):
1. **Merge Sources:** Merges 6 PDF-extracted rows and 30 Zenodo-extracted rows into `merged_records.csv`.
2. **Normalize Units:** Standardizes concentration to `mg/L` (converting `mgl-1`, `ppm`, `mg L-1`), catalyst dosage to `g/L` (converting `gl-1`, `g/l`), and time to `min`.
3. **Enrich Dye Info:** Maps dye names via vocabularies, queries the PubChem API to resolve preferred name, CID, and molecular formula, writing them directly.
4. **Standardize Missing Values:** Aligns empty cells, `NaN`, and missing value tokens to `null` values.
5. **Schema Validation:** Validates format types and requirements against the JSON schema.
6. **Filtering & Deduplication:** Removes unresolved dye entries and drops duplicate rows matching on `record_id` (0 duplicates were detected; all 36 records were retained).

## Validation summary

Project verification was fully successful:
- **Project validation script ([validate_project.py](../scripts/validate_project.py)):** Passed with 0 errors and 0 warnings.
- **Unit tests (`pytest`):** 9/9 tests passed (100% success rate), verifying repository structure, schema integrity, DOI completeness, metadata file availability, and CSV parseability.
- **Outstanding warnings:** None.

## Limitations

- **Coverage Gaps:** There is a strong publication bias in scientific literature; "negative" or zero-degradation control runs are almost never published.
- **Incomplete Catalyst Properties:** Important semiconductor properties (such as surface area `catalyst_surface_area_m2g`, particle size `catalyst_particle_size_nm`, and band gap `catalyst_band_gap_ev`) are frequently not measured or specified in primary publications, leaving those fields empty in the final dataset.
- **Uncertain Extractions:** Complex composite catalyst formulations are prone to potential OCR/transcription errors.
- **Upstream Inconsistencies:** The Zenodo dataset relied on self-reported entries which, despite normalization, may contain varying baseline measurement uncertainties.

## Final artifacts

| Artifact | Path |
|----------|------|
| Processed dataset | [dataset.csv](../data/processed/dataset.csv) |
| Schema | [dataset_schema.json](../specs/dataset_schema.json) |
| Source map | [source_map.json](../specs/source_map.json) |
| Dataset card | [dataset_card.md](../dataset_card.md) |
| Citation | [CITATION.cff](../CITATION.cff) |
| License | [LICENSE](../LICENSE) |
