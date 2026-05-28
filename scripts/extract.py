import os
import glob
import sys
import json
import argparse
import time
from google import genai
from google.genai import types
from utils.logger import get_logger
from utils.env import load_dotenv

logger = get_logger("extract")

def clean_schema_for_gemini(schema_dict):
    """
    Recursively updates the schema to conform to Gemini API JSON Schema requirements:
    1. If 'type' is a list, extract the non-null type, set 'type' to it (uppercase), and set 'nullable' to True.
    2. Convert any string 'type' to uppercase.
    3. If 'enum' contains None (or null), remove it from the enum list, and set 'nullable' to True.
    4. Recursively apply to nested 'properties' and 'items'.
    """
    if not isinstance(schema_dict, dict):
        return schema_dict

    new_schema = {}
    for k, v in schema_dict.items():
        if k == "type":
            if isinstance(v, list):
                # Filter out 'null' / None
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

def main():
    # Load environment variables (such as GEMINI_API_KEY) from .env
    load_dotenv()

    from utils.config import get_config_and_argv
    config, config_path, remaining_argv = get_config_and_argv()
    pipeline_conf = config.get("pipeline", {})
    extract_conf = config.get("stages", {}).get("extract", {})

    parser = argparse.ArgumentParser(description="Extract structured data from ingested articles using Gemini.")
    parser.add_argument(
        "--config",
        default="config/default.yaml",
        help="Path to YAML configuration file."
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        default=extract_conf.get("force", False),
        help="Force re-extraction even if the output JSON file already exists."
    )
    parser.add_argument(
        "--model", "-m",
        default=extract_conf.get("model", "gemini-2.5-flash"),
        help="Gemini model to use for extraction."
    )
    args = parser.parse_args(remaining_argv)

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY or GOOGLE_API_KEY is not set in the environment or .env file.")
        logger.info("Please set it, e.g. export GEMINI_API_KEY='your_api_key' or add it to .env.")
        sys.exit(1)

    # Initialize Gemini client
    client = genai.Client(api_key=api_key)

    # Load schema
    schema_path = pipeline_conf.get("schema_file", "schema.json")
    if not os.path.exists(schema_path):
        logger.error(f"Schema file '{schema_path}' not found in the current directory.")
        sys.exit(1)

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    gemini_schema = clean_schema_for_gemini(schema)

    ingested_dir = extract_conf.get("ingested_dir", "data/ingested")
    if not os.path.isdir(ingested_dir):
        logger.error(f"Directory '{ingested_dir}' not found.")
        sys.exit(1)

    article_dirs = [
        d for d in glob.glob(os.path.join(ingested_dir, "*"))
        if os.path.isdir(d)
    ]

    if not article_dirs:
        logger.error(f"No directories found in {ingested_dir}.")
        sys.exit(1)

    extracted_dir = extract_conf.get("extracted_dir", "data/extracted")
    os.makedirs(extracted_dir, exist_ok=True)

    logger.info(f"Found {len(article_dirs)} article(s) in {ingested_dir} to process.\n")

    for art_dir in article_dirs:
        art_name = os.path.basename(art_dir)
        output_json_path = os.path.join(extracted_dir, f"{art_name}.json")

        if not args.force and os.path.exists(output_json_path):
            logger.info(f"--- Skipping: {art_name} (Already extracted) ---")
            continue

        logger.info(f"--- Processing: {art_name} ---")

        # Find markdown file
        md_files = glob.glob(os.path.join(art_dir, "*.md"))
        if not md_files:
            logger.warning(f"  No markdown file found in {art_dir}. Skipping.")
            continue
        
        md_path = md_files[0]
        logger.info(f"  Found markdown: {os.path.basename(md_path)}")

        # Read markdown content
        with open(md_path, "r", encoding="utf-8") as f:
            md_text = f.read()

        # Find images in images/ directory
        images_dir = os.path.join(art_dir, "images")
        image_parts = []
        if os.path.isdir(images_dir):
            img_files = (
                glob.glob(os.path.join(images_dir, "*.jpg")) +
                glob.glob(os.path.join(images_dir, "*.jpeg")) +
                glob.glob(os.path.join(images_dir, "*.png"))
            )
            logger.info(f"  Found {len(img_files)} image(s) in images/")
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
        else:
            logger.info("  No images/ folder found.")

        # Construct contents list
        contents = [
            "You are a scientific data extraction agent. "
            "Below is a markdown file representing a scientific article and the images (figures/charts/plots) extracted from the article. "
            "Extract the experimental parameters from the text and images to fill the fields in the requested schema. "
            "If a parameter is mentioned in a table or figure, use that information. "
            "Ensure the output strictly follows the schema format. Do not add any explanatory text or formatting outside the JSON object.\n\n"
            "Markdown content:\n"
            f"{md_text}"
        ]
        
        # Add all image parts
        contents.extend(image_parts)

        # Call Gemini
        logger.info("  Sending request to Gemini...")
        max_retries = extract_conf.get("max_retries", 5)
        retry_delay = extract_conf.get("retry_delay", 5)
        success = False
        
        for attempt in range(1, max_retries + 1):
            try:
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=gemini_schema,
                    system_instruction="You are a precise scientific data extraction bot. Extract experimental data from scientific papers."
                )
                response = client.models.generate_content(
                    model=args.model,
                    contents=contents,
                    config=config
                )
                
                response_text = response.text
                if not response_text:
                    raise ValueError("Received empty response from Gemini.")
                
                # Validate response_text is valid JSON
                structured_data = json.loads(response_text)
                
                # Overwrite/set the source field to the article name (ROI)
                if isinstance(structured_data, dict):
                    structured_data["source"] = art_name
                elif isinstance(structured_data, list):
                    for item in structured_data:
                        if isinstance(item, dict):
                            item["source"] = art_name

                with open(output_json_path, "w", encoding="utf-8") as f_out:
                    json.dump(structured_data, f_out, indent=2, ensure_ascii=False)
                
                logger.success(f"  Saved extracted data to: {output_json_path}")
                success = True
                break
                
            except Exception as e:
                logger.warning(f"  Gemini call failed on attempt {attempt}/{max_retries}: {e}")
                if attempt < max_retries:
                    logger.info(f"  Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(f"  All {max_retries} attempts failed to extract data for {art_name}. Terminating script.")
                    sys.exit(1)
        logger.plain("")

    logger.success("Data extraction complete!")

if __name__ == "__main__":
    main()
