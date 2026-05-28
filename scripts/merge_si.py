import os
import shutil
import argparse
from pathlib import Path
from pypdf import PdfWriter
from utils.logger import get_logger
from utils.config import load_config

logger = get_logger("merge_si", "logs/merge.log")

def merge_si(pdf_dir_path="data/raw/pdf", output_pdf_dir_path="data/interim/pdf"):
    pdf_dir = Path(pdf_dir_path)
    output_pdf_dir = Path(output_pdf_dir_path)
    
    if not pdf_dir.exists():
        logger.error(f"PDF directory {pdf_dir} does not exist.")
        return
        
    output_pdf_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all files in raw/pdf
    pdf_files = list(pdf_dir.glob("*.pdf"))
    
    # Filter SI files
    si_files = [f for f in pdf_files if f.name.lower().endswith("_si.pdf")]
    
    # Copy all non-SI PDFs to output_pdf_dir first
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
        # Strip '_si.pdf'
        base_name = si_name[:-7]
        
        # Try matching base name directly (e.g., ao3c07326_si.pdf -> ao3c07326.pdf)
        main_path = pdf_dir / f"{base_name}.pdf"
        
        # If not found, try fuzzy match by stripping numbers at the end of the base name
        # (e.g., d6na00104a1_si.pdf -> d6na00104a.pdf)
        if not main_path.exists() and base_name[-1].isdigit():
            # Try stripping all ending digits
            stripped_base = base_name.rstrip("0123456789")
            main_path = pdf_dir / f"{stripped_base}.pdf"
            
            # If still not found, try stripping just the last digit
            if not main_path.exists():
                stripped_base_last = base_name[:-1]
                main_path = pdf_dir / f"{stripped_base_last}.pdf"

        if main_path.exists():
            logger.info("Match found:")
            logger.info(f"  Main file: {main_path.name}")
            logger.info(f"  SI file:   {si_path.name}")
            
            # Destination merged file path
            dest_merged_path = output_pdf_dir / main_path.name
            writer = PdfWriter()
            
            try:
                # Append main then SI using original raw files
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

if __name__ == "__main__":
    from utils.config import get_config_and_argv
    config, config_path, remaining_argv = get_config_and_argv()
    
    parser = argparse.ArgumentParser(description="Merge SI PDF files.")
    parser.add_argument("--config", default="config/default.yaml", help="Path to config file")
    parser.parse_args(remaining_argv)
    
    pdf_dir = config.get("stages", {}).get("merge_si", {}).get("pdf_dir", "data/raw/pdf")
    output_pdf_dir = config.get("stages", {}).get("merge_si", {}).get("output_pdf_dir", "data/interim/pdf")
    
    merge_si(pdf_dir, output_pdf_dir)

