#!/usr/bin/env python3
"""Run the simplified Practice 3 pipeline stages in order."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", default="sources_pdf_selected.csv")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--no-network", action="store_true")
    return parser.parse_args()

def run(script: str, *args: str) -> None:
    cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / script), *args]
    print(f"\n>>> Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)

def main() -> int:
    args = parse_args()

    # Step 1: Acquire and Validate
    step1_args = ["--manifest", "inputs/practice3_source_manifest.csv"]
    if args.overwrite:
        step1_args.append("--overwrite")
    if args.no_network:
        step1_args.append("--no-network")
    run("01_acquire_and_validate.py", *step1_args)

    # Step 2: Extract Content
    step2_args = ["--sources", args.sources]
    if args.overwrite:
        step2_args.append("--overwrite")
    run("02_extract_content.py", *step2_args)

    # Step 3: Mine Candidates
    step3_args = ["--sources", args.sources]
    if args.overwrite:
        step3_args.append("--overwrite")
    run("03_mine_candidates.py", *step3_args)

    # Step 4: Build Workbook
    run("04_build_workbook.py")

    # Step 5: Validate and Report
    run("05_validate_and_report.py", "--records", "extracted_experiment_records.csv")

    print("\n>>> Pipeline execution completed successfully!")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
