import os
import sys
import glob
import json
import csv
import argparse
from pathlib import Path
from utils.logger import get_logger

logger = get_logger("merge_extracted", "logs/merge.log")

def to_float(val):
    import pandas as pd
    if pd.isna(val) or val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def to_str(val):
    import pandas as pd
    if pd.isna(val) or val is None or val == "null" or val == "None":
        return None
    val_str = str(val).strip()
    return val_str if val_str else None

def main():
    from utils.config import get_config_and_argv
    config, config_path, remaining_argv = get_config_and_argv()
    pipeline_conf = config.get("pipeline", {})
    merge_conf = config.get("stages", {}).get("merge", {})

    parser = argparse.ArgumentParser(description="Merge extracted article JSONs and downloaded datasets into a single CSV file.")
    parser.add_argument(
        "--config",
        default="config/default.yaml",
        help="Path to config file."
    )
    args = parser.parse_args(remaining_argv)

    # Set paths strictly from the config file
    input_dir = Path(merge_conf.get("extracted_dir", "data/extracted"))
    downloaded_dir = Path(merge_conf.get("downloaded_dir", "data/downloaded"))
    output_file = Path(merge_conf.get("output_file", "data/merged/merged.csv"))
    schema_file = Path(pipeline_conf.get("schema_file", "schema.json"))

    # Load fieldnames from schema to strictly enforce ordering and properties
    fieldnames = []
    if schema_file.exists():
        try:
            with open(schema_file, "r", encoding="utf-8") as f:
                schema = json.load(f)
                if "properties" in schema:
                    fieldnames = list(schema["properties"].keys())
                    logger.info(f"Loaded {len(fieldnames)} fields from schema '{schema_file}'.")
        except Exception as e:
            logger.error(f"Could not parse schema file '{schema_file}': {e}.")
            sys.exit(1)
    else:
        logger.error(f"Schema file '{schema_file}' does not exist.")
        sys.exit(1)

    records = []

    # 1. Merge extracted PDF JSONs
    if input_dir.exists():
        json_files = sorted(list(input_dir.glob("*.json")))
        logger.info(f"Found {len(json_files)} extracted JSON file(s) in '{input_dir}'.")
        for file_path in json_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                if isinstance(data, dict):
                    data["source"] = file_path.stem
                    records.append(data)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            item["source"] = file_path.stem
                            records.append(item)
                else:
                    logger.warning(f"Skipping '{file_path.name}': JSON content is not a dictionary or list.")
            except Exception as e:
                logger.error(f"Failed to read or parse '{file_path.name}': {e}")
    else:
        logger.warning(f"Extracted PDF input directory '{input_dir}' does not exist.")

    # 2. Merge downloaded datasets using mappings
    if downloaded_dir.exists():
            try:
                import pandas as pd
            except ImportError:
                logger.error("pandas library is required to merge downloaded datasets. Please run in an environment with pandas installed.")
                sys.exit(1)

            mapping_files = sorted(list(downloaded_dir.glob("**/*_mapping.json")))
            logger.info(f"Found {len(mapping_files)} dataset mapping file(s) in '{downloaded_dir}'.")

            for mapping_file in mapping_files:
                logger.info(f"Processing dataset mapping: {mapping_file}")
                # Data file name is mapping file name without '_mapping.json'
                data_file_path = mapping_file.parent / mapping_file.name.replace("_mapping.json", "")
                if not data_file_path.exists():
                    logger.warning(f"Data file {data_file_path} not found for mapping {mapping_file}. Skipping.")
                    continue

                try:
                    with open(mapping_file, "r", encoding="utf-8") as f:
                        mapping = json.load(f)
                except Exception as e:
                    logger.error(f"Failed to read mapping file {mapping_file}: {e}. Skipping.")
                    continue

                sheet_name = mapping.get("sheet_name")
                suffix = data_file_path.suffix.lower()

                try:
                    if suffix in ['.xlsx', '.xls', '.ods']:
                        if sheet_name and sheet_name != "null":
                            df = pd.read_excel(data_file_path, sheet_name=sheet_name)
                        else:
                            df = pd.read_excel(data_file_path)
                    elif suffix in ['.csv', '.tsv']:
                        sep = '\t' if suffix == '.tsv' else ','
                        df = pd.read_csv(data_file_path, sep=sep)
                    else:
                        logger.warning(f"Unsupported file format '{suffix}' for {data_file_path}. Skipping.")
                        continue
                except Exception as e:
                    logger.error(f"Failed to read data file {data_file_path}: {e}. Skipping.")
                    continue

                logger.info(f"Loaded {data_file_path.name} with {len(df)} rows.")

                # Extract mapping dictionary (keys = schema fields, values = dataset columns)
                col_map = mapping.get("column_mapping", {})
                
                # For backwards compatibility with old mapping files
                if "column_mapping" not in mapping:
                    col_map = {
                        "catalyst_formula": mapping.get("catalyst_column"),
                        "dye_name": mapping.get("dye_column"),
                        "initial_dye_conc_value": mapping.get("initial_conc_column"),
                        "catalyst_dosage_value": mapping.get("dosage_column"),
                        "time_value": mapping.get("time_column"),
                        "time_unit": mapping.get("time_unit"),
                        "efficiency_value": mapping.get("efficiency_column")
                    }
                
                # Normalize values in mapping (map string "null" to None)
                col_map = {k: (None if v == "null" else v) for k, v in col_map.items()}

                source = data_file_path.parent.name

                dataset_records_count = 0
                for _, row in df.iterrows():
                    record = {field: None for field in fieldnames}
                    record["source"] = source

                    for field in fieldnames:
                        if field == "source":
                            continue
                            
                        mapped_col = col_map.get(field)
                        if not mapped_col:
                            continue
                            
                        # If the mapped column exists in the dataset, extract its value.
                        # Note: mapped_col must be a string to be a column name.
                        if isinstance(mapped_col, str) and mapped_col in row:
                            val = row[mapped_col]
                            if field.endswith("_value"):
                                record[field] = to_float(val)
                            else:
                                record[field] = to_str(val)
                        else:
                            # If mapped column is not in columns, treat it as a constant value or unit
                            if mapped_col is not None:
                                if field.endswith("_value"):
                                    record[field] = to_float(mapped_col)
                                else:
                                    record[field] = to_str(mapped_col)

                    records.append(record)
                    dataset_records_count += 1
                
                logger.info(f"Extracted {dataset_records_count} records from {data_file_path.name}.")
    else:
        logger.warning(f"Downloaded datasets directory '{downloaded_dir}' does not exist.")

    if not records:
        logger.warning("No valid data records were merged.")
        sys.exit(1)

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Write to CSV strictly using schema properties as columns
    try:
        with open(output_file, "w", encoding="utf-8", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for record in records:
                writer.writerow(record)
        logger.success(f"Merged {len(records)} records into '{output_file}'.")
    except Exception as e:
        logger.error(f"Failed to write CSV file '{output_file}': {e}")

if __name__ == "__main__":
    main()
