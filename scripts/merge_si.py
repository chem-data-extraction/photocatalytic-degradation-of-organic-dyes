import os
import argparse
from pathlib import Path
from pypdf import PdfWriter
from utils.logger import get_logger
from utils.config import load_config

logger = get_logger("merge_si", "logs/merge.log")

def merge_si(pdf_dir_path="data/pdf"):
    pdf_dir = Path(pdf_dir_path)
    
    if not pdf_dir.exists():
        logger.error(f"PDF directory {pdf_dir} does not exist.")
        return
        
    # Find all files in data/pdf
    pdf_files = list(pdf_dir.glob("*.pdf"))
    
    # Filter SI files
    si_files = [f for f in pdf_files if f.name.lower().endswith("_si.pdf")]
    
    if not si_files:
        logger.warning(f"No *_si.pdf files found in {pdf_dir} to merge.")
        return

    logger.info(f"Found {len(si_files)} SI file(s). Starting matching and merging...\n")
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
            
            # Perform merging
            writer = PdfWriter()
            temp_merged_path = pdf_dir / f"temp_{main_path.name}"
            
            try:
                # Append main then SI using original files
                writer.append(main_path)
                writer.append(si_path)
                
                with open(temp_merged_path, "wb") as f_out:
                    writer.write(f_out)
                writer.close()
                
                # Replace the main PDF with the merged one
                temp_merged_path.replace(main_path)
                
                # Delete the original SI PDF from the main directory so it is not processed
                si_path.unlink()
                
                logger.success(f"  Merged {main_path.name} and {si_path.name} -> {main_path.name}\n")
                merged_count += 1
            except Exception as e:
                logger.error(f"  Failed to merge {main_path.name} and {si_path.name}: {e}\n")
                if temp_merged_path.exists():
                    temp_merged_path.unlink()
                writer.close()
        else:
            logger.warning(f"Could not find matching main PDF for {si_name}\n")

    logger.success(f"Done! Successfully merged {merged_count} PDF pairs.")

if __name__ == "__main__":
    from utils.config import get_config_and_argv
    config, config_path, remaining_argv = get_config_and_argv()
    
    parser = argparse.ArgumentParser(description="Merge SI PDF files.")
    parser.add_argument("--config", default="config/default.yaml", help="Path to config file")
    parser.parse_args(remaining_argv)
    
    pdf_dir = config.get("stages", {}).get("merge_si", {}).get("pdf_dir", "data/pdf")
    
    merge_si(pdf_dir)

