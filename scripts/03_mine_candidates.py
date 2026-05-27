#!/usr/bin/env python3
"""Stage 3: Mine candidate snippets from text and structure initial records."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import helpers

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", default=str(helpers.DEFAULT_SOURCES_CSV))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()

def candidate_to_prefill(candidate: dict[str, object], source_row: pd.Series, index: int) -> dict[str, str]:
    fields = {column: "" for column in helpers.EXPERIMENT_COLUMNS}
    fields.update(
        {
            "experiment_id": f"{candidate['source_id']}-CAND-{index:04d}",
            "source_id": str(candidate["source_id"]),
            "doi_or_url": str(source_row.get("doi_or_url", "")),
            "paper_title": str(source_row.get("title", "")),
            "publication_year": str(source_row.get("publication_year", "")),
            "source_location": str(candidate["source_location"]),
            "value_origin": "text",
            "extraction_confidence": str(candidate["confidence"]),
            "extraction_notes": str(candidate["snippet"])[:500],
            "manual_review_required": "true",
        }
    )
    return fields

def main() -> int:
    args = parse_args()
    helpers.setup_logging(args.verbose)
    helpers.ensure_directories()

    sources_path = Path(args.sources)
    if not sources_path.is_absolute():
        sources_path = helpers.PROJECT_ROOT / sources_path

    sources = helpers.read_csv_or_empty(sources_path, helpers.SOURCE_COLUMNS)
    all_prefill: list[dict[str, str]] = []
    excluded_rows: list[dict[str, str]] = []
    total_candidates = 0

    for _, row in sources.iterrows():
        source_id = row["source_id"]
        pages_path = helpers.INTERMEDIATE_JSON_DIR / f"{source_id}_pages.json"
        candidates: list[dict[str, object]] = []
        
        if pages_path.exists():
            pages = helpers.read_json(pages_path)
            for page in pages:
                candidates.extend(helpers.mine_page_candidates(source_id, int(page["page_number"]), str(page.get("text", ""))))
                
        helpers.write_json(candidates, helpers.INTERMEDIATE_JSON_DIR / f"{source_id}_candidate_snippets.json", overwrite=True)
        
        for idx, candidate in enumerate(candidates, start=1):
            reason = helpers.exclusion_reason(str(candidate["snippet"]))
            if reason:
                excluded_rows.append(
                    {
                        "excluded_id": f"{source_id}-EXCL-{idx:04d}",
                        "source_id": source_id,
                        "source_location": str(candidate["source_location"]),
                        "candidate_description": str(candidate["snippet"])[:500],
                        "exclusion_reason": reason,
                        "notes": "Auto-flagged by exclusion keyword; verify manually.",
                    }
                )
            else:
                all_prefill.append(candidate_to_prefill(candidate, row, idx))
        total_candidates += len(candidates)

    helpers.write_csv(pd.DataFrame(all_prefill, columns=helpers.EXPERIMENT_COLUMNS), helpers.EXPERIMENT_RECORDS_CSV)
    helpers.write_csv(pd.DataFrame(excluded_rows, columns=helpers.EXCLUDED_COLUMNS), helpers.EXCLUDED_RECORDS_CSV)

    print(f"Candidate snippets mined: {total_candidates}")
    print(f"Candidate record rows written for manual review: {len(all_prefill)}")
    print(f"Excluded candidate rows: {len(excluded_rows)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
