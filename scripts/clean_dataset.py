#!/usr/bin/env python3
"""
Photocatalysis Dataset Cleaning, Normalization, and Validation Script.
Reads data/interim/merged_records.csv and writes data/processed/dataset.csv.
Generates reports in reports/.
"""

from __future__ import annotations

import os
import sys
import json
import time
import argparse
from pathlib import Path
import requests
import jsonschema
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from utils.logger import get_logger
from utils.env import load_dotenv
from utils.config import get_config_and_argv

logger = get_logger("clean_dataset", "logs/cleaning.log")

CACHE_FILE = ROOT / "data/interim/pubchem_cache.json"

def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            with CACHE_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load PubChem cache: {e}. Starting fresh.")
    return {}

def save_cache(cache: dict) -> None:
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CACHE_FILE.open("w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to save PubChem cache: {e}")

def load_dye_mapping(vocab_file: Path) -> dict:
    mapping = {}
    if vocab_file.exists():
        try:
            with vocab_file.open(encoding="utf-8") as f:
                raw_mapping = json.load(f)
            for syn, pref in raw_mapping.items():
                mapping[str(syn).strip().lower()] = str(pref).strip()
            logger.info(f"Loaded {len(mapping)} dye synonym mappings from '{vocab_file}'.")
        except Exception as e:
            logger.warning(f"Failed to load vocabularies from {vocab_file}: {e}")
    else:
        logger.warning(f"Vocabulary file {vocab_file} does not exist. Using empty mapping.")
    return mapping

def resolve_dye_name(name: str, vocab_mapping: dict) -> str:
    n = name.strip().lower()
    return vocab_mapping.get(n, name.strip())

def enrich_dye_info(raw_name: str, cache: dict, vocab_mapping: dict) -> dict:
    resolved_name = resolve_dye_name(raw_name, vocab_mapping)
    cache_key = resolved_name.lower().strip()
    
    if cache_key in cache:
        logger.info(f"Cache hit for dye: '{raw_name}' -> '{resolved_name}'")
        return cache[cache_key]
        
    logger.info(f"Cache miss for dye: '{raw_name}' -> '{resolved_name}'. Querying PubChem API...")
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{resolved_name}/property/Title,MolecularFormula/JSON"
    
    try:
        response = requests.get(url, timeout=10)
        time.sleep(0.25)  # Enforce rate limit (max 4 req/s)
        
        if response.status_code == 200:
            data = response.json()
            properties = data.get("PropertyTable", {}).get("Properties", [])
            if properties:
                prop = properties[0]
                cid = prop.get("CID")
                formula = prop.get("MolecularFormula")
                title = prop.get("Title", resolved_name)
                
                result = {
                    "preferred_term": title,
                    "pubchem_cid": cid,
                    "molecular_formula": formula
                }
                cache[cache_key] = result
                save_cache(cache)
                return result
        elif response.status_code == 404:
            logger.warning(f"Dye '{resolved_name}' not found in PubChem REST API.")
        else:
            logger.warning(f"PubChem API returned HTTP status {response.status_code} for dye '{resolved_name}'.")
    except Exception as e:
        logger.error(f"Error querying PubChem API for dye '{resolved_name}': {e}")
        
    result = {
        "preferred_term": raw_name,
        "pubchem_cid": None,
        "molecular_formula": None
    }
    cache[cache_key] = result
    save_cache(cache)
    return result

def load_unit_mapping(units_file: Path) -> dict:
    mapping = {}
    if units_file.exists():
        try:
            with units_file.open(encoding="utf-8") as f:
                raw_mapping = json.load(f)
            for raw, std in raw_mapping.items():
                mapping[str(raw).strip().lower().replace(" ", "")] = str(std).strip()
            logger.info(f"Loaded {len(mapping)} unit mappings from '{units_file}'.")
        except Exception as e:
            logger.warning(f"Failed to load units mapping from {units_file}: {e}")
    else:
        logger.warning(f"Units mapping file {units_file} does not exist. Using empty mapping.")
    return mapping

def harmonize_unit(val: object, unit_mapping: dict) -> object:
    if pd.isna(val) or not isinstance(val, str):
        return val
    cleaned = val.strip().lower().replace(" ", "")
    return unit_mapping.get(cleaned, cleaned)

def calculate_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    missing_count = df.isnull().sum()
    missing_pct = (df.isnull().sum() / len(df)) * 100
    return pd.DataFrame({
        'column': df.columns,
        'missing_count': missing_count,
        'missing_percentage': missing_pct
    })

def build_json_schema_from_template(template_schema_path: Path) -> dict:
    with template_schema_path.open(encoding="utf-8") as f:
        temp_schema = json.load(f)
    
    properties = {}
    required = []
    
    type_mapping = {
        "string": "string",
        "number": "number",
        "integer": "integer",
        "boolean": "boolean"
    }
    
    for field in temp_schema.get("fields", []):
        name = field["name"]
        ftype = field.get("type", "string")
        schema_type = type_mapping.get(ftype, "string")
        
        prop_schema = {
            "type": [schema_type, "null"] if not field.get("required", False) else schema_type,
            "description": field.get("description", "")
        }
        
        if name == "light_type":
            prop_schema["enum"] = ["UV", "Visible", "Solar", "LED", "Dark", None]
        elif name == "irradiation_time_unit":
            prop_schema["enum"] = ["min", "hours", "s", None]
        elif name == "degradation_efficiency_percent":
            prop_schema["minimum"] = 0
            prop_schema["maximum"] = 100
            
        properties[name] = prop_schema
        
        if field.get("required", False):
            required.append(name)
            
    return {
        "type": "object",
        "required": required,
        "properties": properties
    }

def clean_and_validate(
    input_csv: Path,
    output_csv: Path,
    template_schema_path: Path,
    units_file: Path,
    vocabularies_file: Path,
    reports_dir: Path
) -> bool:
    if not input_csv.is_file():
        logger.error(f"Input merged CSV file '{input_csv}' not found.")
        return False
        
    df = pd.read_csv(input_csv)
    initial_row_count = len(df)
    logger.info(f"Loaded {initial_row_count} rows from '{input_csv}'")
    
    pre_missing_stats = calculate_missing_values(df)
    unit_mapping = load_unit_mapping(units_file)
    vocab_mapping = load_dye_mapping(vocabularies_file)
    
    conflicts_log = []
    validation_failures = []
    
    # 1. Unit Harmonization
    unit_cols = [col for col in df.columns if col.endswith('_unit')]
    for col in unit_cols:
        df[col] = df[col].apply(lambda x: harmonize_unit(x, unit_mapping))
    logger.info(f"Harmonized unit columns: {unit_cols}")
    
    # 2. Data Enrichment via PubChem API
    cache = load_cache()
    preferred_terms = []
    cids = []
    formulas = []
    
    for idx, row in df.iterrows():
        name = row['dye_name']
        source_id = row['source_id']
        if pd.isna(name):
            preferred_terms.append(name)
            cids.append(None)
            formulas.append(None)
            conflicts_log.append({
                "row_index": idx,
                "source_id": source_id,
                "field": "dye_name",
                "value": "NaN",
                "error_type": "Missing Value",
                "description": "dye_name is null"
            })
            continue
            
        info = enrich_dye_info(name, cache, vocab_mapping)
        preferred_terms.append(info["preferred_term"])
        cids.append(info["pubchem_cid"])
        formulas.append(info["molecular_formula"])
        
        if info["pubchem_cid"] is None:
            conflicts_log.append({
                "row_index": idx,
                "source_id": source_id,
                "field": "dye_name",
                "value": name,
                "error_type": "PubChem Resolution Failure",
                "description": f"Could not resolve dye '{name}' on PubChem REST API"
            })
        
    df['dye_name'] = preferred_terms
    df['dye_pubchem_cid'] = cids
    df['molecular_formula'] = formulas
    logger.info("Enriched dye names and added PubChem CID/Molecular Formula.")
    
    # 3. NaN Handling / Defaults mapping
    excel_path = ROOT / 'data/raw/external/zenodo_16640173/LC1_φ_NMs_data.xlsx'
    zenodo_mask = df['source_id'] == 'zenodo_16640173'
    if excel_path.is_file():
        try:
            zenodo_df = pd.read_excel(excel_path, sheet_name='9. Descriptors')
            light_mapping = {
                'UV_LIGHT': 'UV',
                'Visible_LIGHT': 'Visible'
            }
            if len(zenodo_df) == zenodo_mask.sum():
                mapped_lights = zenodo_df[' Light Condition'].map(light_mapping).fillna('UV')
                df.loc[zenodo_mask, 'light_type'] = mapped_lights.values
                logger.info("Mapped Zenodo light_type values using the source Excel file.")
            else:
                df.loc[zenodo_mask, 'light_type'] = 'UV'
                logger.warning("Zenodo row count mismatch. Defaulting Zenodo light_type to 'UV'.")
        except Exception as e:
            logger.warning(f"Could not read Excel file to map light types: {e}. Defaulting Zenodo light_type to 'UV'.")
            df.loc[zenodo_mask, 'light_type'] = 'UV'
    else:
        df.loc[zenodo_mask, 'light_type'] = 'UV'
        logger.info("Source Excel not found. Set Zenodo light_type to 'UV' default.")
        
    df['light_type'] = df['light_type'].fillna('UV')

    for col in unit_cols:
        df[col] = df[col].apply(lambda x: harmonize_unit(x, unit_mapping))
        
    logger.info("NaN Handling completed.")
    
    # 4. Schema validation
    if not template_schema_path.is_file():
        logger.error(f"Template schema file '{template_schema_path}' not found.")
        return False
        
    schema = build_json_schema_from_template(template_schema_path)
    valid_records = []
    invalid_count = 0
    
    for index, row in df.iterrows():
        row_dict = row.to_dict()
        row_clean = {k: (None if pd.isna(v) else v) for k, v in row_dict.items()}
        record_to_validate = {k: v for k, v in row_clean.items() if k in schema.get("properties", {})}
        
        try:
            jsonschema.validate(instance=record_to_validate, schema=schema)
            valid_records.append(row_dict)
        except jsonschema.exceptions.ValidationError as e:
            invalid_count += 1
            field_name = e.path[0] if e.path else "schema"
            error_msg = f"Row {index} (source_id: '{row_clean.get('source_id')}') failed schema validation on field '{field_name}': {e.message}"
            validation_failures.append(error_msg)
            logger.error(error_msg)
            conflicts_log.append({
                "row_index": index,
                "source_id": row_clean.get('source_id'),
                "field": field_name,
                "value": str(e.instance),
                "error_type": "Schema Validation Failure",
                "description": e.message
            })
            
    logger.info(f"Validation summary: Valid rows = {len(valid_records)}, Invalid rows = {invalid_count}")
    
    dropped_pubchem_count = 0
    final_row_count = 0
    success = False
    
    if valid_records:
        cleaned_df = pd.DataFrame(valid_records)
        initial_len = len(cleaned_df)
        cleaned_df = cleaned_df.dropna(subset=['dye_pubchem_cid'])
        dropped_pubchem_count = initial_len - len(cleaned_df)
        
        if dropped_pubchem_count > 0:
            logger.warning(f"Dropped {dropped_pubchem_count} rows due to unresolved PubChem CIDs.")
            
        if not cleaned_df.empty:
            cleaned_df['dye_pubchem_cid'] = cleaned_df['dye_pubchem_cid'].astype(int)
            
            # Reorder columns to match template schema exactly
            schema_cols = [field["name"] for field in json.loads(template_schema_path.read_text(encoding="utf-8"))["fields"]]
            for col in schema_cols:
                if col not in cleaned_df.columns:
                    cleaned_df[col] = None
            cleaned_df = cleaned_df[schema_cols]
            
            # Deduplicate by record_id
            cleaned_df = cleaned_df.drop_duplicates(subset=["record_id"], keep="first")
            
            output_csv.parent.mkdir(parents=True, exist_ok=True)
            cleaned_df.to_csv(output_csv, index=False)
            logger.success(f"Cleaned dataset saved to '{output_csv}'")
            post_missing_stats = calculate_missing_values(cleaned_df)
            final_row_count = len(cleaned_df)
            success = True
        else:
            logger.error("No records remaining after PubChem filtering.")
            post_missing_stats = pd.DataFrame()
    else:
        logger.error("No valid records found after schema checks.")
        post_missing_stats = pd.DataFrame()

    # Generate reports
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. conflicts.csv
    conflicts_csv = reports_dir / "conflicts.csv"
    conflicts_df = pd.DataFrame(conflicts_log)
    if conflicts_df.empty:
        conflicts_df = pd.DataFrame(columns=["row_index", "source_id", "field", "value", "error_type", "description"])
    conflicts_df.to_csv(conflicts_csv, index=False)
    logger.success(f"Saved conflict log to '{conflicts_csv}'")
    
    # 2. missing_values_report.md
    missing_report = reports_dir / "missing_values_report.md"
    try:
        with missing_report.open("w", encoding="utf-8") as f_rep:
            f_rep.write("# Missing Values Report\n\n")
            f_rep.write(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f_rep.write("## 1. Merged Dataset (Before Cleaning)\n")
            f_rep.write(f"Total Rows: {initial_row_count}\n\n")
            f_rep.write("| Column | Missing Count | Missing Percentage |\n")
            f_rep.write("| --- | --- | --- |\n")
            for _, r in pre_missing_stats.iterrows():
                f_rep.write(f"| {r['column']} | {r['missing_count']} | {r['missing_percentage']:.2f}% |\n")
            f_rep.write("\n")
            
            f_rep.write("## 2. Final Dataset (After Cleaning and Filtering)\n")
            f_rep.write(f"Total Rows: {final_row_count}\n\n")
            if not post_missing_stats.empty:
                f_rep.write("| Column | Missing Count | Missing Percentage |\n")
                f_rep.write("| --- | --- | --- |\n")
                for _, r in post_missing_stats.iterrows():
                    f_rep.write(f"| {r['column']} | {r['missing_count']} | {r['missing_percentage']:.2f}% |\n")
            else:
                f_rep.write("Dataset is empty.\n")
        logger.success(f"Saved missing values report to '{missing_report}'")
    except Exception as e:
        logger.error(f"Failed to write missing values report: {e}")

    # 3. validation_report.md
    validation_report = reports_dir / "validation_report.md"
    try:
        with validation_report.open("w", encoding="utf-8") as f_val:
            f_val.write("# Validation and Standardization Report\n\n")
            f_val.write(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f_val.write("## Summary Metrics\n\n")
            f_val.write(f"- **Input merged records**: {initial_row_count}\n")
            f_val.write(f"- **Schema validation passed**: {len(valid_records)}\n")
            f_val.write(f"- **Schema validation failed**: {invalid_count}\n")
            f_val.write(f"- **Dropped due to missing PubChem CID**: {dropped_pubchem_count}\n")
            f_val.write(f"- **Final validated records exported**: {final_row_count}\n\n")
            
            f_val.write("## Schema Validation Failures\n\n")
            if validation_failures:
                f_val.write(f"Total of {len(validation_failures)} validation failure(s) found:\n\n")
                for fail in validation_failures:
                    f_val.write(f"- {fail}\n")
            else:
                f_val.write("All records passed the schema validation successfully! 🎉\n")
            f_val.write("\n")
            
            f_val.write("## PubChem Name Enrichment and Resolution Failures\n\n")
            pubchem_fails = [c for c in conflicts_log if c["error_type"] == "PubChem Resolution Failure"]
            if pubchem_fails:
                f_val.write(f"Total of {len(pubchem_fails)} dye name(s) could not be resolved on PubChem and were filtered out:\n\n")
                f_val.write("| Row Index | Source ID | Dye Name | Details |\n")
                f_val.write("| --- | --- | --- | --- |\n")
                for f in pubchem_fails:
                    f_val.write(f"| {f['row_index']} | {f['source_id']} | {f['value']} | {f['description']} |\n")
            else:
                f_val.write("All dyes were successfully resolved and enriched on PubChem API! 🎉\n")
        logger.success(f"Saved validation report to '{validation_report}'")
    except Exception as e:
        logger.error(f"Failed to write validation report: {e}")

    return success

# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================
def main() -> None:
    load_dotenv()
    config, config_path, remaining_argv = get_config_and_argv()
    
    parser = argparse.ArgumentParser(description="Clean, normalize, and enrich merged records.")
    parser.add_argument("--config", default="config/default.yaml", help="Path to config file.")
    parser.parse_args(remaining_argv)
    
    pipeline_conf = config.get("pipeline", {})
    clean_conf = config.get("stages", {}).get("clean", {})
    
    input_file = ROOT / clean_conf.get("input_file", "data/interim/merged_records.csv")
    # Redirect output directly to the template's final location
    output_file = ROOT / "data/processed/dataset.csv"
    template_schema = ROOT / "specs/dataset_schema.json"
    
    global CACHE_FILE
    cache_path = clean_conf.get("pubchem_cache_file", "data/interim/pubchem_cache.json")
    CACHE_FILE = ROOT / cache_path
    
    units_file = ROOT / clean_conf.get("units_file", "specs/units.json")
    vocabularies_file = ROOT / clean_conf.get("vocabularies_file", "specs/vocabularies.json")
    reports_dir = ROOT / clean_conf.get("reports_dir", "reports")
    
    success = clean_and_validate(
        input_csv=input_file,
        output_csv=output_file,
        template_schema_path=template_schema,
        units_file=units_file,
        vocabularies_file=vocabularies_file,
        reports_dir=reports_dir
    )
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
