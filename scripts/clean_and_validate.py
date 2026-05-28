#!/usr/bin/env python3
"""
Photocatalysis Dataset Cleaning, Normalization, and Validation Script.
Created for: ITMO Photocatalysis Project
"""

import os
import json
import time
from utils.logger import get_logger
import requests
import jsonschema
import pandas as pd

logger = get_logger("clean_and_validate", "logs/cleaning.log")

CACHE_FILE = "data/pubchem_cache.json"

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

def resolve_dye_name(name):
    """Maps common abbreviations to official names for better PubChem API query success."""
    n = name.strip().lower()
    mapping = {
        'rhb': 'rhodamine b',
        'mb': 'methylene blue',
        'mo': 'methyl orange'
    }
    return mapping.get(n, name.strip())

def enrich_dye_info(raw_name, cache):
    """
    Enriches dye name using PubChem REST API.
    Returns preferred term, CID, and molecular formula.
    """
    resolved_name = resolve_dye_name(raw_name)
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

def harmonize_unit(val):
    """
    Normalizes unit strings:
    - Lowercase
    - Strip all spaces
    - Replace 'mg L-1', 'ppm', 'mg/l' synonyms with 'mg/L' strictly.
    """
    if pd.isna(val) or not isinstance(val, str):
        return val
    
    cleaned = val.strip().lower().replace(" ", "")
    
    # Specific synonym replacement to strict string 'mg/L'
    synonyms = {
        'mgl-1': 'mg/L',
        'ppm': 'mg/L',
        'mg/l': 'mg/L'
    }
    return synonyms.get(cleaned, cleaned)

def clean_and_validate(input_csv, output_csv, schema_path):
    """
    Pipeline to clean, enrich, handle NaNs, and validate the photocatalysis dataset.
    """
    if not os.path.exists(input_csv):
        logger.error(f"Input merged CSV file '{input_csv}' not found.")
        return False
        
    df = pd.read_csv(input_csv)
    logger.info(f"Loaded {len(df)} rows from '{input_csv}'")
    
    # 1. Unit Harmonization
    unit_cols = [col for col in df.columns if col.endswith('_unit')]
    for col in unit_cols:
        df[col] = df[col].apply(harmonize_unit)
    logger.info(f"Harmonized unit columns: {unit_cols}")
    
    # 2. Data Enrichment via PubChem API
    cache = load_cache()
    preferred_terms = []
    cids = []
    formulas = []
    
    for name in df['dye_name']:
        info = enrich_dye_info(name, cache)
        preferred_terms.append(info["preferred_term"])
        cids.append(info["pubchem_cid"])
        formulas.append(info["molecular_formula"])
        
    df['dye_name'] = preferred_terms
    df['pubchem_cid'] = cids
    df['molecular_formula'] = formulas
    logger.info("Enriched and replaced dye_name with preferred term and added pubchem_cid, molecular_formula.")
    
    # 3. NaN Handling
    # Fill Zenodo light_type using Light Condition from source Excel if it is available
    excel_path = 'data/downloaded/zenodo_16640173/LC1_φ_NMs_data.xlsx'
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
        df[col] = df[col].apply(harmonize_unit)
        
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
            logger.error(f"Row {index} failed schema validation: {e.message} | Row data: {record_to_validate}")
            
    logger.info(f"Validation summary: Valid rows = {len(valid_records)}, Invalid rows = {invalid_count}")
    
    # Write valid rows to output CSV
    if valid_records:
        cleaned_df = pd.DataFrame(valid_records)
        
        # Filter out rows where pubchem_cid is missing/NaN
        initial_len = len(cleaned_df)
        cleaned_df = cleaned_df.dropna(subset=['pubchem_cid'])
        dropped_len = initial_len - len(cleaned_df)
        if dropped_len > 0:
            logger.warning(f"Dropped {dropped_len} rows because their dyes could not be resolved in PubChem.")
            
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
            return True
        else:
            logger.error("No rows had a valid PubChem CID. Final output file not created.")
            return False
    else:
        logger.error("No rows were valid. Final output file not created.")
        return False

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
    
    input_file = clean_conf.get("input_file", "data/merged/merged.csv")
    output_file = clean_conf.get("output_file", "data/final_dataset.csv")
    schema_file = pipeline_conf.get("schema_file", "schema.json")
    cache_file = clean_conf.get("pubchem_cache_file", "data/pubchem_cache.json")
    
    # Update global CACHE_FILE
    CACHE_FILE = cache_file
    
    success = clean_and_validate(input_file, output_file, schema_file)
    if not success:
        sys.exit(1)
