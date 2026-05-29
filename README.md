# Photocatalysis Data Extraction & Cleaning Pipeline

Repository of the project for automatic extraction, cleaning, and standardization of photocatalytic degradation data of organic dyes. This project represents a reproducible tool for creating a high-quality chemical dataset based on scientific publications and open repositories (Zenodo).

---

## 1. Overview
This project is designed to extract structured photocatalysis parameters (catalyst chemical formula, dye name, dosages, light source type, irradiation time, and degradation efficiency) from scientific articles and Supplementary Information (in PDF format) using document layout analysis systems (MinerU) and large language models (Gemini API). The extracted data are combined with tabular datasets downloaded from Zenodo, enriched via the PubChem API, cleaned, and brought to a single quality standard.

---

## 2. What's inside
The repository architecture strictly complies with reproducibility and data standardization requirements:

```text
├── CITATION.cff           # Machine-readable dataset citation file
├── LICENSE                # Project license (MIT)
├── README.md              # Main entry point and description of the project (this file)
├── environment.yml        # Conda environment configuration file
├── requirements.txt       # List of Python dependencies for pip
├── run_pipeline.py        # Main orchestrator script to run the pipeline
├── config/
│   └── default.yaml       # Global configuration file for parameters and paths
├── specs/                 # JSON schemas, source map, manifests, pipeline, and dictionaries
│   ├── dataset_schema.json # JSON schema of the data structure for validation
│   ├── source_map.json    # Map of all data sources and IDs
│   ├── pdf_extraction_manifest.json # PDF extraction configuration
│   ├── web_extraction_manifest.json # Web extraction configuration
│   ├── cleaning_pipeline.json # Configuration of processing steps
│   ├── validation_rules.json # Custom rules for validation
│   ├── units.json         # Reference and mapping of measurement units (JSON)
│   └── vocabularies.json  # Vocabulary mapping dye trivial names to formal names (JSON)
├── data/                  # Data storage, split by processing stages
│   ├── raw/               # READ-ONLY: original raw files
│   │   ├── pdf/           # Original scientific articles in PDF format
│   │   ├── web/           # HTML snapshots, saved pages, or API responses
│   │   └── external/      # Third-party CSV, ZIP, or database exports (Zenodo, etc.)
│   ├── extracted/         # Consolidated extraction outputs
│   │   ├── pdf_extracted_records.csv  # Extracted records from PDFs
│   │   ├── web_extracted_records.csv  # Extracted records from Web/Zenodo
│   │   └── extraction_log.jsonl       # Log of extraction events
│   ├── interim/           # Interim partially preprocessed files
│   │   ├── pdf/           # Outputs from merge-si stage
│   │   ├── ingested/      # Recognized text and layout from MinerU (Markdown)
│   │   ├── extracted/     # Individual extracted JSON files via Gemini API
│   │   ├── merged_records.csv # Merged raw table (before final cleaning)
│   │   └── pubchem_cache.json # Cache of PubChem API queries to optimize rate limits
│   └── processed/         # Final validated and standardized dataset
│       └── dataset.csv    # Final publication-ready dataset
├── scripts/               # Data processing pipelines
│   ├── extract_pdf.py     # PDF merging, layout analysis, and Gemini extraction
│   ├── extract_web.py     # Zenodo dataset downloader and consolidation
│   ├── build_dataset.py   # Combines PDF and Web extracted CSVs
│   ├── clean_dataset.py   # Cleans, enriches via PubChem, and normalizes
│   ├── validate_project.py # Checks database structure against schemas
│   └── utils/             # Helper modules (logger, config, environment)
└── reports/               # Folder for data quality reports
    ├── validation_report.md # Report on validation results against the schema
    ├── conflicts.csv        # Log of unresolved conflicts and parsing errors
    └── missing_values_report.md # Report on missing values (NaN)
```

---

## 3. How it was created
The final dataset is created through a reproducible step-by-step processing pipeline:

```mermaid
graph TD
    A[data/raw/pdf] -->|extract_pdf.py| B[data/extracted/pdf_extracted_records.csv]
    C[data/raw/external] -->|extract_web.py| D[data/extracted/web_extracted_records.csv]
    B -->|build_dataset.py| E[data/interim/merged_records.csv]
    D -->|build_dataset.py| E
    E -->|clean_dataset.py| F[data/processed/dataset.csv]
```

### Processing Steps:
1. **`extract_pdf.py`**: Merges supplementary documents, analyzes PDF layout via MinerU, extracts parameters via Gemini API, and outputs consolidated records to `data/extracted/pdf_extracted_records.csv` and individual JSON files to `data/interim/extracted/`.
2. **`extract_web.py`**: Queries and downloads Zenodo tabular datasets to `data/raw/external`, filters records, and outputs consolidated records to `data/extracted/web_extracted_records.csv`.
3. **`build_dataset.py`**: Merges PDF and Web extraction tables into a single schema-compliant `data/interim/merged_records.csv`.
4. **`clean_dataset.py`**: Performs unit normalization, maps dye names via PubChem API, resolves conflicts, filters invalid rows, and saves the final output to `data/processed/dataset.csv`.

*Reproducibility:* All stochastic processes (such as LLM generation temperature) are fixed in scripts via API parameters.

---

## 4. Data schema and columns
Each row of the final dataset `data/processed/dataset.csv` represents a single measurement of degradation efficiency at a specific point in time within one experiment.

| Column Name | Data Type | Required? | Description | Example |
| :--- | :--- | :---: | :--- | :--- |
| `source_id` | String | No | Source identifier (article DOI or Zenodo ID) | `ao3c07326` |
| `catalyst` | String | No | Composition of the photocatalyst used | `Mg-doped Ag2O` |
| `catalyst_band_gap_ev` | Number | No | Band gap of the photocatalyst in eV | `2.6` |
| `catalyst_surface_area_m2g` | Number | No | Specific surface area of the photocatalyst in m²/g | `50.2` |
| `catalyst_particle_size_nm` | Number | No | Particle size / diameter of the photocatalyst in nm | `23.87` |
| `dye_name` | String | No | Normalized preferred name of the dye (from PubChem) | `Rhodamine B` |
| `dye_pubchem_cid` | Integer | **Yes** | Official PubChem Compound ID of the dye | `6099` |
| `initial_dye_concentration_value` | Number | No | Initial concentration of the dye | `10.0` |
| `initial_dye_concentration_unit` | String | No | Initial dye concentration unit (converted to `mg/L`) | `mg/L` |
| `catalyst_dosage_value` | Number | No | Photocatalyst dosage/concentration | `0.25` |
| `catalyst_dosage_unit` | String | No | Catalyst dosage unit (converted to `g/L`) | `g/L` |
| `light_type` | String | No | Type of radiation (`UV`, `Visible`, `Solar`, `LED`, `Dark`) | `Visible` |
| `irradiation_time_value` | Number | **Yes** | Time elapsed since the start of irradiation | `120.0` |
| `irradiation_time_unit` | String | **Yes** | Time unit (converted to `min`, `hours`, `s`) | `min` |
| `degradation_efficiency_percent` | Number | **Yes** | Degradation efficiency (%) within the range of 0-100 | `95.5` |

---

## 5. Units and controlled vocabularies
External reference dictionaries are used to eliminate discrepancies in physical and chemical data:
*   **Measurement units (`specs/units.json`)**: Contains mappings of various unit representations to standardized formats. For example, `ppm`, `mg l-1`, `mg/l` are normalized to a strict `mg/L`.
*   **Dye names dictionary (`specs/vocabularies.json`)**: Maps abbreviations to full names (e.g., `rhb` -> `rhodamine b`, `mb` -> `methylene blue`).
*   **PubChem API**: Allows verifying the dye by name, retrieving its structural formula and a single identifier (`dye_pubchem_cid`), and filtering out non-existent or incorrectly recognized compounds.

---

## 6. Data sources and licenses
*   **Original PDF articles**: Collected from authoritative scientific chemistry journals (ACS Omega, Scientific Reports, etc.). Rights to the original articles belong to their respective publishers.
*   **Third-party datasets**: Downloaded from Zenodo (e.g., repository [zenodo_16640173](https://zenodo.org/records/16640173)), distributed under the Creative Commons Attribution 4.0 International license (CC-BY-4.0).
*   **Project code**: Supplied under the **MIT License** (see [LICENSE](file:///home/arutamonofu/dev/study/itmo_extraction/LICENSE)).

---

## 7. Data quality and validation
Quality validation is performed automatically during each run of the cleaning script. All reports are generated in the `reports/` folder:
1.  **[validation_report.md](file:///home/arutamonofu/dev/study/itmo_extraction/reports/validation_report.md)** — contains general validation metrics, information on the applied schema, and a row-by-row log of validation errors.
2.  **[missing_values_report.md](file:///home/arutamonofu/dev/study/itmo_extraction/reports/missing_values_report.md)** — contains a detailed analysis of missing values (quantitative and percentage summary) for each feature before and after filtering.
3.  **[conflicts.csv](file:///home/arutamonofu/dev/study/itmo_extraction/reports/conflicts.csv)** — records detailed logs of all unresolved discrepancies (e.g., unconfirmed dyes in PubChem or schema data type mismatches).

---

## 8. How to use the data

### Prerequisites
Requires Python 3.10+ or Conda.

### Environment Setup
Install dependencies using Conda:
```bash
conda env create -f environment.yml
conda activate itmo_extraction
```
Or use standard pip:
```bash
pip install -r requirements.txt
```

### Running the Pipeline
1. Place raw articles into `data/raw/pdf/`.
2. Add API keys to the `.env` file in the root folder:
   ```env
   GEMINI_API_KEY="your_gemini_key"
   MINERU_TOKEN="your_mineru_token"
   ```
3. Run the orchestrator:
   ```bash
   python run_pipeline.py --config config/default.yaml
   ```

### Importing Data in Python
The final dataset can be easily loaded using the pandas library:
```python
import pandas as pd
df = pd.read_csv("data/processed/dataset.csv")
print(df.head())
```

---

## 9. Known limitations
*   **Pollutant types limitation**: The current version of the dataset is focused only on three popular dyes: Rhodamine B, Methylene Blue, and Methyl Orange.
*   **Dependency on LLMs**: The quality of extracting complex tables and implicit parameters from article texts depends on the accuracy of the Gemini API.
*   **Lack of reactor parameters**: Characteristics such as lamp power (W), reactor geometry, and medium pH are not included in the current data schema specification.

---

## 10. Citation and contact
When using this dataset or code in scientific publications, please cite it in accordance with the [CITATION.cff](file:///home/arutamonofu/dev/study/itmo_extraction/CITATION.cff) file:

```bibtex
@misc{PhotocatalysisDataset2026,
  author       = {Ivanov, Ivan and Petrov, Petr},
  title        = {Photocatalytic Dye Degradation Dataset},
  year         = 2026,
  publisher    = {Zenodo},
  version      = {1.0.0},
  doi          = {10.5281/zenodo.1234567}
}
```

*Contact:* support@itmo.ru

---

## 11. Changelog
*   **`v0.1`** (Internal working version):
    *   Created the basic pipeline structure and integration with Gemini API.
*   **`v1.0`** (Release version):
    *   Implemented strict directory structure: `raw/`, `interim/`, `processed/`.
    *   Introduced metadata standardization (`units.json`, `vocabularies.json` in specs).
    *   Added automatic validation reports (`reports/`).
    *   Created academic files `CITATION.cff` and `LICENSE`.