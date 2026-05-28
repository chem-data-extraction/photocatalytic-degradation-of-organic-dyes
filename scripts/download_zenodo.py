#!/usr/bin/env python3
import os
import sys
import argparse
import requests
import re
import json
import time

def load_dotenv(dotenv_path=".env"):
    if os.path.exists(dotenv_path):
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, val = line.split("=", 1)
                        val = val.strip()
                        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                            val = val[1:-1]
                        os.environ[key.strip()] = val

def parse_args():
    parser = argparse.ArgumentParser(
        description="Clean minimalist script to download tabular datasets from Zenodo."
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        default="photocatalytic degradation dye dataset",
        help="Search query for Zenodo (default: 'photocatalytic degradation dye dataset')"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="data/downloaded",
        help="Directory to save downloaded datasets (default: data/downloaded)"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=10,
        help="Maximum number of records to retrieve (default: 10)"
    )
    parser.add_argument(
        "--filter", "-f",
        type=str,
        choices=["none", "llm", "interactive"],
        default="interactive",
        help="Filtering mode to exclude irrelevant datasets (default: interactive)"
    )
    return parser.parse_args()

def download_file(url, filepath):
    """Downloads a file with a clean console progress bar."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
    except Exception as e:
        print(f"    [ERROR] Failed to connect to download URL: {e}")
        return False

    total_size = int(response.headers.get("content-length", 0))
    block_size = 8192
    downloaded = 0

    try:
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r    Progress: {percent:.1f}% ({downloaded / (1024*1024):.2f}/{total_size / (1024*1024):.2f} MB)", end="", flush=True)
                    else:
                        print(f"\r    Progress: {downloaded / (1024*1024):.2f} MB downloaded", end="", flush=True)
        print()  # New line after progress finishes
        return True
    except Exception as e:
        print(f"\n    [ERROR] Failed writing file {filepath}: {e}")
        # Clean up partial file on failure
        if os.path.exists(filepath):
            os.remove(filepath)
        return False

def check_relevance_llm(title, description, filenames):
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("[WARNING] GEMINI_API_KEY is not set. Cannot run LLM filtering. Bypassing check.")
        return True, "GEMINI_API_KEY not configured."
        
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("[WARNING] google-genai is not installed. Cannot run LLM filtering. Bypassing check.")
        return True, "google-genai package is not installed."
        
    try:
        client = genai.Client(api_key=api_key)
        
        schema = {
            "type": "OBJECT",
            "properties": {
                "relevant": {"type": "BOOLEAN"},
                "reason": {"type": "STRING"}
            },
            "required": ["relevant", "reason"]
        }
        
        prompt = f"""Analyze the Zenodo record metadata below.
Determine if it contains a tabular dataset of experiments on PHOTOCATALYTIC DYE DEGRADATION.
The dataset is relevant ONLY if it contains experimental runs measuring dye degradation over time (e.g., initial dye concentration, catalyst dosage, light type, irradiation time, degradation efficiency).
It is IRRELEVANT if:
- It only contains material characterization raw data (like XRD patterns, Raman spectra, XPS spectra, EPR, BET isotherms) without systematic degradation kinetic tables.
- It is about a different chemical process (e.g. gas degradation, bromodichloromethane removal, biological cell processes) instead of photocatalytic dye degradation.

Metadata:
Title: {title}
Description: {description[:1000]}
Files: {filenames}
"""
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            system_instruction="You are an expert scientific data classifier. Determine if a Zenodo dataset contains tabular photocatalytic dye degradation experimental data."
        )
        
        max_retries = 5
        retry_delay = 5
        for attempt in range(1, max_retries + 1):
            try:
                response = client.models.generate_content(
                    model="gemini-3-flash-preview",
                    contents=prompt,
                    config=config
                )
                res = json.loads(response.text)
                return res.get("relevant", True), res.get("reason", "No reason provided.")
            except Exception as e:
                print(f"[WARNING] LLM relevance check failed on attempt {attempt}/{max_retries}: {e}")
                if attempt < max_retries:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    print(f"[ERROR] All {max_retries} attempts failed for LLM relevance check. Terminating script.")
                    sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Setup or client initialization for LLM relevance check failed: {e}")
        sys.exit(1)

def get_file_preview(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    if ext in ('.xlsx', '.xls', '.ods'):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
            preview = {}
            for sheetname in wb.sheetnames[:8]:  # Limit to 8 sheets
                sheet = wb[sheetname]
                rows = []
                for r_idx, row in enumerate(sheet.iter_rows(values_only=True), 1):
                    if r_idx > 6:  # Read 6 rows
                        break
                    row_vals = [str(val)[:40] if val is not None else "" for val in row]
                    if any(row_vals):
                        rows.append(row_vals)
                if rows:
                    preview[sheetname] = rows
            return preview
        except Exception as e:
            return {"error": f"Failed to parse Excel: {e}"}
    elif ext in ('.csv', '.tsv'):
        delim = '\t' if ext == '.tsv' else ','
        try:
            import csv
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f, delimiter=delim)
                rows = []
                for r_idx, row in enumerate(reader):
                    if r_idx > 6:
                        break
                    rows.append([str(val)[:40] for val in row])
                return {"csv_data": rows}
        except Exception as e:
            return {"error": f"Failed to parse CSV: {e}"}
    return {"error": "Unsupported file format"}

def check_file_content_relevance_llm(filepath, title, description):
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return True, {}, "GEMINI_API_KEY not configured."
        
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return True, {}, "google-genai package is not installed."
        
    preview = get_file_preview(filepath)
    if "error" in preview:
        return True, {}, f"Could not read preview: {preview['error']}"
        
    try:
        client = genai.Client(api_key=api_key)
        
        schema = {
            "type": "OBJECT",
            "properties": {
                "relevant": {"type": "BOOLEAN"},
                "reason": {"type": "STRING"},
                "sheet_name": {"type": "STRING"},
                "column_mapping": {
                    "type": "OBJECT",
                    "properties": {
                        "catalyst_formula": {"type": "STRING", "nullable": True},
                        "dye_name": {"type": "STRING", "nullable": True},
                        "initial_dye_conc_value": {"type": "STRING", "nullable": True},
                        "initial_dye_conc_unit": {"type": "STRING", "nullable": True},
                        "catalyst_dosage_value": {"type": "STRING", "nullable": True},
                        "catalyst_dosage_unit": {"type": "STRING", "nullable": True},
                        "light_type": {"type": "STRING", "nullable": True},
                        "time_value": {"type": "STRING", "nullable": True},
                        "time_unit": {"type": "STRING", "nullable": True},
                        "efficiency_value": {"type": "STRING", "nullable": True}
                    },
                    "required": [
                        "catalyst_formula",
                        "dye_name",
                        "initial_dye_conc_value",
                        "initial_dye_conc_unit",
                        "catalyst_dosage_value",
                        "catalyst_dosage_unit",
                        "light_type",
                        "time_value",
                        "time_unit",
                        "efficiency_value"
                    ]
                }
            },
            "required": ["relevant", "reason"]
        }
        
        prompt = f"""Analyze the content preview of the downloaded file '{os.path.basename(filepath)}'.
This file belongs to the Zenodo record: "{title}"
Description snippet: {description[:500]}

Determine if this file (or one of its sheets) is a clean, flat tabular dataset of photocatalytic dye degradation experiments that is suitable for direct database import according to our schema by applying a column mapping.

A file is SUITABLE (relevant: True) ONLY if:
1. It contains a flat table structure where each row represents a single experimental observation/run, and columns represent distinct variables.
2. It has a clear, unique mapping to our target fields (e.g. one unique column for Time, and one unique column for Degradation Efficiency or Concentration).

A file is UNSUITABLE (relevant: False) and MUST be rejected if:
1. It is a plotting helper sheet with side-by-side repeated columns for different curves (e.g., multiple 'time' and '% removal' columns side-by-side for different catalyst samples).
2. It is dominated by material characterization data (such as XRD patterns, DRS absorbance/reflectance spectra, BET N2 isotherms, FTIR spectra, EPR/XPS intensities, band gap estimation) rather than systematic dye degradation runs over time.
3. It lacks a flat table structure, making it impossible to import via a simple column-to-field mapping.

If the file is SUITABLE, identify the columns that map to the target fields:
- sheet_name: (For Excel files) the sheet name containing the flat table.
- column_mapping: a dictionary mapping each schema field to the corresponding column name in the dataset (or null / constant). Specifically:
  - catalyst_formula: column name for catalyst formula if present.
  - dye_name: column name for dye name if present.
  - initial_dye_conc_value: column name for initial dye concentration value if present.
  - initial_dye_conc_unit: column name for initial dye concentration unit, or a constant like 'mg/L' if not in columns.
  - catalyst_dosage_value: column name for catalyst dosage value if present.
  - catalyst_dosage_unit: column name for catalyst dosage unit, or a constant like 'g/L' if not in columns.
  - light_type: column name for light condition/type if present.
  - time_value: column name containing the time values.
  - time_unit: column name containing the time unit, or a constant like 'min', 'hours', 's' if not in columns.
  - efficiency_value: column name containing degradation efficiency (0-100%) or concentration ratio.

File structure preview (first few rows of each sheet/data):
{json.dumps(preview, indent=2)}
"""
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            system_instruction="You are a strict data validation agent. Determine if a tabular file contains a clean, flat table (not a plotting coordinate sheet with side-by-side repeated columns or raw characterization data) that is suitable for direct database import using column mapping."
        )
        
        max_retries = 5
        retry_delay = 5
        for attempt in range(1, max_retries + 1):
            try:
                response = client.models.generate_content(
                    model="gemini-3.1-flash-lite",
                    contents=prompt,
                    config=config
                )
                res = json.loads(response.text)
                
                is_relevant = res.get("relevant", True)
                reason = res.get("reason", "No reason provided.")
                
                mapping = {}
                if is_relevant:
                    mapping["sheet_name"] = res.get("sheet_name")
                    mapping["column_mapping"] = res.get("column_mapping", {})
                    
                return is_relevant, mapping, reason
            except Exception as e:
                print(f"[WARNING] LLM content relevance check failed on attempt {attempt}/{max_retries}: {e}")
                if attempt < max_retries:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    print(f"[ERROR] All {max_retries} attempts failed for LLM content relevance check. Terminating script.")
                    sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Setup or client initialization for LLM content relevance check failed: {e}")
        sys.exit(1)

def ask_user_interactive(idx, total, record_id, title, description, filenames):
    clean_desc = re.sub(r"<[^>]*>", "", description).strip()
    desc_snippet = clean_desc[:200] + "..." if len(clean_desc) > 200 else clean_desc
    
    print("=" * 60)
    print(f"[{idx}/{total}] Record ID: {record_id}")
    print(f"Title: {title}")
    print(f"Description: {desc_snippet}")
    print(f"Tabular Files: {filenames}")
    print("-" * 60)
    
    while True:
        choice = input("Download this dataset? [y]es / [n]o / [a]ll remaining / [q]uit: ").strip().lower()
        if choice in ("y", "yes"):
            return "y"
        elif choice in ("n", "no"):
            return "n"
        elif choice in ("a", "all"):
            return "a"
        elif choice in ("q", "quit"):
            return "q"
        else:
            print("Invalid choice. Please enter y, n, a, or q.")


def main():
    load_dotenv()
    args = parse_args()
    
    # Target tabular extensions
    allowed_extensions = (".csv", ".xlsx", ".xls", ".tsv", ".ods")
    
    # Zenodo records API endpoint
    api_url = "https://zenodo.org/api/records"
    
    # We restrict the query specifically to resource_type.type:dataset
    # and combine it with the user's search terms.
    search_query = f'resource_type.type:dataset AND ({args.query})'
    
    params = {
        "q": search_query,
        "size": args.limit,
        "status": "published"
    }
    
    print(f"[*] Querying Zenodo API...")
    print(f"[-] Search term: {args.query}")
    print(f"[-] Output directory: {args.output}")
    print(f"[-] Record limit: {args.limit}")
    print(f"[-] Filter: {args.filter}\n")
    
    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Failed to query Zenodo API: {e}")
        sys.exit(1)
        
    results = response.json()
    hits = results.get("hits", {}).get("hits", [])
    
    if not hits:
        print("[!] No records found matching the query.")
        sys.exit(0)
        
    print(f"[+] Found {len(hits)} dataset records. Starting download of tabular files...\n")
    
    os.makedirs(args.output, exist_ok=True)
    
    downloaded_records_count = 0
    downloaded_files_count = 0
    
    for idx, hit in enumerate(hits, 1):
        record_id = hit.get("id")
        metadata = hit.get("metadata", {})
        title = metadata.get("title", "Untitled Dataset")
        
        # Get list of files
        files = hit.get("files", [])
        
        # Filter for tabular files
        tabular_files = [
            f for f in files 
            if f.get("key", "").lower().endswith(allowed_extensions)
        ]
        
        if not tabular_files:
            # Skip record if there are no tabular files
            continue
            
        filenames = [f.get("key", "") for f in tabular_files]
        description = metadata.get("description", "")

        is_relevant = True
        skip_reason = ""
        
        if args.filter == "llm":
            is_relevant, skip_reason = check_relevance_llm(title, description, filenames)
        elif args.filter == "interactive":
            action = ask_user_interactive(idx, len(hits), record_id, title, description, filenames)
            if action == "q":
                print("[*] Exiting download script.")
                break
            elif action == "n":
                is_relevant = False
                skip_reason = "Skipped by user."
            elif action == "a":
                args.filter = "none"
                is_relevant = True
            else:
                is_relevant = True

        if not is_relevant:
            print(f"[{idx}/{len(hits)}] Skipping Record ID: {record_id} - {title[:50]}...")
            print(f"    Reason: {skip_reason}")
            print("-" * 50)
            continue
            
        print(f"[{idx}/{len(hits)}] Processing Record ID: {record_id}")
        print(f"    Title: {title}")
        print(f"    Found {len(tabular_files)} tabular file(s).")
        
        # Create record-specific subdirectory to avoid naming conflicts
        record_dir = os.path.join(args.output, f"zenodo_{record_id}")
        os.makedirs(record_dir, exist_ok=True)
        
        record_has_downloads = False
        downloaded_paths = []
        for f_info in tabular_files:
            filename = f_info.get("key")
            download_url = f_info.get("links", {}).get("self") or f_info.get("links", {}).get("content")
            
            if not filename or not download_url:
                continue
                
            dest_path = os.path.join(record_dir, filename)
            print(f"  -> Downloading {filename}...")
            
            success = download_file(download_url, dest_path)
            if success:
                # Stage 2 validation check on the downloaded file content
                if args.filter == "llm":
                    print(f"  [+] Inspecting file content for relevance...")
                    is_rel, mapping, reason = check_file_content_relevance_llm(dest_path, title, description)
                    if not is_rel:
                        print(f"    [!] File {filename} is IRRELEVANT after content inspection: {reason}")
                        print(f"    [-] Deleting {filename}.")
                        try:
                            os.remove(dest_path)
                        except Exception as e:
                            print(f"    [ERROR] Failed to delete file: {e}")
                        continue
                    else:
                        print(f"    [+] File {filename} is RELEVANT. Reason: {reason}")
                        # Save mapping
                        mapping_path = os.path.join(record_dir, f"{filename}_mapping.json")
                        try:
                            with open(mapping_path, "w", encoding="utf-8") as f_map:
                                json.dump(mapping, f_map, indent=2, ensure_ascii=False)
                            print(f"    [+] Saved column mapping to: {mapping_path}")
                        except Exception as e:
                            print(f"    [WARNING] Failed to save mapping: {e}")
                
                downloaded_paths.append(dest_path)
                downloaded_files_count += 1
                record_has_downloads = True
                
        if record_has_downloads:
            downloaded_records_count += 1
        else:
            # Clean up empty directory if no files were kept
            try:
                os.rmdir(record_dir)
                print(f"  [-] Removed empty directory for record {record_id}")
            except Exception:
                pass
        print("-" * 50)
        
    print(f"\n[+] Completed! Downloaded {downloaded_files_count} files from {downloaded_records_count} datasets.")
    print(f"[+] All files saved under: {os.path.abspath(args.output)}")

if __name__ == "__main__":
    main()
