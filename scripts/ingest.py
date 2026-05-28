import os
import glob
import sys
import re
import json
import argparse
from mineru import MinerU

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

def cleanup_unused_images(pdf_output_dir, md_file_path):
    if not os.path.exists(md_file_path):
        return
        
    # 1. Find the content_list.json file
    content_lists = glob.glob(os.path.join(pdf_output_dir, "*_content_list.json"))
    if not content_lists:
        print("  [WARNING] No content list found. Skipping chart-only filtering to prevent data loss.")
        return

    # 2. Identify chart images from content_list.json
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
        print(f"      [x] Error reading content list for chart detection: {e}")
        return

    # 3. Read Markdown content
    with open(md_file_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    
    # 4. Find all image references in markdown and determine which ones to delete
    all_referenced = set(re.findall(r"images/([a-f0-9]+\.jpg)", md_content))
    images_to_delete = all_referenced - chart_images

    # 5. Clean up references to non-chart images in markdown
    if images_to_delete:
        original_content = md_content
        for img in images_to_delete:
            pattern = r"!\[.*?\]\(images/" + re.escape(img) + r"\)\s*\n?"
            md_content = re.sub(pattern, "", md_content)
        if md_content != original_content:
            with open(md_file_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            print(f"  [-] Removed {len(images_to_delete)} non-chart references from markdown.")

    # 6. Delete non-chart files from images/ folder
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
                print(f"      [x] Error deleting {img}: {e}")
                
    if deleted_count > 0:
        print(f"  [-] Cleaned up {deleted_count} non-chart images. Kept {len(chart_images)} chart figures.")

def main():
    # Load environment variables from .env file
    load_dotenv()

    # Parse command line arguments (skips already processed PDFs by default)
    parser = argparse.ArgumentParser(description="Extract content from PDFs using MinerU.")
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-extraction even if the output markdown file already exists."
    )
    args, unknown = parser.parse_known_args()
    skip_existing = not args.force

    # Configurable extraction parameters for Precision Mode
    EXTRACTION_MODEL = "vlm"      # Choices: "vlm", "pipeline"
    ENABLE_FORMULA = True        # Enable equation/formula recognition (LaTeX)
    ENABLE_TABLE = True          # Enable table structure recognition
    ENABLE_OCR = False            # Force OCR for scanned documents
    OCR_LANGUAGE = "en"          # OCR language ("en", "zh", "auto", etc.)
    
    # 1. Check API token
    token = os.environ.get("MINERU_TOKEN")
    if not token:
        print("[WARNING] MINERU_TOKEN environment variable is not set.")
        print("For high-precision extraction (including tables, figures, formulas), please set it:")
        print("  export MINERU_TOKEN='your_api_token' or place it in a .env file.")
        print("Proceeding in Flash (free/limited) mode...\n")
        client = MinerU()
    else:
        print("[INFO] MINERU_TOKEN found. Processing in Precision Mode (high-precision VLM + OCR).")
        client = MinerU(token)

    pdf_dir = "data/pdf"
    ingested_dir = "data/ingested"

    # Ensure output directory exists
    os.makedirs(ingested_dir, exist_ok=True)

    # Find all PDF files in data/pdf
    pdf_files = glob.glob(os.path.join(pdf_dir, "*.pdf"))
    
    if not pdf_files:
        print(f"[ERROR] No PDF files found in {pdf_dir}.")
        print("Please place your PDF files in that folder and run the script again.")
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDF(s) to process.\n")

    for pdf_path in pdf_files:
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        
        pdf_output_dir = os.path.join(ingested_dir, pdf_name)
        md_file_path = os.path.join(pdf_output_dir, f"{pdf_name}.md")

        if skip_existing and os.path.exists(md_file_path):
            print(f"--- Skipping: {pdf_name}.pdf (Already processed) ---")
            print(f"  [INFO] Found existing output markdown at: {md_file_path}\n")
            continue

        print(f"--- Processing: {pdf_name}.pdf ---")
        
        try:
            # 2. Perform Extraction
            if token:
                # Precision Mode with explicit parameters
                result = client.extract(
                    pdf_path,
                    model=EXTRACTION_MODEL,
                    formula=ENABLE_FORMULA,
                    table=ENABLE_TABLE,
                    ocr=ENABLE_OCR,
                    language=OCR_LANGUAGE
                )
            else:
                # Flash Mode (lightweight preview)
                result = client.flash_extract(pdf_path)
            
            # Ensure output directory for this specific PDF exists
            os.makedirs(pdf_output_dir, exist_ok=True)

            # 3. Save all resources (including model.json, layout.json, pdf, etc.)
            # Extracting directly into pdf_output_dir
            result.save_all(pdf_output_dir)
            print(f"  [+] Saved figures and assets to: {pdf_output_dir}")

            # 4. Rename full.md to {pdf_name}.md to avoid duplicate Markdown files
            full_md_path = os.path.join(pdf_output_dir, "full.md")
            if os.path.exists(full_md_path):
                if os.path.exists(md_file_path):
                    os.remove(md_file_path)
                os.rename(full_md_path, md_file_path)
                print(f"  [+] Renamed full.md to: {md_file_path}")

            # 5. Clean up redundant origin PDF file (we already have it in data/pdf)
            for filename in os.listdir(pdf_output_dir):
                if filename.endswith("_origin.pdf"):
                    try:
                        os.remove(os.path.join(pdf_output_dir, filename))
                        print(f"  [-] Removed redundant PDF copy: {filename}")
                    except Exception as e:
                        print(f"  [x] Error deleting redundant PDF: {e}")

            # 6. Clean up images folder (keep only referenced figures)
            cleanup_unused_images(pdf_output_dir, md_file_path)
            
        except Exception as e:
            print(f"  [x] Error processing {pdf_name}.pdf: {e}")
        print()

    print("Processing complete!")

if __name__ == "__main__":
    main()
