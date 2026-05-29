# Practice 3 — PDF extraction

> Align with `specs/pdf_extraction_manifest.json` and `data/extracted/pdf_extracted_records.csv`.

## Selected PDF sources

| source_id | pdf_id | Year (approx.) | Path | Title |
|-----------|--------|----------------|------|-------|
| 2024.v50.i4.4030 | 2024.v50.i4.4030 | 2024 | data/raw/pdf/ | Improved photocatalytic degradation of methylene blue by novel hexagonal ZnO particles |
| 8874791 | 8874791 | 2026 | data/raw/pdf/ | Kinetic Investigation of Photocatalytic Degradation of Methyl Orange Dye Using Mg-Doped Ag2O Nanoparticle |
| ao3c07326 | ao3c07326 | 2024 | data/raw/pdf/ | Visible Light-Driven Photocatalytic Degradation of Methylene Blue Dye Using a Highly Efficient Mg-Al LDH@g-C3N4@Ag3PO4 Nanocomposite |
| d6na00104a | d6na00104a | 2026 | data/raw/pdf/ | A BiVO4/UU-200 heterojunction for efficient visible-light photocatalytic degradation of rhodamine B |
| j.arabjc.2022.103732 | j.arabjc.2022.103732 | 2022 | data/raw/pdf/ | Co3O4-Bi2O3 heterojunction: An effective photocatalyst for photodegradation of rhodamine B dye |
| s41598-026-40207-0 | s41598-026-40207-0 | 2026 | data/raw/pdf/ | ZnO/WO composite for efficient photocatalytic degradation of methylene blue dye under solar light |

## Why these PDFs were selected

- **Relevance**: All selected papers describe primary experimental research on the photocatalytic degradation of organic dyes (Methylene Blue, Methyl Orange, Rhodamine B). They capture key physical parameters such as catalyst type, dye initial concentration, catalyst dosage, light sources, reaction times, and final degradation efficiency.
- **Open Access**: All articles are published under open-access models (e.g. CC-BY), which allows for legal data retrieval, parsing, and inclusion in public databases.
- **Data & Layout Quality**: These documents contain structured text, clearly formatted tables of experimental results, and high-quality charts. This makes them ideal for benchmarking OCR engines (like MinerU) and Large Language Models (like Gemini).
- **Research Overlap**: These sources offer a diverse set of photocatalysts (e.g., ZnO, Ag2O, LDH composites, BiVO4/MOF heterojunctions, Co3O4-Bi2O3, ZnO/WO3) and light sources (UV, Visible, Solar, LED) to test the robustness and boundary limits of the dataset schema.

## Pages used

- **2024.v50.i4.4030.pdf** (12 pages total):
  - *Page 1 (Abstract)*: Summary of the main result (MicNo-ZnO catalyst, 96% Methylene Blue removal in 180 min).
  - *Pages 8–11 (Results and Discussion)*: Text sections detailing the impact of initial dye concentration (10 mg/L) and catalyst dosage (0.25 g/L) under UV irradiation (Section 3.4, Figure 13).
- **8874791.pdf** (12 pages total):
  - *Page 1 (Abstract)*: Summary of coprecipitation synthesis and primary results.
  - *Page 5 (Kinetics)*: Section 3.8 / Figure 8 showing degradation kinetics (96.1% MO removal in 150 min at 30 ppm).
  - *Page 6 (Dosage)*: Section 3.9 / Figure 9 detailing the effect of catalyst dosage (0.4 g).
- **ao3c07326.pdf** (24 pages total):
  - *Page 1 (Abstract)*: Overview of Mg-Al LDH@g-C3N4@Ag3PO4 synthesis and its 99% MB degradation performance in 45 min under visible light.
  - *Pages 11–13 (Photocatalysis)*: Text detailing the specific experimental conditions (10 mg/L MB, 0.05 g dosage, visible light).
- **d6na00104a.pdf** (31 pages total):
  - *Page 1 (Abstract)*: High-level overview of the 5% BiVO4/UU-200 composite achieving 96.79% Rhodamine B degradation under LED light within 120 min.
  - *Page 8 (Experimental)*: Sections defining the catalyst dosage (10 mg) and dye concentration (15 mg/L).
- **j.arabjc.2022.103732.pdf** (10 pages total):
  - *Page 1 (Abstract)*: Performance of Co3O4-Bi2O3 heterojunction degrading 92% Rhodamine B in 120 min under solar light.
  - *Page 6 (Results)*: Setup details (0.05 g catalyst, 100 mg/L dye concentration).
- **s41598-026-40207-0.pdf** (17 pages total):
  - *Page 1 (Abstract)*: Overview of ZnO/WO3 composite, simulated solar light, 93.8% MB degradation in 60 min (3 mg catalyst, 30 mL volume, 5 ppm concentration).
  - *Page 8 (Photocatalysis)*: Detailed breakdown of the optimization runs.

## Extraction methods

### Tools Considered
- **PyMuPDF**: Fast text parsing, but loses two-column reading layouts and fails on mathematical notation and table structures.
- **pdfplumber / Camelot / Tabula**: Excellent for clean, grid-based tables, but fail when tables contain wrapped text, merged cells, or are embedded inside complex two-column PDF structures.
- **Manual entry**: Highly accurate but labor-intensive and unscalable for large-scale data collection.

### Selection and Pipeline Implementation
A hybrid automated pipeline was developed and implemented via `scripts/extract_pdf.py`:
1. **pypdf**: Used for matching and merging main PDF documents with their Supplementary Information (SI) sheets (matching `*_si.pdf` names).
2. **MinerU (Layout Parser)**: Selected to ingest and convert the raw PDFs. It reconstructs multi-column flows, extracts tables into clean Markdown/HTML formatting, identifies embedded chart images, and parses complex mathematical equations/chemical formulas into LaTeX.
3. **Gemini GenAI (gemini-2.5-flash)**: Selected as the extraction engine. The model is fed the MinerU-parsed markdown text along with extracted chart figures and is instructed to fill the predefined JSON schema under strict prompt rules.
4. **Pandas**: Consolidates individual extracted JSON files into the final CSV.

## Extracted fields

The raw extracted values map directly to the `dataset_schema.json` fields:
- `record_id`: Generated systematically as `rec_photo_pdf_{pdf_id}_{index:04d}` (e.g. `rec_photo_pdf_2024.v50.i4.4030_0001`).
- `source_id`: Filled with the filename stem (e.g. `2024.v50.i4.4030`).
- `catalyst`: Chemical formulation of the active catalyst (verbatim: `MicNo-ZnO`, `Mg-doped Ag2O`, etc.).
- `dye_name`: Common name of the dye (verbatim: `Methylene blue`, `Methyl Orange`, `rhodamine B`).
- `initial_dye_concentration_value` & `_unit`: Extracted verbatim (`10.0` & `mg/L`, `30.0` & `ppm`, `15.0` & `mg L-1`).
- `catalyst_dosage_value` & `_unit`: Extracted verbatim (`0.25` & `g/L`, `0.4` & `g`, `10.0` & `mg`).
- `light_type`: Standardized categorical category (`UV`, `Visible`, `Solar`, `LED`).
- `irradiation_time_value` & `_unit`: Time duration and unit (`180.0` & `min`, `120.0` & `min`, `60.0` & `min`).
- `degradation_efficiency_percent`: Extracted target variable (`96.0`, `96.1`, `99.0`, `96.79`).

*Note on Post-processing*: Physical properties (`catalyst_band_gap_ev`, `catalyst_surface_area_m2g`, `catalyst_particle_size_nm`) and dye chemical identifiers (`dye_pubchem_cid`, `dye_molecular_formula`) are left empty in raw PDF extraction. They are resolved programmatically in the cleaning and normalization pipelines via PubChem API integration.

## Extraction problems

- **Varying Units & Measurement Scales**: Concentrations and dosages are represented differently across papers (e.g. `mg/L` vs `mg L-1` vs `ppm` for concentration; `g/L` concentration vs `mg` absolute mass for dosage). Converting units requires math/formulas, which was prohibited in the LLM extraction step to prevent hallucinations.
- **Complex Composite Formulas**: Multi-component catalysts (e.g. `Mg-Al LDH@g-C3N430@Ag3PO45`) are prone to OCR transcription errors. Using MinerU's LaTeX parser helped keep formulas readable and correct.
- **Absence of Negative/Control Data**: The literature rarely publishes zero-degradation experiments, leading to a bias in the dataset.
- **Missing Catalyst Properties**: Crucial properties like the surface area or particle size of the catalyst are frequently not mentioned in the main text of the papers, leading to sparse columns.

## Output files

- `data/extracted/pdf_extracted_records.csv` — consolidated table of 6 records.
- `data/extracted/extraction_log.jsonl` — audit log showing step, status, and record count.
- Raw PDFs under `data/raw/pdf/`

