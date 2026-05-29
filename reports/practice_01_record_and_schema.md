# Practice 1 — Record definition and dataset schema

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
| `source_doi` | Yes | String (ID) | DOI of the source article (to ensure data verifiability) |
| `catalyst_formula` | Yes | String | Photocatalyst formula (e.g., TiO2, g-C3N4) |
| `dye_name` | Yes | String | Name of the dye (Methylene Blue, Rhodamine B) |
| `initial_dye_conc` | Yes | Float | Initial dye concentration in the solution (mg/L) |
| `catalyst_dosage` | Yes | Float | Catalyst mass per solution volume (g/L) |
| `light_type` | Yes | Categorical | Light source. Values: UV, Visible, Solar, LED |
| `time_min` | Yes | Float | Irradiation time of the solution (in minutes) |
| `efficiency_percent` | Yes | Float | Target variable: % of dye degradation (0.0 – 100.0) |

## Ambiguous cases

When collecting data, decisions for the following ambiguous situations must be taken into account and recorded:
- Digitizing degradation kinetics graphs when numerical tables are absent in the text of the article.
- A method for standardizing dye names and bringing them to a single format (e.g., via CAS numbers in PubChem).
- Normalizing the chemical formulas of catalysts (e.g., $TiO_2$ vs titanium dioxide) for proper text field operations.