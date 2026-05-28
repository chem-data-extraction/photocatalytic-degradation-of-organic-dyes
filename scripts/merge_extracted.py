import os
import glob
import json
import csv
import argparse
from pathlib import Path

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
    parser = argparse.ArgumentParser(description="Merge extracted article JSONs and downloaded datasets into a single CSV file.")
    parser.add_argument(
        "--input-dir", "-i",
        default="data/extracted",
        help="Directory containing extracted JSON files from PDFs (default: data/extracted)"
    )
    parser.add_argument(
        "--downloaded-dir", "-d",
        default="data/downloaded",
        help="Directory containing downloaded Zenodo datasets (default: data/downloaded)"
    )
    parser.add_argument(
        "--output-file", "-o",
        default="data/merged/articles.csv",
        help="Path to the output CSV file (default: data/merged/merged.csv)"
    )
    parser.add_argument(
        "--schema-file", "-s",
        default="schema.json",
        help="Path to the schema JSON file to extract field order (default: schema.json)"
    )
    parser.add_argument(
        "--no-extracted",
        action="store_true",
        help="Skip merging extracted PDF JSON files"
    )
    parser.add_argument(
        "--no-downloaded",
        action="store_true",
        help="Skip merging downloaded datasets"
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    downloaded_dir = Path(args.downloaded_dir)
    output_file = Path(args.output_file)
    schema_file = Path(args.schema_file)

    # Load fieldnames from schema to strictly enforce ordering and properties
    fieldnames = []
    if schema_file.exists():
        try:
            with open(schema_file, "r", encoding="utf-8") as f:
                schema = json.load(f)
                if "properties" in schema:
                    fieldnames = list(schema["properties"].keys())
                    print(f"Loaded {len(fieldnames)} fields from schema '{schema_file}'.")
        except Exception as e:
            print(f"[ERROR] Could not parse schema file '{schema_file}': {e}.")
            return
    else:
        print(f"[ERROR] Schema file '{schema_file}' does not exist.")
        return

    records = []

    # 1. Merge extracted PDF JSONs
    if not args.no_extracted:
        if input_dir.exists():
            json_files = sorted(list(input_dir.glob("*.json")))
            print(f"Found {len(json_files)} extracted JSON file(s) in '{input_dir}'.")
            for file_path in json_files:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        
                    if isinstance(data, dict):
                        records.append(data)
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                records.append(item)
                    else:
                        print(f"[WARNING] Skipping '{file_path.name}': JSON content is not a dictionary or list.")
                except Exception as e:
                    print(f"[ERROR] Failed to read or parse '{file_path.name}': {e}")
        else:
            print(f"[WARNING] Extracted PDF input directory '{input_dir}' does not exist.")

    # 2. Merge downloaded datasets using mappings
    if not args.no_downloaded:
        if downloaded_dir.exists():
            try:
                import pandas as pd
            except ImportError:
                print("[ERROR] pandas library is required to merge downloaded datasets. Please run in an environment with pandas installed.")
                return

            mapping_files = sorted(list(downloaded_dir.glob("**/*_mapping.json")))
            print(f"Found {len(mapping_files)} dataset mapping file(s) in '{downloaded_dir}'.")

            for mapping_file in mapping_files:
                print(f"Processing dataset mapping: {mapping_file}")
                # Data file name is mapping file name without '_mapping.json'
                data_file_path = mapping_file.parent / mapping_file.name.replace("_mapping.json", "")
                if not data_file_path.exists():
                    print(f"[WARNING] Data file {data_file_path} not found for mapping {mapping_file}. Skipping.")
                    continue

                try:
                    with open(mapping_file, "r", encoding="utf-8") as f:
                        mapping = json.load(f)
                except Exception as e:
                    print(f"[ERROR] Failed to read mapping file {mapping_file}: {e}. Skipping.")
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
                        print(f"[WARNING] Unsupported file format '{suffix}' for {data_file_path}. Skipping.")
                        continue
                except Exception as e:
                    print(f"[ERROR] Failed to read data file {data_file_path}: {e}. Skipping.")
                    continue

                print(f"Loaded {data_file_path.name} with {len(df)} rows.")

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

                source_doi = data_file_path.parent.name

                dataset_records_count = 0
                for _, row in df.iterrows():
                    record = {field: None for field in fieldnames}
                    record["source_doi"] = source_doi

                    for field in fieldnames:
                        if field == "source_doi":
                            continue
                            
                        mapped_col = col_map.get(field)
                        if not mapped_col:
                            continue
                            
                        # If the mapped column exists in the dataset, extract its value
                        if mapped_col in row:
                            val = row[mapped_col]
                            if field.endswith("_value"):
                                record[field] = to_float(val)
                            else:
                                record[field] = to_str(val)
                        else:
                            # If mapped column is not in columns, check if it's a constant
                            # Constants are typically non-value fields (e.g. units like "min" or "mg/L")
                            if not field.endswith("_value"):
                                record[field] = to_str(mapped_col)

                    records.append(record)
                    dataset_records_count += 1
                
                print(f"Extracted {dataset_records_count} records from {data_file_path.name}.")
        else:
            print(f"[WARNING] Downloaded datasets directory '{downloaded_dir}' does not exist.")

    if not records:
        print("[WARNING] No valid data records were merged.")
        return

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Write to CSV strictly using schema properties as columns
    try:
        with open(output_file, "w", encoding="utf-8", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for record in records:
                writer.writerow(record)
        print(f"[SUCCESS] Merged {len(records)} records into '{output_file}'.")
    except Exception as e:
        print(f"[ERROR] Failed to write CSV file '{output_file}': {e}")

if __name__ == "__main__":
    main()
