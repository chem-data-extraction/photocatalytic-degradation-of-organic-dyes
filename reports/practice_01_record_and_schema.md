# Record definition and dataset schema

## Topic

Photocatalytic degradation of organic dyes.

## Scientific task

Task formalization, defining strict dataset boundaries, and establishing the foundation for subsequent source searching and data extraction.

## One-record definition

**One record** = a single unique water purification experiment described in a scientific paper. This experiment captures exactly one combination: "catalyst + dye + specific lighting and time conditions = resulting degradation percentage." In the data table, this corresponds to a single row.

## Examples of records

| Example | Why it counts |
|---------|----------------|
| An experiment containing the chemical formula of the material, the name of the pollutant, key experimental parameters (concentration, dosage, light, time), and the final degradation result. | Includes all required parameters and an exact result for a single combination of conditions. |
| Papers where the pollutants are specifically organic dyes (Methylene Blue, Rhodamine B, Methyl Orange, etc.) under the influence of light. | Matches the inclusion criteria for the type of pollutant and the presence of light exposure. |
| Experiments with clear numerical results: reaction time and degradation percentage (or a graph that can be digitized). | Provides verifiable quantitative target values. |

## Non-record examples

| Example | Why it is not a record |
|---------|-------------------------|
| Detailed step-by-step instructions for the synthesis of the catalyst itself (calcination temperature, powder stirring time, etc.). | Excluded from the record as it relates to synthesis, not the degradation experiment itself. |
| Authors' textual discussions regarding reaction mechanisms. | Excluded because it is a qualitative description rather than a structured numerical parameter. |
| Experiments on the degradation of other types of pollutants (antibiotics, pesticides, phenols). | Violates the inclusion criteria (not an organic dye). |
| "Dark experiments," where only dye adsorption by the powder surface occurs without the participation of light. | Does not meet the condition of conducting the experiment under light exposure. |
| Papers where the catalyst is used in the form of bulk films or membranes. | Excluded to ensure dosage comparability (restricted to powders/suspensions only). |

## Dataset fields

| Field Name | Required? | Format | Description / Example |
|:---|:---|:---|:---|
| `record_id` | Yes | String (ID) | Stable unique identifier for one degradation measurement record. |
| `source_id` | Yes | String | Identifier linking to an entry in `specs/source_map.json`. |
| `catalyst` | Yes | String | Composition/formula of the photocatalyst used (e.g., `TiO2`, `MicNo-ZnO`). |
| `catalyst_band_gap_ev` | No | Float | Band gap of the photocatalyst in eV (e.g., `3.2`). |
| `catalyst_surface_area_m2g` | No | Float | Specific surface area of the photocatalyst in m2/g (e.g., `50.0`). |
| `catalyst_particle_size_nm` | No | Float | Particle size / diameter of the photocatalyst in nm (e.g., `21.0`). |
| `dye_name` | Yes | String | Standardized preferred name of the organic dye pollutant (e.g., `Methylene Blue`). |
| `dye_pubchem_cid` | Yes | Integer | PubChem Compound ID (CID) of the dye (e.g., `6099`). |
| `dye_molecular_formula` | No | String | Molecular formula of the dye (e.g., `C16H18ClN3S`). |
| `initial_dye_concentration_value` | No | Float | Initial concentration of the dye pollutant (e.g., `10.0`). |
| `initial_dye_concentration_unit` | No | String | Unit of the initial dye concentration, standardized to `mg/L`. |
| `catalyst_dosage_value` | No | Float | Photocatalyst dosage or concentration in the reaction mixture (e.g., `1.0`). |
| `catalyst_dosage_unit` | No | String | Unit of the catalyst dosage, standardized to `g/L`. |
| `light_type` | No | Categorical | Type of light source used for irradiation (UV, Visible, Solar, LED, Dark). |
| `irradiation_time_value` | No | Float | Duration of light irradiation (e.g., `60.0`). |
| `irradiation_time_unit` | No | String | Unit of irradiation time, standardized to `min`. |
| `degradation_efficiency_percent` | No | Float | Dye degradation efficiency percentage (0.0 – 100.0). |

## Ambiguous cases

When collecting data, decisions for the following ambiguous situations must be taken into account and recorded:
- Digitizing degradation kinetics graphs when numerical tables are absent in the text of the article.
- A method for standardizing dye names and bringing them to a single format (e.g., via CAS numbers in PubChem).
- Normalizing the chemical formulas of catalysts (e.g., $TiO_2$ vs titanium dioxide) for proper text field operations.