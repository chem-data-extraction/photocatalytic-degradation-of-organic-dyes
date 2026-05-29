#!/usr/bin/env python3
"""
PDF Extraction Driver.
Integrates SI PDF merging, MinerU layout parsing, and Gemini API extraction.
Outputs to data/extracted/pdf_extracted_records.csv and data/extracted/extraction_log.jsonl.
"""

from __future__ import annotations

import os
import sys
import glob
import json
import shutil
import argparse
import time
from datetime import datetime, timezone
from pathlib import Path
from pypdf import PdfWriter
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from utils.logger import get_logger
from utils.env import load_dotenv

logger = get_logger("extract_pdf", "logs/extract.log")

# ==============================================================================
# STAGE 1: Merge Supplementary Information
# ==============================================================================
def merge_si(pdf_dir_path: str, output_pdf_dir_path: str) -> None:
    pdf_dir = Path(pdf_dir_path)
    output_pdf_dir = Path(output_pdf_dir_path)
    
    if not pdf_dir.exists():
        logger.error(f"PDF directory {pdf_dir} does not exist.")
        return
        
    output_pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_files = list(pdf_dir.glob("*.pdf"))
    si_files = [f for f in pdf_files if f.name.lower().endswith("_si.pdf")]
    
    for f in pdf_files:
        if f not in si_files:
            shutil.copy2(f, output_pdf_dir / f.name)
            
    if not si_files:
        logger.info(f"No *_si.pdf files found in {pdf_dir} to merge. Copied all PDFs to {output_pdf_dir}.")
        return

    logger.info(f"Found {len(si_files)} SI file(s). Starting matching and merging into {output_pdf_dir}...\n")
    merged_count = 0

    for si_path in si_files:
        si_name = si_path.name
        base_name = si_name[:-7]
        main_path = pdf_dir / f"{base_name}.pdf"
        
        if not main_path.exists() and base_name[-1].isdigit():
            stripped_base = base_name.rstrip("0123456789")
            main_path = pdf_dir / f"{stripped_base}.pdf"
            
            if not main_path.exists():
                stripped_base_last = base_name[:-1]
                main_path = pdf_dir / f"{stripped_base_last}.pdf"

        if main_path.exists():
            logger.info("Match found:")
            logger.info(f"  Main file: {main_path.name}")
            logger.info(f"  SI file:   {si_path.name}")
            
            dest_merged_path = output_pdf_dir / main_path.name
            writer = PdfWriter()
            
            try:
                writer.append(main_path)
                writer.append(si_path)
                
                with open(dest_merged_path, "wb") as f_out:
                    writer.write(f_out)
                writer.close()
                
                logger.success(f"  Merged {main_path.name} and {si_path.name} -> {dest_merged_path.name}\n")
                merged_count += 1
            except Exception as e:
                logger.error(f"  Failed to merge {main_path.name} and {si_path.name}: {e}\n")
                writer.close()
        else:
            logger.warning(f"Could not find matching main PDF for {si_name}\n")

    logger.success(f"Done! Successfully merged {merged_count} PDF pairs into {output_pdf_dir}.")

# ==============================================================================
# STAGE 2: MinerU PDF Ingestion / Parsing
# ==============================================================================
def cleanup_unused_images(pdf_output_dir: str, md_file_path: str) -> None:
    if not os.path.exists(md_file_path):
        return
        
    content_lists = glob.glob(os.path.join(pdf_output_dir, "*_content_list.json"))
    if not content_lists:
        logger.warning("  No content list found. Skipping chart-only filtering to prevent data loss.")
        return

    chart_images = set()
    try:
        with open(content_lists[0], "r", encoding="utf-8") as f:
            c_list = json.load(f)
        for block in c_list:
            if "img_path" in block:
                name = os.path.basename(block["img_path"])
                if block.get("type") == "chart":
                    chart_images.add(name)
    except Exception as e:
        logger.error(f"      Error reading content list for chart detection: {e}")
        return

    with open(md_file_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    
    import re
    all_referenced = set(re.findall(r"images/([a-f0-9]+\.jpg)", md_content))
    images_to_delete = all_referenced - chart_images

    if images_to_delete:
        original_content = md_content
        for img in images_to_delete:
            pattern = r"!\[.*?\]\(images/" + re.escape(img) + r"\)\s*\n?"
            md_content = re.sub(pattern, "", md_content)
        if md_content != original_content:
            with open(md_file_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            logger.info(f"  Removed {len(images_to_delete)} non-chart references from markdown.")

    images_dir = os.path.join(pdf_output_dir, "images")
    if not os.path.exists(images_dir):
        return
        
    all_images = os.listdir(images_dir)
    deleted_count = 0
    for img in all_images:
        if img not in chart_images:
            try:
                os.remove(os.path.join(images_dir, img))
                deleted_count += 1
            except Exception as e:
                logger.error(f"      Error deleting {img}: {e}")
                
    if deleted_count > 0:
        logger.info(f"  Cleaned up {deleted_count} non-chart images. Kept {len(chart_images)} chart figures.")

def run_ingestion(
    pdf_dir: str,
    ingested_dir: str,
    force: bool,
    extraction_model: str = "vlm",
    enable_formula: bool = True,
    enable_table: bool = True,
    enable_ocr: bool = False,
    ocr_language: str = "en"
) -> None:
    from mineru import MinerU
    
    EXTRACTION_MODEL = extraction_model
    ENABLE_FORMULA = enable_formula
    ENABLE_TABLE = enable_table
    ENABLE_OCR = enable_ocr
    OCR_LANGUAGE = ocr_language
    
    token = os.environ.get("MINERU_TOKEN")
    if not token:
        logger.warning("MINERU_TOKEN environment variable is not set. Running in Flash Mode.")
        client = MinerU()
    else:
        logger.info("MINERU_TOKEN found. Processing in Precision Mode.")
        client = MinerU(token)

    os.makedirs(ingested_dir, exist_ok=True)
    pdf_files = glob.glob(os.path.join(pdf_dir, "*.pdf"))
    
    if not pdf_files:
        logger.error(f"No PDF files found in {pdf_dir}.")
        return

    logger.info(f"Found {len(pdf_files)} PDF(s) to process.\n")

    for pdf_path in pdf_files:
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        pdf_output_dir = os.path.join(ingested_dir, pdf_name)
        md_file_path = os.path.join(pdf_output_dir, f"{pdf_name}.md")

        if not force and os.path.exists(md_file_path):
            logger.info(f"--- Skipping ingestion: {pdf_name}.pdf (Already processed) ---")
            continue

        logger.info(f"--- Ingesting: {pdf_name}.pdf ---")
        try:
            if token:
                result = client.extract(
                    pdf_path,
                    model=EXTRACTION_MODEL,
                    formula=ENABLE_FORMULA,
                    table=ENABLE_TABLE,
                    ocr=ENABLE_OCR,
                    language=OCR_LANGUAGE
                )
            else:
                result = client.flash_extract(pdf_path)
            
            os.makedirs(pdf_output_dir, exist_ok=True)
            result.save_all(pdf_output_dir)
            
            full_md_path = os.path.join(pdf_output_dir, "full.md")
            if os.path.exists(full_md_path):
                if os.path.exists(md_file_path):
                    os.remove(md_file_path)
                os.rename(full_md_path, md_file_path)
                logger.success(f"  Renamed full.md to: {md_file_path}")

            for filename in os.listdir(pdf_output_dir):
                if filename.endswith("_origin.pdf"):
                    try:
                        os.remove(os.path.join(pdf_output_dir, filename))
                    except Exception as e:
                        logger.error(f"  Error deleting redundant PDF copy: {e}")

            cleanup_unused_images(pdf_output_dir, md_file_path)
        except Exception as e:
            logger.error(f"  Error processing {pdf_name}.pdf during ingestion: {e}")

# ==============================================================================
# STAGE 3: Gemini Data Extraction
# ==============================================================================
def clean_schema_for_gemini(schema_dict: dict) -> dict:
    if not isinstance(schema_dict, dict):
        return schema_dict

    new_schema = {}
    for k, v in schema_dict.items():
        if k == "type":
            if isinstance(v, list):
                non_null_types = [t for t in v if t != "null" and t is not None]
                if non_null_types:
                    new_schema["type"] = non_null_types[0].upper()
                new_schema["nullable"] = True
            elif isinstance(v, str):
                new_schema["type"] = v.upper()
            else:
                new_schema["type"] = v
        elif k == "enum" and isinstance(v, list):
            non_null_enum = [val for val in v if val is not None and val != "null"]
            new_schema["enum"] = non_null_enum
            if len(non_null_enum) < len(v):
                new_schema["nullable"] = True
        elif k == "properties" and isinstance(v, dict):
            new_schema["properties"] = {
                prop_name: clean_schema_for_gemini(prop_val)
                for prop_name, prop_val in v.items()
            }
        elif k == "items" and isinstance(v, dict):
            new_schema["items"] = clean_schema_for_gemini(v)
        else:
            new_schema[k] = v
    return new_schema

def build_gemini_schema_from_template(template_schema_path: Path) -> dict:
    with template_schema_path.open(encoding="utf-8") as f:
        temp_schema = json.load(f)
    
    properties = {}
    type_mapping = {
        "string": "string",
        "number": "number",
        "integer": "integer",
        "boolean": "boolean"
    }
    
    # We want to extract all fields except record_id, source_id, dye_pubchem_cid, and molecular_formula
    exclude_fields = {"record_id", "source_id", "dye_pubchem_cid", "molecular_formula"}
    
    for field in temp_schema.get("fields", []):
        name = field["name"]
        if name in exclude_fields:
            continue
            
        field_type = field.get("type", "string")
        schema_type = type_mapping.get(field_type, "string")
        
        prop_schema = {
            "type": [schema_type, "null"] if not field.get("required", False) else schema_type,
            "description": field.get("description", "")
        }
        
        # Manually restore enums for light_type and irradiation_time_unit if not specified in schema
        if name == "light_type":
            prop_schema["enum"] = ["UV", "Visible", "Solar", "LED", "Dark", None]
        elif name == "irradiation_time_unit":
            prop_schema["enum"] = ["min", "hours", "s", None]
            
        properties[name] = prop_schema
        
    obj_schema = {
        "type": "object",
        "properties": properties,
        "required": []
    }
    
    return clean_schema_for_gemini(obj_schema)

def run_extraction(
    ingested_dir: str,
    extracted_dir: str,
    force: bool,
    model_name: str = "gemini-2.5-flash",
    max_retries: int = 5,
    retry_delay: int = 5
) -> None:
    from google import genai
    from google.genai import types
    
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY or GOOGLE_API_KEY not configured. Skipping Gemini extraction.")
        return

    client = genai.Client(api_key=api_key)
    
    schema_path = ROOT / "specs/dataset_schema.json"
    gemini_schema = build_gemini_schema_from_template(schema_path)
    
    article_dirs = [d for d in glob.glob(os.path.join(ingested_dir, "*")) if os.path.isdir(d)]
    os.makedirs(extracted_dir, exist_ok=True)

    for art_dir in article_dirs:
        art_name = os.path.basename(art_dir)
        output_json_path = os.path.join(extracted_dir, f"{art_name}.json")

        if not force and os.path.exists(output_json_path):
            logger.info(f"--- Skipping extraction: {art_name} (Already extracted) ---")
            continue

        logger.info(f"--- Extracting: {art_name} ---")
        md_files = glob.glob(os.path.join(art_dir, "*.md"))
        if not md_files:
            logger.warning(f"  No markdown file found in {art_dir}. Skipping.")
            continue
        
        md_path = md_files[0]
        with open(md_path, "r", encoding="utf-8") as f:
            md_text = f.read()

        images_dir = os.path.join(art_dir, "images")
        image_parts = []
        if os.path.isdir(images_dir):
            img_files = (
                glob.glob(os.path.join(images_dir, "*.jpg")) +
                glob.glob(os.path.join(images_dir, "*.jpeg")) +
                glob.glob(os.path.join(images_dir, "*.png"))
            )
            for img_path in sorted(img_files):
                ext = os.path.splitext(img_path)[1].lower()
                mime_type = "image/png" if ext == ".png" else "image/jpeg"
                try:
                    with open(img_path, "rb") as f_img:
                        img_bytes = f_img.read()
                    part = types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
                    image_parts.append(part)
                except Exception as e:
                    logger.warning(f"  Error reading image {img_path}: {e}")

        contents = [
            "You are a scientific data extraction agent. "
            "Below is a markdown file representing a scientific article and the images (figures/charts/plots) extracted from the article. "
            "Extract the experimental parameters from the text and images to fill the fields in the requested schema.\n"
            "STRICT EXTRACTION GUIDELINES:\n"
            "- Only extract values that are directly, explicitly, and literally stated in the text, tables, or figures. "
            "- Do NOT perform any mathematical calculations or logical derivations (e.g., do not calculate degradation efficiency or catalyst dosage). "
            "- Do NOT convert units of measurement (e.g., do not convert hours to minutes). "
            "- If a parameter is not explicitly mentioned, you must set its value to null, even if it can be easily inferred or calculated from other data.\n"
            "Ensure the output strictly follows the schema format. Do not add any explanatory text or formatting outside the JSON object.\n\n"
            "Markdown content:\n"
            f"{md_text}"
        ]
        contents.extend(image_parts)

        success = False
        curr_delay = retry_delay
        for attempt in range(1, max_retries + 1):
            try:
                genai_config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=gemini_schema,
                    system_instruction=(
                        "You are a precise scientific data extraction bot. Extract experimental data from scientific papers.\n"
                        "CRITICAL RULES:\n"
                        "1. EXPLICIT EXTRACTION ONLY: Extract ONLY values that are directly, explicitly, and literally written in the text, tables, or figures of the article.\n"
                        "2. NO CALCULATIONS OR DERIVATIONS: Do NOT calculate, compute, estimate, or derive any values. If the value is not explicitly written, it does not exist.\n"
                        "3. NO CONVERSIONS: Do NOT convert values or units of measurement. Extract them exactly as written in the text verbatim.\n"
                        "4. STRICT NULLS: If a parameter is not explicitly stated in the source text, tables, or figures, you MUST set its value to null. Never assume, infer, or extrapolate a value."
                    )
                )
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=genai_config
                )
                
                response_text = response.text
                if not response_text:
                    raise ValueError("Received empty response from Gemini.")
                
                structured_data = json.loads(response_text)
                
                if isinstance(structured_data, dict):
                    structured_data["source_id"] = art_name
                elif isinstance(structured_data, list):
                    for item in structured_data:
                        if isinstance(item, dict):
                            item["source_id"] = art_name

                with open(output_json_path, "w", encoding="utf-8") as f_out:
                    json.dump(structured_data, f_out, indent=2, ensure_ascii=False)
                
                logger.success(f"  Saved extracted data to: {output_json_path}")
                success = True
                break
            except Exception as e:
                logger.warning(f"  Gemini call failed on attempt {attempt}/{max_retries}: {e}")
                if attempt < max_retries:
                    time.sleep(curr_delay)
                    curr_delay *= 2
                else:
                    logger.error(f"  All {max_retries} attempts failed to extract data for {art_name}.")
                    sys.exit(1)

# ==============================================================================
# STAGE 4: Consolidate JSONs into pdf_extracted_records.csv & Append Log
# ==============================================================================
def load_schema_columns(schema_path: Path) -> list[str]:
    with schema_path.open(encoding="utf-8") as f:
        schema = json.load(f)
    return [field["name"] for field in schema["fields"]]

def consolidate_records(extracted_dir: str, output_csv: Path, schema_path: Path) -> None:
    json_files = sorted(list(Path(extracted_dir).glob("*.json")))
    columns = load_schema_columns(schema_path)
    
    records = []
    record_counter = 1
    
    for f_path in json_files:
        try:
            with f_path.open(encoding="utf-8") as f:
                data = json.load(f)
            
            # Sub-records list inside JSON or single record object
            sub_records = data if isinstance(data, list) else [data]
            
            for item in sub_records:
                if not isinstance(item, dict):
                    continue
                
                # Make sure we clean NaN-like string keys and build matching fields
                row = {c: None for c in columns}
                row["source_id"] = f_path.stem
                
                # Generate unique record ID
                row["record_id"] = f"rec_photo_pdf_{f_path.stem}_{record_counter:04d}"
                record_counter += 1
                
                for k, v in item.items():
                    if k in row and k not in ("record_id", "source_id"):
                        row[k] = v
                
                records.append(row)
        except Exception as e:
            logger.error(f"Failed to read/parse extracted JSON {f_path.name}: {e}")

    df = pd.DataFrame(records, columns=columns)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)
    logger.success(f"Consolidated {len(df)} records into {output_csv.relative_to(ROOT)}")

def append_log(log_path: Path, status: str, count: int, issue: str | None = None) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "step": "pdf_extraction",
        "source_id": "pdf_manifest",
        "status": status,
        "tool": "extract_pdf.py",
        "output": "data/extracted/pdf_extracted_records.csv",
        "records_extracted": count
    }
    if issue:
        entry["issue"] = issue
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    logger.success(f"Appended log event to {log_path.relative_to(ROOT)}")

# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================
def main() -> None:
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="PDF Extraction Orchestrator.")
    parser.add_argument("--force", action="store_true", help="Force ingestion and extraction.")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Gemini model name.")
    args = parser.parse_args()
    
    # Static paths
    pdf_dir = "data/raw/pdf"
    output_pdf_dir = "data/interim/pdf"
    ingested_dir = "data/interim/ingested"
    extracted_dir = "data/interim/extracted"
    
    logger.info("=== PDF Extraction: Merging SI PDFs ===")
    merge_si(pdf_dir, output_pdf_dir)
    
    # 2. Ingestion
    logger.info("=== PDF Extraction: Running Ingestion ===")
    run_ingestion(output_pdf_dir, ingested_dir, args.force)
    
    # 3. Gemini Extraction
    logger.info("=== PDF Extraction: Running Gemini AI Extraction ===")
    run_extraction(ingested_dir, extracted_dir, args.force, args.model)
    
    # 4. Consolidation
    output_csv = ROOT / "data/extracted/pdf_extracted_records.csv"
    schema_path = ROOT / "specs/dataset_schema.json"
    log_path = ROOT / "data/extracted/extraction_log.jsonl"
    
    logger.info("=== PDF Extraction: Consolidating Records ===")
    consolidate_records(extracted_dir, output_csv, schema_path)
    
    # Get record count
    try:
        df = pd.read_csv(output_csv)
        count = len(df)
    except Exception:
        count = 0
        
    append_log(log_path, "success", count)
    logger.success("PDF Extraction completed successfully!")

if __name__ == "__main__":
    main()
