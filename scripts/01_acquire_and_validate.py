#!/usr/bin/env python3
"""Stage 1: Acquire source documents and validate the input inventory."""

from __future__ import annotations

import argparse
import sys
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import helpers

USER_AGENT = "Practice3PDFExtraction/0.1 (+manual-acquisition-fallback)"

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(helpers.PRACTICE3_SOURCE_MANIFEST_CSV))
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--no-network", action="store_true", help="Create manifests/queues without HTTP requests.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when required inventory checks fail.")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()

def ensure_reference_files() -> None:
    if not helpers.PRACTICE1_SCHEMA_MD.exists():
        lines = ["# Practice 1 Schema Reference", "", "One record = one independent photocatalytic degradation experiment for one organic dye under one fixed set of conditions.", "", "## Fields", ""]
        lines.extend(f"- {column}" for column in helpers.EXPERIMENT_COLUMNS)
        helpers.write_text("\n".join(lines), helpers.PRACTICE1_SCHEMA_MD, overwrite=False)
    if not helpers.PRACTICE2_SOURCE_MAP_MD.exists():
        helpers.write_text("# Practice 2 Source Map\n\nSelected Practice 3 sources are represented in `inputs/practice3_source_manifest.csv`.\n", helpers.PRACTICE2_SOURCE_MAP_MD, overwrite=False)

def write_yaml_configs() -> None:
    schema_yaml = "experiment_record_fields:\n" + "\n".join(f"  - {column}" for column in helpers.EXPERIMENT_COLUMNS) + "\n"
    vocab_lines = ["controlled_vocabularies:"]
    for name, values in helpers.CONTROLLED_VOCABS.items():
        vocab_lines.append(f"  {name}:")
        vocab_lines.extend(f"    - {value}" for value in sorted(values))
    helpers.write_text(schema_yaml, helpers.CONFIG_DIR / "schema_fields.yaml", overwrite=True)
    helpers.write_text("\n".join(vocab_lines) + "\n", helpers.CONFIG_DIR / "controlled_vocabularies.yaml", overwrite=True)

def ensure_manifest(path: Path, overwrite: bool) -> pd.DataFrame:
    if path.exists() and not overwrite:
        return helpers.read_csv_or_empty(path, helpers.MANIFEST_COLUMNS)
    df = pd.DataFrame(helpers.default_manifest_rows(), columns=helpers.MANIFEST_COLUMNS)
    helpers.write_csv(df, path)
    return df

def http_get(url: str, timeout: int) -> requests.Response:
    return requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})

def reason_from_status(status: int) -> str:
    if status == 403:
        return "http_403"
    if status == 404:
        return "http_404"
    if status == 429:
        return "http_429_rate_limited"
    if status >= 400:
        return "publisher_protection"
    return ""

def manual_row(row: pd.Series, needed_file_type: str, reason: str, expected_path: Path) -> dict[str, str]:
    landing = row.get("landing_url", "") or row.get("doi_or_url", "")
    rel_path = expected_path.relative_to(helpers.PROJECT_ROOT)
    return {
        "source_id": row["source_id"],
        "title": row["title"],
        "doi_or_url": row["doi_or_url"],
        "landing_url": landing,
        "needed_file_type": needed_file_type,
        "reason": reason,
        "manual_instruction": f"Open {landing or row['doi_or_url']} in a browser, download {needed_file_type}, and save it exactly as {rel_path}.",
        "expected_local_path": str(rel_path),
    }

def log_row(source_id: str, file_type: str, url: str, local_path: Path, status: str, reason: str = "", http_status: str = "", message: str = "") -> dict[str, str]:
    return {
        "source_id": source_id,
        "file_type": file_type,
        "url": url,
        "local_path": str(local_path.relative_to(helpers.PROJECT_ROOT) if local_path.is_absolute() else local_path),
        "status": status,
        "reason": reason,
        "http_status": str(http_status),
        "message": message,
        "download_date": date.today().isoformat(),
    }

def save_url(url: str, out_path: Path, timeout: int, expected_pdf: bool = False) -> tuple[str, str, str]:
    response = http_get(url, timeout)
    reason = reason_from_status(response.status_code)
    if reason:
        return "failed", reason, str(response.status_code)
    content_type = response.headers.get("content-type", "").lower()
    if expected_pdf and "pdf" not in content_type and not response.content.startswith(b"%PDF"):
        return "failed", "pdf_url_not_found", str(response.status_code)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(response.content)
    return "success", "", str(response.status_code)

def discover_pdf_links(html: str, base_url: str) -> tuple[str, str]:
    pdf_url = ""
    supp_url = ""
    for match in re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE):
        absolute = urljoin(base_url, match)
        lowered = absolute.lower()
        if not pdf_url and (lowered.endswith(".pdf") or "download" in lowered and "pdf" in lowered):
            pdf_url = absolute
        if not supp_url and any(token in lowered for token in ["supplement", "supporting", "suppl"]):
            supp_url = absolute
    return pdf_url, supp_url

def acquire_one(row: pd.Series, timeout: int, no_network: bool) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    source_id = row["source_id"]
    helpers.source_dir(source_id).mkdir(parents=True, exist_ok=True)
    metadata = helpers.metadata_from_manifest(row)
    logs: list[dict[str, str]] = []
    manual: list[dict[str, str]] = []
    mode = row["download_mode"]
    article_path = helpers.article_pdf_path(source_id)
    html_path = helpers.landing_html_path(source_id)

    # Detect already existing files
    if article_path.exists():
        helpers.add_file_metadata(metadata, article_path, "article_pdf", "manual_present", notes="Local PDF already present.")
    if html_path.exists():
        helpers.add_file_metadata(metadata, html_path, "article_html", "manual_present", notes="Local HTML already present.")

    supplements = sorted(helpers.source_dir(source_id).glob("supplementary_*"))
    for supp in supplements:
        helpers.add_file_metadata(metadata, supp, "supplementary", "manual_present", notes="Local supplement already present.")

    if "verify" in str(row["doi_or_url"]).lower() or mode == "blocked_or_verify":
        metadata["metadata_warnings"].append("DOI/source metadata requires manual verification before extraction.")
        if not article_path.exists():
            manual.append(manual_row(row, "article_pdf", "doi_metadata_unclear", article_path))
            helpers.add_file_metadata(metadata, article_path, "article_pdf", "manual_required", notes="Metadata verification required.")
        helpers.write_metadata(source_id, metadata)
        return logs, manual

    if no_network:
        if not article_path.exists():
            manual.append(manual_row(row, "article_pdf", "pdf_url_not_found", article_path))
            helpers.add_file_metadata(metadata, article_path, "article_pdf", "manual_required", notes="Network disabled for acquisition run.")
        if "supplement" in str(row.get("source_type", "")).lower() and not supplements:
            supp_path = helpers.source_dir(source_id) / "supplementary_001.pdf"
            manual.append(manual_row(row, "supplementary", "supplement_url_not_found", supp_path))
            helpers.add_file_metadata(metadata, supp_path, "supplementary", "manual_required", notes="Network disabled for acquisition run.")
        helpers.write_metadata(source_id, metadata)
        return logs, manual

    landing_url = str(row.get("landing_url", "")).strip()
    if landing_url:
        try:
            status, reason, http_status = save_url(landing_url, html_path, timeout, expected_pdf=False)
            logs.append(log_row(source_id, "article_html", landing_url, html_path, status, reason, http_status))
            if status == "success":
                helpers.add_file_metadata(metadata, html_path, "article_html", "success", landing_url)
            else:
                manual.append(manual_row(row, "article_html", reason, html_path))
        except Exception as exc:
            logs.append(log_row(source_id, "article_html", landing_url, html_path, "failed", "publisher_protection", message=str(exc)))
            manual.append(manual_row(row, "article_html", "publisher_protection", html_path))

    expected_pdf_url = str(row.get("expected_pdf_url", "")).strip()
    expected_supp_url = str(row.get("expected_supplement_url", "")).strip()
    if not expected_pdf_url and mode in {"auto_html_then_pdf_discovery", "auto_pmc"} and html_path.exists():
        html = html_path.read_text(encoding="utf-8", errors="ignore")
        expected_pdf_url, discovered_supp = discover_pdf_links(html, landing_url)
        expected_supp_url = expected_supp_url or discovered_supp

    if expected_pdf_url:
        try:
            status, reason, http_status = save_url(expected_pdf_url, article_path, timeout, expected_pdf=True)
            logs.append(log_row(source_id, "article_pdf", expected_pdf_url, article_path, status, reason, http_status))
            helpers.add_file_metadata(metadata, article_path, "article_pdf", status if status == "success" else "manual_required", expected_pdf_url, reason)
            if status != "success":
                manual.append(manual_row(row, "article_pdf", reason, article_path))
        except Exception as exc:
            logs.append(log_row(source_id, "article_pdf", expected_pdf_url, article_path, "failed", "publisher_protection", message=str(exc)))
            manual.append(manual_row(row, "article_pdf", "publisher_protection", article_path))
            helpers.add_file_metadata(metadata, article_path, "article_pdf", "manual_required", expected_pdf_url, str(exc))
    elif not article_path.exists():
        manual.append(manual_row(row, "article_pdf", "pdf_url_not_found", article_path))
        helpers.add_file_metadata(metadata, article_path, "article_pdf", "manual_required", notes="No direct or discovered PDF URL.")

    if expected_supp_url:
        supp_path = helpers.source_dir(source_id) / "supplementary_001"
        try:
            response = http_get(expected_supp_url, timeout)
            reason = reason_from_status(response.status_code)
            if reason:
                logs.append(log_row(source_id, "supplementary", expected_supp_url, supp_path, "failed", reason, response.status_code))
                manual.append(manual_row(row, "supplementary", reason, supp_path))
                helpers.add_file_metadata(metadata, supp_path, "supplementary", "manual_required", expected_supp_url, reason)
            else:
                suffix = ".pdf" if "pdf" in response.headers.get("content-type", "").lower() else Path(expected_supp_url).suffix or ".bin"
                supp_path = supp_path.with_suffix(suffix)
                supp_path.write_bytes(response.content)
                logs.append(log_row(source_id, "supplementary", expected_supp_url, supp_path, "success", http_status=response.status_code))
                helpers.add_file_metadata(metadata, supp_path, "supplementary", "success", expected_supp_url)
        except Exception as exc:
            logs.append(log_row(source_id, "supplementary", expected_supp_url, supp_path, "failed", "publisher_protection", message=str(exc)))
            manual.append(manual_row(row, "supplementary", "publisher_protection", supp_path))
    elif "supplement" in str(row.get("source_type", "")).lower():
        supp_path = helpers.source_dir(source_id) / "supplementary_001.pdf"
        manual.append(manual_row(row, "supplementary", "supplement_url_not_found", supp_path))
        helpers.add_file_metadata(metadata, supp_path, "supplementary", "manual_required", notes="Supplement URL not found.")

    helpers.write_metadata(source_id, metadata)
    return logs, manual

def source_card_text(row: pd.Series) -> str:
    source_id = row["source_id"]
    article = helpers.article_pdf_path(source_id)
    html = helpers.landing_html_path(source_id)
    supplements = sorted(helpers.source_dir(source_id).glob("supplementary_*"))
    return f"""# {source_id} — Source card

## Bibliographic metadata
- Title: {row['title']}
- DOI/URL: {row['doi_or_url']}
- Access date: {row['access_date']}
- License/terms: {row['license_or_terms']}

## Local files
- Article PDF: {article.relative_to(helpers.PROJECT_ROOT) if article.exists() else 'missing'}
- Supplementary files: {', '.join(str(path.relative_to(helpers.PROJECT_ROOT)) for path in supplements) if supplements else 'missing/not_required'}
- HTML landing page: {html.relative_to(helpers.PROJECT_ROOT) if html.exists() else 'missing'}

## Scope decision
- In-scope dyes: {row['in_scope_dyes']}
- Out-of-scope parts: {row['out_of_scope_parts']}
- Expected experiment-level records: manual review after extraction

## Expected extraction targets
- Text sections: methods, photocatalytic degradation, kinetics, controls
- Tables: {row['expected_fields']}
- Figures: degradation curves, kinetic plots, activity comparisons
- Supplementary files: as listed in source metadata

## Known risks
- Missing light metadata: possible
- Dark adsorption ambiguity: possible
- Graph-derived values: manual digitization only
- Multi-dye splitting: {row['in_scope_dyes']}
- DOI/license verification: {row['notes']}
"""

def validate_inventory(manifest: pd.DataFrame) -> tuple[list[str], list[str], list[dict[str, str]]]:
    errors: list[str] = []
    warnings: list[str] = []
    manual_rows: list[dict[str, str]] = []

    for required in [helpers.PRACTICE1_SCHEMA_MD, helpers.PRACTICE2_SOURCE_MAP_MD, helpers.PRACTICE3_SOURCE_MANIFEST_CSV]:
        if not required.exists():
            errors.append(f"Missing required input file: {required.relative_to(helpers.PROJECT_ROOT)}")

    for _, row in manifest.iterrows():
        source_id = row["source_id"]
        sdir = helpers.source_dir(source_id)
        if not sdir.exists():
            errors.append(f"{source_id}: missing local source directory {sdir.relative_to(helpers.PROJECT_ROOT)}")
            sdir.mkdir(parents=True, exist_ok=True)
        metadata = helpers.load_metadata(source_id)
        if not metadata:
            errors.append(f"{source_id}: missing metadata.json")
        if "verify" in str(row["doi_or_url"]).lower() or source_id in {"P2-S03", "P2-S06", "P2-S20"}:
            warnings.append(f"{source_id}: DOI/source metadata must be verified before extraction.")
        priority = str(row.get("priority", "")).lower()
        if priority != "optional" and not helpers.has_usable_input(source_id):
            warnings.append(f"{source_id}: no local article PDF/HTML is available; extraction will skip this source.")
            manual_rows.append(manual_row(row, "article_pdf", "pdf_url_not_found", sdir / "article.pdf"))
        if not str(row.get("doi_or_url", "")).strip():
            errors.append(f"{source_id}: missing DOI/URL metadata.")

    return errors, warnings, manual_rows

def build_inventory_report(errors: list[str], warnings: list[str], manifest: pd.DataFrame) -> str:
    usable = sum(1 for source_id in manifest["source_id"] if helpers.has_usable_input(source_id))
    lines = [
        "# Input Inventory Report",
        "",
        "## Summary",
        f"- sources: {len(manifest)}",
        f"- usable_sources_with_pdf_or_html: {usable}",
        f"- errors: {len(errors)}",
        f"- warnings: {len(warnings)}",
        "",
        "## Errors",
    ]
    lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
    lines.append("")
    lines.append("## Warnings")
    lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
    lines.append("")
    lines.append("## Extraction Gate")
    lines.append("Extraction may run only for sources with local `article.pdf` or `landing.html`. Missing files are listed in `inputs/manual_download_queue.csv`.")
    return "\n".join(lines) + "\n"

def main() -> int:
    args = parse_args()
    helpers.setup_logging(args.verbose)
    helpers.ensure_directories()
    
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = helpers.PROJECT_ROOT / manifest_path
        
    ensure_reference_files()
    write_yaml_configs()
    
    manifest = ensure_manifest(manifest_path, args.overwrite)
    all_logs: list[dict[str, str]] = []
    all_manual: list[dict[str, str]] = []
    
    for _, row in manifest.iterrows():
        logs, manual = acquire_one(row, args.timeout, args.no_network)
        all_logs.extend(logs)
        all_manual.extend(manual)
        card = source_card_text(row)
        helpers.write_text(card, helpers.INPUT_SOURCE_CARDS_DIR / f"{row['source_id']}.md", overwrite=True)
        helpers.write_text(card, helpers.SOURCE_CARDS_DIR / f"{row['source_id']}.md", overwrite=True)
        
    helpers.write_csv(pd.DataFrame(all_logs, columns=helpers.DOWNLOAD_LOG_COLUMNS), helpers.DOWNLOAD_LOG_CSV)
    helpers.write_csv(pd.DataFrame(all_manual, columns=helpers.MANUAL_QUEUE_COLUMNS), helpers.MANUAL_DOWNLOAD_QUEUE_CSV)
    helpers.write_csv(helpers.manifest_to_sources_csv(manifest), helpers.DEFAULT_SOURCES_CSV)
    
    errors, warnings, extra_manual = validate_inventory(manifest)
    
    report = build_inventory_report(errors, warnings, manifest)
    helpers.write_text(report, helpers.INPUT_INVENTORY_REPORT_MD, overwrite=True)
    
    print(f"Manifest sources: {len(manifest)}")
    print(f"Download log rows: {len(all_logs)}")
    print(f"Manual queue rows: {len(all_manual) + len(extra_manual)}")
    print(f"Inventory validation errors: {len(errors)}, warnings: {len(warnings)}")
    
    if args.strict and errors:
        print("Inventory validation failed with strict checks.", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
