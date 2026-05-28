import os
import shutil
from pathlib import Path
from pypdf import PdfWriter

def merge_si():
    pdf_dir = Path("data/pdf")
    backup_dir = pdf_dir / "backup"
    
    # Ensure backup directory exists
    backup_dir.mkdir(exist_ok=True)
    
    # Find all files in data/pdf
    pdf_files = list(pdf_dir.glob("*.pdf"))
    
    # Filter SI files
    si_files = [f for f in pdf_files if f.name.lower().endswith("_si.pdf")]
    
    if not si_files:
        print("No *_si.pdf files found in data/pdf to merge.")
        return

    print(f"Found {len(si_files)} SI file(s). Starting matching and merging...\n")
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
            print(f"Match found:")
            print(f"  Main file: {main_path.name}")
            print(f"  SI file:   {si_path.name}")
            
            # Back up original files to backup directory
            backup_main = backup_dir / main_path.name
            backup_si = backup_dir / si_path.name
            
            # Only backup if not already backed up to preserve the true originals
            if not backup_main.exists():
                shutil.copy2(main_path, backup_main)
                print(f"  [+] Backed up original {main_path.name} to {backup_dir}")
            else:
                print(f"  [i] Backup of {main_path.name} already exists.")
                
            if not backup_si.exists():
                shutil.copy2(si_path, backup_si)
                print(f"  [+] Backed up original {si_path.name} to {backup_dir}")
            else:
                print(f"  [i] Backup of {si_path.name} already exists.")
            
            # Perform merging
            writer = PdfWriter()
            temp_merged_path = pdf_dir / f"temp_{main_path.name}"
            
            try:
                # Append main then SI using original (or backup) files
                writer.append(main_path)
                writer.append(si_path)
                
                with open(temp_merged_path, "wb") as f_out:
                    writer.write(f_out)
                writer.close()
                
                # Replace the main PDF with the merged one
                temp_merged_path.replace(main_path)
                
                # Delete the original SI PDF from the main directory so it is not processed
                si_path.unlink()
                
                print(f"  [SUCCESS] Merged {main_path.name} and {si_path.name} -> {main_path.name}\n")
                merged_count += 1
            except Exception as e:
                print(f"  [ERROR] Failed to merge {main_path.name} and {si_path.name}: {e}\n")
                if temp_merged_path.exists():
                    temp_merged_path.unlink()
                writer.close()
        else:
            print(f"[WARNING] Could not find matching main PDF for {si_name}\n")

    print(f"Done! Successfully merged {merged_count} PDF pairs.")

if __name__ == "__main__":
    merge_si()
