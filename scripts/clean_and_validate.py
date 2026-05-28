#!/usr/bin/env python3
"""
Photocatalysis Dataset Cleaning, Normalization, and Validation Script.
Created for: ITMO Photocatalysis Project
"""

import os
import json
import time
import csv
from utils.logger import get_logger
import requests
import jsonschema
import pandas as pd

logger = get_logger("clean_and_validate", "logs/cleaning.log")

CACHE_FILE = "data/interim/pubchem_cache.json"

def load_cache():
    """Loads the PubChem query cache if it exists."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load PubChem cache: {e}. Starting fresh.")
    return {}

def save_cache(cache):
    """Saves the PubChem query cache to disk."""
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to save PubChem cache: {e}")

def load_dye_mapping(vocab_file):
    """Loads dye synonyms from a CSV file."""
    mapping = {}
    if os.path.exists(vocab_file):
        try:
            vocab_df = pd.read_csv(vocab_file)
            for _, row in vocab_df.iterrows():
                syn = str(row['synonym']).strip().lower()
                pref = str(row['preferred_term']).strip()
                mapping[syn] = pref
            logger.info(f"Loaded {len(mapping)} dye synonym mappings from '{vocab_file}'.")
        except Exception as e:
            logger.warning(f"Failed to load vocabularies from {vocab_file}: {e}")
    else:
        logger.warning(f"Vocabulary file {vocab_file} does not exist. Using empty mapping.")
    return mapping

def resolve_dye_name(name, vocab_mapping):
    """Maps common abbreviations to official names for better PubChem API query success."""
    n = name.strip().lower()
    return vocab_mapping.get(n, name.strip())

def enrich_dye_info(raw_name, cache, vocab_mapping):
    """
    Enriches dye name using PubChem REST API.
    Returns preferred term, CID, and molecular formula.
    """
    resolved_name = resolve_dye_name(raw_name, vocab_mapping)
    cache_key = resolved_name.lower().strip()
    
    if cache_key in cache:
        logger.info(f"Cache hit for dye: '{raw_name}' -> '{resolved_name}'")
        return cache[cache_key]
        
    logger.info(f"Cache miss for dye: '{raw_name}' -> '{resolved_name}'. Querying PubChem API...")
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{resolved_name}/property/Title,MolecularFormula/JSON"
    
    try:
        response = requests.get(url, timeout=10)
        # Enforce rate limit (max 5 requests per second)
        time.sleep(0.25)
        
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
        
    # Store fallback/default in cache to prevent continuous failing requests
    result = {
        "preferred_term": raw_name,
        "pubchem_cid": None,
        "molecular_formula": None
    }
    cache[cache_key] = result
    save_cache(cache)
    return result

def load_unit_mapping(units_file):
    """Loads unit mappings from a CSV file."""
    mapping = {}
    if os.path.exists(units_file):
        try:
            units_df = pd.read_csv(units_file)
            for _, row in units_df.iterrows():
                raw = str(row['raw_unit']).strip().lower().replace(" ", "")
                std = str(row['standard_unit']).strip()
                mapping[raw] = std
            logger.info(f"Loaded {len(mapping)} unit mappings from '{units_file}'.")
        except Exception as e:
            logger.warning(f"Failed to load units mapping from {units_file}: {e}")
    else:
        logger.warning(f"Units mapping file {units_file} does not exist. Using empty mapping.")
    return mapping

def harmonize_unit(val, unit_mapping):
    """
    Normalizes unit strings:
    - Lowercase
    - Strip all spaces
    - Replace synonyms using loaded unit mapping
    """
    if pd.isna(val) or not isinstance(val, str):
        return val
    
    cleaned = val.strip().lower().replace(" ", "")
    return unit_mapping.get(cleaned, cleaned)

def calculate_missing_values(df):
    """Computes missing value stats per column."""
    missing_count = df.isnull().sum()
    missing_pct = (df.isnull().sum() / len(df)) * 100
    missing_df = pd.DataFrame({
        'column': df.columns,
        'missing_count': missing_count,
        'missing_percentage': missing_pct
    })
    return missing_df

def clean_and_validate(input_csv, output_csv, schema_path, units_file, vocabularies_file, reports_dir):
    """
    Pipeline to clean, enrich, handle NaNs, and validate the photocatalysis dataset.
    Generates validation and quality reports.
    """
    if not os.path.exists(input_csv):
        logger.error(f"Input merged CSV file '{input_csv}' not found.")
        return False
        
    df = pd.read_csv(input_csv)
    initial_row_count = len(df)
    logger.info(f"Loaded {initial_row_count} rows from '{input_csv}'")
    
    # Pre-cleaning stats
    pre_missing_stats = calculate_missing_values(df)
    
    # Load mappings
    unit_mapping = load_unit_mapping(units_file)
    vocab_mapping = load_dye_mapping(vocabularies_file)
    
    # Lists for logging reports
    conflicts_log = [] # List of dicts for conflicts.csv
    validation_failures = [] # List of strings for validation_report.md
    
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
        source = row['source']
        if pd.isna(name):
            preferred_terms.append(name)
            cids.append(None)
            formulas.append(None)
            conflicts_log.append({
                "row_index": idx,
                "source": source,
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
                "source": source,
                "field": "dye_name",
                "value": name,
                "error_type": "PubChem Resolution Failure",
                "description": f"Could not resolve dye '{name}' on PubChem REST API"
            })
        
    df['dye_name'] = preferred_terms
    df['pubchem_cid'] = cids
    df['molecular_formula'] = formulas
    logger.info("Enriched and replaced dye_name with preferred term and added pubchem_cid, molecular_formula.")
    
    # 3. NaN Handling
    # Fill Zenodo light_type using Light Condition from source Excel if it is available
    excel_path = 'data/raw/downloaded/zenodo_16640173/LC1_φ_NMs_data.xlsx'
    zenodo_mask = df['source'] == 'zenodo_16640173'
    if os.path.exists(excel_path):
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
            df.loc[df['source'] == 'zenodo_16640173', 'light_type'] = 'UV'
    else:
        df.loc[df['source'] == 'zenodo_16640173', 'light_type'] = 'UV'
        logger.info("Source Excel not found. Set Zenodo light_type to 'UV' default.")
        
    # Fill missing light_type with 'UV' based on source description fallback
    df['light_type'] = df['light_type'].fillna('UV')

    # Re-harmonize in case defaults weren't fully normalized
    for col in unit_cols:
        df[col] = df[col].apply(lambda x: harmonize_unit(x, unit_mapping))
        
    logger.info("NaN Handling completed.")
    
    # 4. Data Validation against schema.json
    if not os.path.exists(schema_path):
        logger.error(f"Schema file '{schema_path}' not found.")
        return False
        
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
    except Exception as e:
        logger.error(f"Failed to parse schema file: {e}")
        return False

    valid_records = []
    invalid_count = 0
    
    for index, row in df.iterrows():
        row_dict = row.to_dict()
        # Convert NaN values to None for JSON schema validation compatibility
        row_clean = {k: (None if pd.isna(v) else v) for k, v in row_dict.items()}
        
        # Validate only properties defined in the schema
        record_to_validate = {k: v for k, v in row_clean.items() if k in schema.get("properties", {})}
        
        try:
            jsonschema.validate(instance=record_to_validate, schema=schema)
            # If valid, append the row (with all columns, including DOI and PubChem info)
            valid_records.append(row_dict)
        except jsonschema.exceptions.ValidationError as e:
            invalid_count += 1
            error_msg = f"Row {index} (source: '{row_clean.get('source')}') failed schema validation: {e.message}"
            validation_failures.append(error_msg)
            logger.error(f"{error_msg} | Row data: {record_to_validate}")
            conflicts_log.append({
                "row_index": index,
                "source": row_clean.get('source'),
                "field": e.path[0] if e.path else "schema",
                "value": str(e.instance),
                "error_type": "Schema Validation Failure",
                "description": e.message
            })
            
    logger.info(f"Validation summary: Valid rows = {len(valid_records)}, Invalid rows = {invalid_count}")
    
    final_valid_records = []
    dropped_pubchem_count = 0
    
    # Write valid rows to output CSV
    if valid_records:
        cleaned_df = pd.DataFrame(valid_records)
        
        # Filter out rows where pubchem_cid is missing/NaN
        initial_len = len(cleaned_df)
        cleaned_df = cleaned_df.dropna(subset=['pubchem_cid'])
        dropped_pubchem_count = initial_len - len(cleaned_df)
        if dropped_pubchem_count > 0:
            logger.warning(f"Dropped {dropped_pubchem_count} rows because their dyes could not be resolved in PubChem.")
            
        if not cleaned_df.empty:
            cleaned_df['pubchem_cid'] = cleaned_df['pubchem_cid'].astype(int)
            
            # Ensure column ordering matches original and puts PubChem fields after dye name (dropping dye_name and molecular_formula)
            cols = [
                'source', 'catalyst_formula', 'pubchem_cid',
                'initial_dye_conc_value', 'initial_dye_conc_unit', 'catalyst_dosage_value', 'catalyst_dosage_unit',
                'light_type', 'time_value', 'time_unit', 'efficiency_value'
            ]
            # Only keep columns that are actually present
            cols = [c for c in cols if c in cleaned_df.columns]
            cleaned_df = cleaned_df[cols]
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(os.path.abspath(output_csv)), exist_ok=True)
            cleaned_df.to_csv(output_csv, index=False)
            logger.success(f"Cleaned, normalized, and validated dataset saved to '{output_csv}'")
            post_missing_stats = calculate_missing_values(cleaned_df)
            final_row_count = len(cleaned_df)
            success = True
        else:
            logger.error("No rows had a valid PubChem CID. Final output file not created.")
            cleaned_df = pd.DataFrame()
            post_missing_stats = pd.DataFrame()
            final_row_count = 0
            success = False
    else:
        logger.error("No rows were valid. Final output file not created.")
        cleaned_df = pd.DataFrame()
        post_missing_stats = pd.DataFrame()
        final_row_count = 0
        success = False

    # Generate Reports
    os.makedirs(reports_dir, exist_ok=True)
    
    # 1. Write conflicts.csv
    conflicts_csv_path = os.path.join(reports_dir, "conflicts.csv")
    try:
        conflicts_df = pd.DataFrame(conflicts_log)
        if conflicts_df.empty:
            # Create empty CSV with headers
            conflicts_df = pd.DataFrame(columns=["row_index", "source", "field", "value", "error_type", "description"])
        conflicts_df.to_csv(conflicts_csv_path, index=False)
        logger.success(f"Saved conflict log to '{conflicts_csv_path}'")
    except Exception as e:
        logger.error(f"Failed to write conflicts CSV: {e}")
        
    # 2. Write missing_values_report.md
    missing_report_path = os.path.join(reports_dir, "missing_values_report.md")
    try:
        with open(missing_report_path, "w", encoding="utf-8") as f_rep:
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
        logger.success(f"Saved missing values report to '{missing_report_path}'")
    except Exception as e:
        logger.error(f"Failed to write missing values report: {e}")

    # 3. Write validation_report.md
    validation_report_path = os.path.join(reports_dir, "validation_report.md")
    try:
        with open(validation_report_path, "w", encoding="utf-8") as f_val:
            f_val.write("# Validation and Standardization Report\n\n")
            f_val.write(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f_val.write("## Summary Metrics\n\n")
            f_val.write(f"- **Input merged records**: {initial_row_count}\n")
            f_val.write(f"- **Schema validation passed**: {len(valid_records)}\n")
            f_val.write(f"- **Schema validation failed (invalid schema)**: {invalid_count}\n")
            f_val.write(f"- **Dropped due to missing PubChem CID**: {dropped_pubchem_count}\n")
            f_val.write(f"- **Final validated records exported**: {final_row_count}\n\n")
            
            f_val.write(f"## Data Schema Information\n")
            f_val.write(f"- Schema source file: `{schema_path}`\n\n")
            
            f_val.write("## Schema Validation Failures\n\n")
            if validation_failures:
                f_val.write(f"Total of {len(validation_failures)} validation failure(s) found:\n\n")
                for fail in validation_failures:
                    f_val.write(f"- {fail}\n")
            else:
                f_val.write("All records passed the JSON schema validation successfully! 🎉\n")
            f_val.write("\n")
            
            f_val.write("## PubChem Name Enrichment and Resolution Failures\n\n")
            pubchem_fails = [c for c in conflicts_log if c["error_type"] == "PubChem Resolution Failure"]
            if pubchem_fails:
                f_val.write(f"Total of {len(pubchem_fails)} dye name(s) could not be resolved on PubChem and were filtered out:\n\n")
                f_val.write("| Row Index | Source | Dye Name | Details |\n")
                f_val.write("| --- | --- | --- | --- |\n")
                for f in pubchem_fails:
                    f_val.write(f"| {f['row_index']} | {f['source']} | {f['value']} | {f['description']} |\n")
            else:
                f_val.write("All dyes were successfully resolved and enriched on PubChem API! 🎉\n")
                
        logger.success(f"Saved validation report to '{validation_report_path}'")
    except Exception as e:
        logger.error(f"Failed to write validation report: {e}")

    return success

if __name__ == "__main__":
    import sys
    import argparse
    from utils.config import get_config_and_argv
    
    config, config_path, remaining_argv = get_config_and_argv()
    pipeline_conf = config.get("pipeline", {})
    clean_conf = config.get("stages", {}).get("clean", {})
    
    # Main parser
    parser = argparse.ArgumentParser(description="Clean, normalize, and validate dataset.")
    parser.add_argument("--config", default="config/default.yaml", help="Path to config file")
    parser.parse_args(remaining_argv)
    
    input_file = clean_conf.get("input_file", "data/interim/merged/merged.csv")
    output_file = clean_conf.get("output_file", "data/processed/final_cleaned_dataset.csv")
    schema_file = pipeline_conf.get("schema_file", "schemas/schema.json")
    cache_file = clean_conf.get("pubchem_cache_file", "data/interim/pubchem_cache.json")
    units_file = clean_conf.get("units_file", "metadata/units.csv")
    vocabularies_file = clean_conf.get("vocabularies_file", "metadata/vocabularies.csv")
    reports_dir = clean_conf.get("reports_dir", "reports")
    
    # Update global CACHE_FILE
    CACHE_FILE = cache_file
    
    success = clean_and_validate(
        input_csv=input_file,
        output_csv=output_file,
        schema_path=schema_file,
        units_file=units_file,
        vocabularies_file=vocabularies_file,
        reports_dir=reports_dir
    )
    if not success:
        sys.exit(1)
