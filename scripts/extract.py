import os
import glob
import sys
import json
import argparse
import time
from google import genai
from google.genai import types

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

def main():
    # Load environment variables (such as GEMINI_API_KEY) from .env
    load_dotenv()

    parser = argparse.ArgumentParser(description="Extract structured data from ingested articles using Gemini.")
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-extraction even if the output JSON file already exists."
    )
    parser.add_argument(
        "--model", "-m",
        default="gemini-3-flash-preview",
        help="Gemini model to use for extraction (default: gemini-3.1-flash-lite)."
    )
    args = parser.parse_known_args()[0]

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY or GOOGLE_API_KEY is not set in the environment or .env file.")
        print("Please set it, e.g. export GEMINI_API_KEY='your_api_key' or add it to .env.")
        sys.exit(1)

    # Initialize Gemini client
    client = genai.Client(api_key=api_key)

    # Load schema
    schema_path = "schema.json"
    if not os.path.exists(schema_path):
        print(f"[ERROR] Schema file '{schema_path}' not found in the current directory.")
        sys.exit(1)

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    ingested_dir = "data/ingested"
    if not os.path.isdir(ingested_dir):
        print(f"[ERROR] Directory '{ingested_dir}' not found.")
        sys.exit(1)

    article_dirs = [
        d for d in glob.glob(os.path.join(ingested_dir, "*"))
        if os.path.isdir(d)
    ]

    if not article_dirs:
        print(f"[ERROR] No directories found in {ingested_dir}.")
        sys.exit(1)

    extracted_dir = "data/extracted"
    os.makedirs(extracted_dir, exist_ok=True)

    print(f"Found {len(article_dirs)} article(s) in {ingested_dir} to process.\n")

    for art_dir in article_dirs:
        art_name = os.path.basename(art_dir)
        output_json_path = os.path.join(extracted_dir, f"{art_name}.json")

        if not args.force and os.path.exists(output_json_path):
            print(f"--- Skipping: {art_name} (Already extracted) ---")
            continue

        print(f"--- Processing: {art_name} ---")

        # Find markdown file
        md_files = glob.glob(os.path.join(art_dir, "*.md"))
        if not md_files:
            print(f"  [WARNING] No markdown file found in {art_dir}. Skipping.")
            continue
        
        md_path = md_files[0]
        print(f"  [+] Found markdown: {os.path.basename(md_path)}")

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
            print(f"  [+] Found {len(img_files)} image(s) in images/")
            for img_path in sorted(img_files):
                ext = os.path.splitext(img_path)[1].lower()
                mime_type = "image/png" if ext == ".png" else "image/jpeg"
                try:
                    with open(img_path, "rb") as f_img:
                        img_bytes = f_img.read()
                    part = types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
                    image_parts.append(part)
                except Exception as e:
                    print(f"  [WARNING] Error reading image {img_path}: {e}")
        else:
            print("  [i] No images/ folder found.")

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
        print("  [+] Sending request to Gemini...")
        max_retries = 5
        retry_delay = 5
        success = False
        
        for attempt in range(1, max_retries + 1):
            try:
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
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
                
                with open(output_json_path, "w", encoding="utf-8") as f_out:
                    json.dump(structured_data, f_out, indent=2, ensure_ascii=False)
                
                print(f"  [SUCCESS] Saved extracted data to: {output_json_path}")
                success = True
                break
                
            except Exception as e:
                print(f"  [WARNING] Gemini call failed on attempt {attempt}/{max_retries}: {e}")
                if attempt < max_retries:
                    print(f"  Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    print(f"  [ERROR] All {max_retries} attempts failed to extract data for {art_name}. Terminating script.")
                    sys.exit(1)
        print()

    print("Data extraction complete!")

if __name__ == "__main__":
    main()
