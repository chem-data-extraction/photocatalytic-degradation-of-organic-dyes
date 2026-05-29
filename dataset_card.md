# Dataset card — Photocatalytic dye degradation dataset

## Dataset title

Photocatalytic dye degradation dataset

## Dataset summary

Tabular collection of experimentally reported organic dye degradation measurements under light irradiation in the presence of various semiconductor photocatalysts, including catalyst properties (composition, band gap, surface area, particle size), dye details (name, PubChem CID, formula), reaction conditions (dosage, initial concentration, light type, irradiation time), degradation efficiency, and provenance tracking.

## Scientific task

Support comparison of reported degradation efficiencies and experimental conditions across literature and community-shared dataset sources for various semiconductor photocatalysts and organic dyes.

## Record unit

One row = one experimentally reported dye degradation efficiency measurement at a specific point in time within one experiment from a specific source under a specific set of reaction conditions.

## Data sources

Defined in `specs/source_map.json`: journal PDFs (6 publications with manual/layout-extracted tables) and public Zenodo repository containing a photocatalytic degradation dataset (Record ID: 16640173).

## Data extraction procedure

1. PDF: `scripts/extract_pdf.py` guided by `specs/pdf_extraction_manifest.json`
2. Web: `scripts/extract_web.py` guided by `specs/web_extraction_manifest.json`
3. Logs: `data/extracted/extraction_log.jsonl`

## Data cleaning and normalization

`scripts/build_dataset.py` merges extracts; `scripts/clean_dataset.py` normalizes units (concentration to mg/L, dosage to g/L, time to min using `specs/units.json`), enriches dye names with PubChem CID and molecular formulas, standardizes missing values (to null), and deduplicates per `specs/cleaning_pipeline.json`.

## Dataset schema

Field definitions, types, and constraints: `specs/dataset_schema.json`. Final columns in `data/processed/dataset.csv`. Key columns include `record_id`, `source_id`, `catalyst`, `catalyst_band_gap_ev`, `catalyst_surface_area_m2g`, `catalyst_particle_size_nm`, `dye_name`, `dye_pubchem_cid`, `dye_molecular_formula`, `initial_dye_concentration_value`, `initial_dye_concentration_unit`, `catalyst_dosage_value`, `catalyst_dosage_unit`, `light_type`, `irradiation_time_value`, `irradiation_time_unit`, and `degradation_efficiency_percent`.

## Validation

Rules in `specs/validation_rules.json`; checks via `scripts/validate_project.py` and `tests/test_required_artifacts.py`.

## Known limitations

- Some experimental parameters (e.g. band gap, surface area) are missing from the primary source publications.
- Upstream Zenodo dataset might contain unverified or inconsistent reporting before normalization.
- Ground truth validation is limited to schema-level checks and unit constraints.

## Recommended use

Comparing photocatalytic performance of different semiconductor catalysts; benchmarking organic dye degradation models; analyzing the impact of experimental conditions (dosage, concentration, light type) on degradation rates.

## Not recommended use

Direct industrial design of photocatalytic reactors without verification of raw literature sources; modeling advanced kinetics without accounting for unmeasured factors (e.g. reactor geometry, light intensity).

## License

See `LICENSE` — Creative Commons Attribution 4.0 International (CC-BY-4.0) (refer to the `LICENSE` file for details, subject to upstream Zenodo/publisher licenses).

## Citation

See `CITATION.cff` for citing this dataset.

