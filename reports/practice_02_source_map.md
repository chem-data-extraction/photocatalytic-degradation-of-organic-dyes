# Source map

## Source search strategy

The search is conducted across specialized scientific journals, dedicated repositories, and open datasets using keywords related to photocatalysis and dye degradation (e.g., "photocatalytic dataset", "dye degradation prediction"). Data validation and normalization are performed using external chemical reference books and APIs.

## Source groups

- **Group A: Scientific Papers (Primary Sources)** — text documents (PDF) containing experimental descriptions, kinetics graphs, and summary tables.
- **Group B: Aggregated Datasets** — ready-made tabular files (CSV, XLSX, JSON) and code repositories containing collected data arrays.
- **Group C: Reference Data & Regulators** — structured databases and web interfaces (APIs) for the validation and normalization of chemical names.

## Priority sources

Sources are ranked by extraction priority to optimize dataset building speed and targeted gap-filling:

1. **High Priority:** Ready-made datasets from GitHub / Zenodo (Group B) — for instant baseline data collection.
   - *Examples:* Zenodo Repository, Mendeley Data, Figshare Archive, GitHub, Hugging Face Datasets.
2. **Medium Priority:** Summary tables from review papers in Applied Catalysis B and Journal of Hazardous Materials (Group A) — for dataset expansion.
   - *Examples of profile journals:* Applied Catalysis B: Environment and Energy, Journal of Hazardous Materials, Chemical Engineering Journal, Chemosphere, Journal of Environmental Chemical Engineering, ACS Applied Materials & Interfaces, Environmental Science & Technology on the ScienceDirect (Elsevier) and ACS platforms.
3. **Low Priority:** Text parsing of individual papers (Group A) — for targeted gap-filling.

**Subsidiary sources for validation:**
- PubChem (obtaining CAS numbers and structures for dyes like Methylene Blue, Rhodamine B, Methyl Orange).
- ChemSpider (Royal Society of Chemistry database).
- The Materials Project (checking basic physical properties and crystal structures of catalysts like $TiO_2$ or $ZnO$).

## Expected data types

- Text documents (PDF) with descriptions of conditions.
- Kinetics graphs (requiring digitization).
- Summary and ready-made tables (CSV, XLSX, JSON formats).
- Web interfaces and structured databases (APIs).

## Expected conflicts and overlaps

- **Primary source duplication:** Repetition of the same primary sources (DOIs) when downloading different aggregated datasets from Group B. Deduplication by the `source_doi` field is required.
- **Baseline condition matching:** Overlap of baseline conditions (identical concentrations of popular dyes) by different authors in Group A.

## Lineage Connections
Laboratory experiment $\rightarrow$ Journal publication (Group A) $\rightarrow$ Extraction by authors of reviews / ML models into CSV (Group B) $\rightarrow$ Collection into our dataset $\rightarrow$ Validation via PubChem (Group C).

## Coverage gaps

The following systematic gaps in publications are expected during data collection and must be considered:
- **Absence of "negative" results:** Papers almost never publish experiments where the degradation is equal to 0%.
- **Missing physical properties:** Authors frequently omit measuring or specifying the specific surface area of the catalyst powder.
- **Discrepancies in units:** Differences in specifying lamp power (some authors write Watts, while others use $mW/cm^2$).