"""Consolidated helper module for Practice 3 PDF Extraction.
Aggregates configuration, schemas, text/table/figure parsing,
data mining rules, and record validation logic.
"""

from __future__ import annotations

import argparse
import re
import sys
import json
import math
import logging
from pathlib import Path
from typing import Any, Iterable
from datetime import date
from urllib.parse import urljoin
import pandas as pd
import requests

# ==========================================
# 1. PATH CONFIGURATION (formerly config.py)
# ==========================================
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
INPUTS_DIR = PROJECT_ROOT / "inputs"
INPUT_RAW_SOURCES_DIR = INPUTS_DIR / "raw_sources"
INPUT_SOURCE_CARDS_DIR = INPUTS_DIR / "source_cards"
REPORTS_DIR = PROJECT_ROOT / "reports"
DATA_DIR = PROJECT_ROOT / "data"
RAW_PDFS_DIR = DATA_DIR / "raw_pdfs"
RAW_SUPPLEMENTS_DIR = DATA_DIR / "raw_supplements"
EXTRACTED_TEXT_DIR = DATA_DIR / "extracted_text"
EXTRACTED_TABLES_DIR = DATA_DIR / "extracted_tables"
EXTRACTED_FIGURES_DIR = DATA_DIR / "extracted_figures"
INTERMEDIATE_JSON_DIR = DATA_DIR / "intermediate_json"
SOURCE_CARDS_DIR = PROJECT_ROOT / "source_cards"

DEFAULT_SOURCES_CSV = PROJECT_ROOT / "sources_pdf_selected.csv"
PRACTICE1_SCHEMA_MD = INPUTS_DIR / "practice1_schema.md"
PRACTICE2_SOURCE_MAP_MD = INPUTS_DIR / "practice2_source_map.md"
PRACTICE3_SOURCE_MANIFEST_CSV = INPUTS_DIR / "practice3_source_manifest.csv"
DOWNLOAD_LOG_CSV = INPUTS_DIR / "download_log.csv"
MANUAL_DOWNLOAD_QUEUE_CSV = INPUTS_DIR / "manual_download_queue.csv"
INPUT_INVENTORY_REPORT_MD = REPORTS_DIR / "input_inventory_report.md"
EXPERIMENT_RECORDS_CSV = PROJECT_ROOT / "extracted_experiment_records.csv"
TIME_SERIES_CSV = PROJECT_ROOT / "extracted_time_series_optional.csv"
TABLES_INDEX_CSV = PROJECT_ROOT / "extracted_tables_index.csv"
FIGURES_INDEX_CSV = PROJECT_ROOT / "extracted_figures_index.csv"
AMBIGUOUS_CASES_CSV = PROJECT_ROOT / "ambiguous_cases.csv"
EXCLUDED_RECORDS_CSV = PROJECT_ROOT / "excluded_records.csv"

def ensure_directories() -> None:
    """Create the standard project directories."""
    for path in [
        CONFIG_DIR,
        INPUTS_DIR,
        INPUT_RAW_SOURCES_DIR,
        INPUT_SOURCE_CARDS_DIR,
        REPORTS_DIR,
        RAW_PDFS_DIR,
        RAW_SUPPLEMENTS_DIR,
        EXTRACTED_TEXT_DIR,
        EXTRACTED_TABLES_DIR,
        EXTRACTED_FIGURES_DIR,
        INTERMEDIATE_JSON_DIR,
        SOURCE_CARDS_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)

# ==========================================
# 2. SCHEMAS & VOCABULARIES (formerly schema.py & input_schema.py)
# ==========================================
SOURCE_COLUMNS = [
    "source_id", "title", "doi_or_url", "publication_year",
    "source_group", "source_type", "expected_data_format",
    "expected_available_fields", "extraction_role",
    "license_or_terms", "notes", "local_pdf_path", "local_supplement_paths",
]

EXPERIMENT_COLUMNS = [
    "experiment_id", "source_id", "doi_or_url", "paper_title", "publication_year",
    "source_location", "value_origin", "catalyst_name_raw", "catalyst_composition",
    "catalyst_class", "catalyst_mode", "dye_name", "dye_abbreviation", "single_dye_system",
    "initial_dye_concentration_value", "initial_dye_concentration_unit",
    "solution_volume_value", "solution_volume_unit",
    "catalyst_loading_value", "catalyst_loading_unit", "initial_pH",
    "light_regime", "light_source_type", "wavelength_or_cutoff_nm",
    "irradiance_value", "irradiance_unit", "dark_adsorption_present",
    "dark_adsorption_time_min", "dark_adsorption_pct", "irradiation_time_min",
    "degradation_efficiency_pct", "outcome_type", "C_over_C0_final",
    "k_app_value", "k_app_unit", "kinetic_model", "R2_kinetic_fit",
    "analysis_method", "monitoring_wavelength_nm", "photolysis_control_present",
    "dark_control_present", "sensitization_risk_flag", "high_dark_adsorption_flag",
    "missing_dark_control_flag", "missing_photolysis_control_flag",
    "unclear_light_source_flag", "approximate_value_flag", "rhb_peak_shift_flag",
    "mixed_metric_flag", "extraction_confidence", "extraction_notes",
    "unit_normalization_notes", "manual_review_required",
]

TIME_SERIES_COLUMNS = [
    "time_series_id", "experiment_id", "source_id", "source_location",
    "value_origin", "time_min", "C_over_C0", "absorbance",
    "concentration_value", "concentration_unit", "degradation_efficiency_pct",
    "monitoring_wavelength_nm", "approximate_value_flag", "extraction_notes",
]

TABLE_INDEX_COLUMNS = [
    "source_id", "file_path", "page_number", "table_index",
    "extraction_method", "output_csv_path", "n_rows", "n_columns",
    "caption_or_nearby_text", "relevance_score", "manual_review_required", "notes",
]

FIGURE_INDEX_COLUMNS = [
    "source_id", "file_path", "page_number", "figure_index",
    "image_path", "caption", "nearby_text", "figure_type_guess",
    "relevance_score", "contains_degradation_curve", "contains_kinetic_plot",
    "contains_bar_chart", "manual_digitization_required", "notes",
]

AMBIGUOUS_COLUMNS = [
    "case_id", "source_id", "file_path", "page_number", "source_location",
    "case_type", "description", "affected_fields", "proposed_resolution", "manual_review_required",
]

EXCLUDED_COLUMNS = [
    "excluded_id", "source_id", "source_location", "candidate_description",
    "exclusion_reason", "notes",
]

VALIDATION_COLUMNS = ["level", "record_id", "source_id", "field", "message"]

MANIFEST_COLUMNS = [
    "source_id", "title", "doi_or_url", "landing_url", "expected_pdf_url",
    "expected_supplement_url", "source_group", "source_type", "access_date",
    "license_or_terms", "download_mode", "priority", "practice3_role",
    "in_scope_dyes", "out_of_scope_parts", "expected_fields", "notes",
]

DOWNLOAD_LOG_COLUMNS = [
    "source_id", "file_type", "url", "local_path", "status", "reason",
    "http_status", "message", "download_date",
]

MANUAL_QUEUE_COLUMNS = [
    "source_id", "title", "doi_or_url", "landing_url", "needed_file_type",
    "reason", "manual_instruction", "expected_local_path",
]

CONTROLLED_VOCABS = {
    "light_regime": {"UV", "visible", "solar", "solar_simulator", "mixed", "unknown"},
    "catalyst_mode": {"suspended_powder", "immobilized_film", "coated_support", "unknown"},
    "outcome_type": {"decolorization", "removal", "degradation", "mineralization", "unknown"},
    "analysis_method": {"UV-Vis", "TOC", "COD", "HPLC", "other", "not_reported"},
    "value_origin": {"text", "table", "digitized_figure", "supplement", "repository", "mixed"},
    "control": {"yes", "no", "not_reported"},
    "boolean": {"true", "false"},
    "extraction_confidence": {"high", "medium", "low"},
}

REQUIRED_RECORD_FIELDS = [
    "experiment_id", "source_id", "doi_or_url", "paper_title", "publication_year",
    "source_location", "catalyst_name_raw", "catalyst_composition", "catalyst_mode",
    "dye_name", "single_dye_system", "light_regime", "light_source_type",
    "irradiation_time_min", "degradation_efficiency_pct", "outcome_type",
    "analysis_method", "photolysis_control_present", "dark_control_present", "sensitization_risk_flag",
]

BOOLEAN_FIELDS = [
    "sensitization_risk_flag", "high_dark_adsorption_flag", "missing_dark_control_flag",
    "missing_photolysis_control_flag", "unclear_light_source_flag", "approximate_value_flag",
    "rhb_peak_shift_flag", "mixed_metric_flag", "manual_review_required",
]

CONTROL_FIELDS = ["photolysis_control_present", "dark_control_present", "dark_adsorption_present"]

EXCLUSION_REASONS = {
    "pure_adsorption_without_irradiation", "pure_photolysis_without_catalyst",
    "mixed_dye_not_separable", "real_wastewater_no_single_target_dye",
    "non_dye_reaction", "hydrogen_evolution_only", "antibacterial_only",
    "phenol_only", "catalyst_characterization_only", "no_numerical_outcome",
    "no_irradiation_time", "review_summary_only", "unsupported_or_unreadable_source",
}

DOWNLOAD_MODES = {
    "auto_pdf_url", "manual_landing_page", "auto_html_then_pdf_discovery",
    "auto_pmc", "blocked_or_verify",
}

PRIORITIES = {"pilot", "core", "optional", "fallback", "pilot/core", "core/optional", "core but verify"}

MANUAL_REASONS = {
    "http_403", "http_404", "http_429_rate_limited", "publisher_protection",
    "doi_metadata_unclear", "pdf_url_not_found", "supplement_url_not_found",
    "license_or_terms_need_manual_check",
}

def default_manifest_rows() -> list[tuple[str, ...]]:
    today = date.today().isoformat()
    return [
        ("P2-S01", "Adsorption and Photocatalytic Degradation of Methylene Blue on TiO2 Thin Films Impregnated with Anderson-Evans Al-Polyoxometalates", "10.1021/acsomega.3c02657", "https://pmc.ncbi.nlm.nih.gov/", "", "", "Practice 2 selected", "PDF + supplementary PDF", today, "open/verify at source", "auto_pmc", "pilot", "PDF + supplementary PDF", "methylene blue; MB", "", "MB degradation %, adsorption %, k_app", "Pilot/core source; PMC/ACS availability should be verified."),
        ("P2-S02", "Sunlight-Driven Photocatalytic Degradation of Methylene Blue with Cu-Cu2O-Cu3N Nanoparticle Mixtures", "10.3390/nano13081311", "https://www.mdpi.com/2079-4991/13/8/1311", "", "", "Practice 2 selected", "HTML/PDF + supplementary", today, "open/verify at source", "auto_html_then_pdf_discovery", "pilot", "HTML/PDF + supplementary", "methylene blue; MB", "", "MB degradation; sunlight; catalyst dosages", "Pilot/core source; MDPI may rate-limit direct download."),
        ("P2-S09", "Enhanced Photocatalytic Degradation of Malachite Green Dye Using Silver-Manganese Oxide Nanoparticles", "10.3390/molecules28176241", "https://www.mdpi.com/1420-3049/28/17/6241", "", "", "Practice 2 selected", "HTML/PDF", today, "open/verify at source", "auto_html_then_pdf_discovery", "pilot", "HTML/PDF article", "malachite green; MG", "", "MG degradation; sunlight; dosage; pH; dark stage", "Pilot/core source."),
        ("P2-S03", "Study of methylene blue removal and photocatalytic degradation on zirconia thin films modified with Mn-Anderson polyoxometalates", "verify DOI: likely 10.1039/D4DT02782E", "https://pubs.rsc.org/", "", "", "Practice 2 selected", "PDF/article", today, "verify at source", "blocked_or_verify", "core", "PDF/article", "methylene blue; MB", "", "MB removal; degradation; kinetics", "DOI mismatch risk; do not process until resolved."),
        ("P2-S04", "Kinetic Investigation of Photocatalytic Degradation of Methyl Orange Dye Using Mg-Doped Ag2O Nanoparticle", "10.1155/2026/5063293", "", "", "", "Practice 2 selected", "PDF/article", today, "open/verify at source", "blocked_or_verify", "core", "PDF/article", "methyl orange; MO", "", "MO degradation; k_app", "Direct PDF may be available; verify source manually if discovery fails."),
        ("P2-S05", "TiO2-modified g-C3N4 nanocomposite for photocatalytic degradation of RhB and MB", "10.1016/j.heliyon.2022.e11065", "https://pmc.ncbi.nlm.nih.gov/", "", "", "Practice 2 selected", "PDF/article", today, "open/verify at source", "auto_pmc", "core", "PDF/article", "rhodamine B; RhB; methylene blue; MB", "", "RhB and MB degradation; kinetics", "Multi-dye article; split records by dye."),
        ("P2-S06", "Photocatalytic degradation of Rhodamine B using ZnO/Ag nanowire nanocomposite films", "verify DOI/source metadata before processing", "https://royalsocietypublishing.org/", "", "", "Practice 2 selected", "PDF/article", today, "open/verify at source", "blocked_or_verify", "core", "PDF/article", "rhodamine B; RhB", "", "RhB degradation; kinetics", "Metadata verification required."),
        ("P2-S07", "Ni-Cd co-doped ZnO nanoparticles for RhB degradation", "10.1038/s41598-025-14177-2", "https://www.nature.com/articles/s41598-025-14177-2", "", "", "Practice 2 selected", "HTML/PDF + supplement", today, "open/verify at source", "auto_html_then_pdf_discovery", "core", "HTML/PDF + supplement", "rhodamine B; RhB", "", "RhB degradation; supplement; unit conversion", "Supplement may require manual download."),
        ("P2-S08", "Photodegradation of Rhodamine B and Phenol Using TiO2/SiO2 Composite Nanoparticles", "10.3390/w15152773", "https://www.mdpi.com/2073-4441/15/15/2773", "", "", "Practice 2 selected", "HTML/PDF", today, "open/verify at source", "auto_html_then_pdf_discovery", "core", "HTML/PDF article", "rhodamine B; RhB", "phenol-only records", "RhB degradation only", "Extract RhB only; exclude phenol."),
        ("P2-S10", "Photocatalytic degradation of methyl orange, eriochrome black T and methylene blue using silica-titania fibers", "10.3390/app152212084", "https://www.mdpi.com/", "", "", "Practice 2 selected", "HTML/PDF/article", today, "open/verify at source", "blocked_or_verify", "core", "HTML/PDF article", "methyl orange; eriochrome black T; methylene blue", "", "separable dye degradation outcomes", "Verify DOI and availability."),
        ("P2-S20", "Photocatalytic degradation of Orange G dye using Bi2MoO6", "PMCID/source-map identifier must be verified", "https://pmc.ncbi.nlm.nih.gov/", "", "", "Practice 2 optional", "PDF/article", today, "open/verify at source", "blocked_or_verify", "optional", "PDF/article", "Orange G", "", "Orange G degradation", "Optional extension; verify identifier."),
    ]

DEFAULT_SOURCES = [
    ("P2-S01", "Al-polyoxometalate-impregnated TiO2 thin films for methylene-blue degradation", "10.1021/acsomega.3c02657", "2023", "Practice 2 selected", "PDF + supplementary PDF", "article/supplement PDF", "conditions; degradation; kinetics; figures", "primary", "open/verify at source", "", "", ""),
    ("P2-S02", "Sunlight-driven Cu-Cu2O-Cu3N nanoparticles for methylene-blue degradation", "10.3390/nano13020270", "2023", "Practice 2 selected", "HTML/PDF + supplementary PDF", "article/supplement PDF", "conditions; degradation; kinetics; figures", "primary", "open/verify at source", "", "", ""),
    ("P2-S03", "Methylene-blue removal on zirconia thin films modified with Mn-Anderson polyoxometalates", "10.1039/C3DT51181A", "2013", "Practice 2 selected", "PDF article", "article PDF", "conditions; removal; kinetics; figures", "primary", "verify at source", "", "", ""),
    ("P2-S04", "Kinetic investigation of methyl orange degradation using Mg-doped Ag2O nanoparticles", "10.1155/2026/5063293", "2026", "Practice 2 selected", "PDF article", "article PDF", "conditions; degradation; kinetics", "primary", "open/verify at source", "", "", ""),
    ("P2-S05", "TiO2/g-C3N4 heterostructure for RhB and MB degradation", "10.1016/j.heliyon.2022.e11065", "2022", "Practice 2 selected", "PDF article", "article PDF", "conditions; degradation; kinetics; figures", "primary", "open/verify at source", "", "", ""),
    ("P2-S06", "ZnO/Ag nanowire composite for Rhodamine B degradation", "10.1098/rsos.170869", "2018", "Practice 2 selected", "PDF article", "article PDF", "conditions; degradation; kinetics; figures", "primary", "open/verify at source", "", "", ""),
    ("P2-S07", "Ni-Cd co-doped ZnO nanoparticles for RhB degradation", "10.1038/s41598-025-14177-2", "2025", "Practice 2 selected", "HTML/PDF + supplementary DOCX", "article/supplement PDF/DOCX", "conditions; degradation; kinetics; figures", "primary", "open/verify at source", "", "", ""),
    ("P2-S08", "Photodegradation of RhB and phenol using TiO2/SiO2 composite", "10.3390/w15213730", "2023", "Practice 2 selected", "PDF article", "article PDF", "RhB only; conditions; degradation; figures", "primary", "open/verify at source", "Extract RhB only; phenol-only records excluded.", "", ""),
    ("P2-S09", "Enhanced photocatalytic degradation of malachite green using silver-manganese oxide nanoparticles", "10.3390/molecules28176241", "2023", "Practice 2 selected", "PDF article", "article PDF", "conditions; degradation; kinetics; figures", "primary", "open/verify at source", "", "", ""),
    ("P2-S10", "Photocatalytic degradation of methyl orange, eriochrome black T and methylene blue using silica-titania fibers", "10.3390/app152212084", "2025", "Practice 2 selected", "PDF/HTML article", "article PDF/HTML", "separable dye outcomes; conditions; degradation", "primary", "open/verify at source", "", "", ""),
    ("P2-S20", "Photocatalytic degradation of Orange G dye using Bi2MoO6", "PMC6450450369", "", "Practice 2 optional", "PDF article", "article PDF", "conditions; degradation; kinetics", "optional", "open/verify at source", "Optional extension if time allows.", "", ""),
]

# ==========================================
# 3. I/O UTILITIES (formerly io_utils.py)
# ==========================================
logger = logging.getLogger("core")

def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")

def read_csv_or_empty(path: Path, columns: list[str]) -> pd.DataFrame:
    if path.exists():
        df = pd.read_csv(path, dtype=str).fillna("")
        for column in columns:
            if column not in df.columns:
                df[column] = ""
        return df[columns]
    return pd.DataFrame(columns=columns)

def write_csv(df: pd.DataFrame, path: Path, overwrite: bool = True) -> None:
    if path.exists() and not overwrite:
        logger.info("Keeping existing file: %s", path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)

def write_json(data: Any, path: Path, overwrite: bool = True) -> None:
    if path.exists() and not overwrite:
        logger.info("Keeping existing file: %s", path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def write_text(text: str, path: Path, overwrite: bool = True) -> None:
    if path.exists() and not overwrite:
        logger.info("Keeping existing file: %s", path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

def append_rows(path: Path, rows: Iterable[dict[str, Any]], columns: list[str]) -> None:
    rows = list(rows)
    if not rows:
        return
    existing = read_csv_or_empty(path, columns)
    appended = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
    appended = appended.drop_duplicates()
    write_csv(appended[columns], path)

# ==========================================
# 4. ACQUISITION HELPERS (formerly input_inventory.py)
# ==========================================
def source_dir(source_id: str) -> Path:
    return INPUT_RAW_SOURCES_DIR / source_id

def metadata_path(source_id: str) -> Path:
    return source_dir(source_id) / "metadata.json"

def article_pdf_path(source_id: str) -> Path:
    return source_dir(source_id) / "article.pdf"

def landing_html_path(source_id: str) -> Path:
    return source_dir(source_id) / "landing.html"

def load_metadata(source_id: str) -> dict[str, Any]:
    path = metadata_path(source_id)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

def write_metadata(source_id: str, metadata: dict[str, Any]) -> None:
    path = metadata_path(source_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

def metadata_from_manifest(row: pd.Series) -> dict[str, Any]:
    return {
        "source_id": row["source_id"],
        "title": row["title"],
        "doi_or_url": row["doi_or_url"],
        "landing_url": row["landing_url"],
        "access_date": row["access_date"],
        "download_date": date.today().isoformat(),
        "license_or_terms": row["license_or_terms"],
        "download_mode": row["download_mode"],
        "priority": row["priority"],
        "practice3_role": row["practice3_role"],
        "metadata_warnings": [],
        "files": [],
    }

def add_file_metadata(metadata: dict[str, Any], local_path: Path, file_type: str, status: str, source_url: str = "", notes: str = "") -> None:
    files = [item for item in metadata.get("files", []) if item.get("file_type") != file_type]
    files.append(
        {
            "local_path": str(local_path.relative_to(PROJECT_ROOT) if local_path.is_absolute() else local_path),
            "file_type": file_type,
            "download_status": status,
            "source_url": source_url,
            "notes": notes,
        }
    )
    metadata["files"] = files

def has_usable_input(source_id: str) -> bool:
    meta = load_metadata(source_id)
    files = meta.get("files", [])
    for item in files:
        local_path = PROJECT_ROOT / item.get("local_path", "")
        if item.get("file_type") in {"article_pdf", "article_html"} and item.get("download_status") in {"success", "manual_present"} and local_path.exists():
            return True
    return article_pdf_path(source_id).exists() or landing_html_path(source_id).exists()

def manifest_to_sources_csv(manifest: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for _, row in manifest.iterrows():
        source_id = row["source_id"]
        pdf_path = article_pdf_path(source_id)
        supp_paths = sorted(source_dir(source_id).glob("supplementary_*"))
        rows.append(
            {
                "source_id": source_id,
                "title": row["title"],
                "doi_or_url": row["doi_or_url"],
                "publication_year": "",
                "source_group": row["source_group"],
                "source_type": row["source_type"],
                "expected_data_format": row["practice3_role"],
                "expected_available_fields": row["expected_fields"],
                "extraction_role": "optional" if row["priority"] == "optional" else "primary",
                "license_or_terms": row["license_or_terms"],
                "notes": row["notes"],
                "local_pdf_path": str(pdf_path.relative_to(PROJECT_ROOT)) if pdf_path.exists() else "",
                "local_supplement_paths": "|".join(str(path.relative_to(PROJECT_ROOT)) for path in supp_paths),
            }
        )
    return pd.DataFrame(rows, columns=SOURCE_COLUMNS)

# ==========================================
# 5. PROVENANCE (formerly provenance.py)
# ==========================================
def source_location(page_number: int | str | None = None, detail: str | None = None) -> str:
    parts: list[str] = []
    if page_number not in (None, ""):
        parts.append(f"page {page_number}")
    if detail:
        parts.append(detail)
    return " ".join(parts) if parts else "not_reported"

def ambiguous_case(
    case_id: str,
    source_id: str,
    file_path: str | Path,
    case_type: str,
    description: str,
    page_number: int | str = "",
    affected_fields: str = "",
    proposed_resolution: str = "manual review",
) -> dict[str, str]:
    return {
        "case_id": case_id,
        "source_id": source_id,
        "file_path": str(file_path),
        "page_number": str(page_number),
        "source_location": source_location(page_number),
        "case_type": case_type,
        "description": description,
        "affected_fields": affected_fields,
        "proposed_resolution": proposed_resolution,
        "manual_review_required": "true",
    }

# ==========================================
# 6. PDF EXTRACTION UTILITIES (formerly pdf_text/tables/figures)
# ==========================================
def extract_pages(pdf_path: Path, source_id: str) -> list[dict[str, object]]:
    import pdfplumber
    pages: list[dict[str, object]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append(
                {
                    "source_id": source_id,
                    "file_path": str(pdf_path),
                    "page_number": index,
                    "text": text,
                    "char_count": len(text),
                    "extraction_method": "pdfplumber",
                }
            )
    return pages

def pages_to_markdown(source_id: str, pages: list[dict[str, object]]) -> str:
    chunks = [f"# Extracted text: {source_id}", ""]
    for page in pages:
        chunks.append(f"## Page {page['page_number']}")
        chunks.append("")
        chunks.append(str(page.get("text", "")))
        chunks.append("")
    return "\n".join(chunks)

# Table utilities
TABLE_KEYWORDS = [
    "degradation", "removal", "decolorization", "photocatalytic",
    "photocatalysis", "kinetic", "rate constant", "k_app", "kapp",
    "min-1", "min−1", "c/c0", "c0/c", "concentration", "dye",
    "methylene blue", "mb", "rhodamine b", "rhb", "methyl orange",
    "mo", "malachite green", "mg", "crystal violet", "cv",
    "catalyst loading", "ph", "irradiation", "visible", "uv", "sunlight",
]

def relevance_score_table(text: str) -> int:
    lowered = text.lower()
    return sum(1 for keyword in TABLE_KEYWORDS if keyword in lowered)

def table_to_dataframe(table: list[list[Any]]) -> pd.DataFrame:
    cleaned = [["" if cell is None else str(cell).strip() for cell in row] for row in table]
    if not cleaned:
        return pd.DataFrame()
    width = max(len(row) for row in cleaned)
    normalized = [row + [""] * (width - len(row)) for row in cleaned]
    return pd.DataFrame(normalized)

def nearby_text(page: Any, max_chars: int = 600) -> str:
    text = page.extract_text() or ""
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]

def extract_pdfplumber_tables(pdf_path: Path, source_id: str, out_dir: Path) -> list[dict[str, object]]:
    import pdfplumber
    rows: list[dict[str, object]] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            page_text = nearby_text(page)
            for table_index, table in enumerate(page.extract_tables() or [], start=1):
                df = table_to_dataframe(table)
                if df.empty:
                    continue
                output_path = out_dir / f"{source_id}_p{page_index}_t{table_index}.csv"
                df.to_csv(output_path, index=False, header=False)
                combined_text = page_text + " " + " ".join(df.astype(str).fillna("").values.ravel())
                score = relevance_score_table(combined_text)
                rows.append(
                    {
                        "source_id": source_id,
                        "file_path": str(pdf_path),
                        "page_number": page_index,
                        "table_index": table_index,
                        "extraction_method": "pdfplumber",
                        "output_csv_path": str(output_path),
                        "n_rows": len(df),
                        "n_columns": len(df.columns),
                        "caption_or_nearby_text": page_text,
                        "relevance_score": score,
                        "manual_review_required": str(score >= 2).lower(),
                        "notes": "",
                    }
                )
    return rows

# Figure utilities
FIGURE_RELEVANCE_KEYWORDS = [
    "degradation", "c/c0", "ct/c0", "ln(c0/c)", "kinetic", "rate constant",
    "removal efficiency", "decolorization", "irradiation time", "photocatalytic activity",
]

CAPTION_PATTERN = re.compile(
    r"((?:Fig\.|Figure|Scheme)\s*\d+[^\n]{0,500}|Graphical abstract[^\n]{0,300})",
    re.IGNORECASE,
)

def relevance_score_figure(text: str) -> int:
    lowered = text.lower()
    return sum(1 for keyword in FIGURE_RELEVANCE_KEYWORDS if keyword in lowered)

def guess_figure_type(text: str) -> str:
    lowered = text.lower()
    if "ln(c0/c)" in lowered or "rate constant" in lowered or "kinetic" in lowered:
        return "kinetic_plot"
    if "c/c0" in lowered or "ct/c0" in lowered or "degradation" in lowered or "irradiation time" in lowered:
        return "degradation_curve"
    if "bar" in lowered or "efficiency" in lowered:
        return "bar_chart"
    if "uv-vis" in lowered or "absorbance" in lowered or "spectra" in lowered:
        return "uv_vis_spectra"
    if "xrd" in lowered:
        return "xrd"
    if "sem" in lowered or "tem" in lowered:
        return "sem_tem"
    if "scheme" in lowered:
        return "scheme"
    return "unknown"

def extract_page_figures(pdf_path: Path, source_id: str, out_dir: Path, zoom: float = 1.5) -> list[dict[str, object]]:
    import fitz
    rows: list[dict[str, object]] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    with fitz.open(pdf_path) as doc:
        matrix = fitz.Matrix(zoom, zoom)
        for page_index, page in enumerate(doc, start=1):
            text = re.sub(r"\s+", " ", page.get_text("text") or "").strip()
            captions = CAPTION_PATTERN.findall(text)
            relevant_page = relevance_score_figure(text) > 0
            if not captions and not relevant_page:
                continue
            pix = page.get_pixmap(matrix=matrix)
            image_path = out_dir / f"{source_id}_p{page_index}_fig1.png"
            pix.save(image_path)
            caption = captions[0] if captions else ""
            nearby = caption or text[:800]
            combined = f"{caption} {nearby}"
            score = relevance_score_figure(combined)
            figure_type = guess_figure_type(combined)
            rows.append(
                {
                    "source_id": source_id,
                    "file_path": str(pdf_path),
                    "page_number": page_index,
                    "figure_index": 1,
                    "image_path": str(image_path),
                    "caption": caption,
                    "nearby_text": nearby,
                    "figure_type_guess": figure_type,
                    "relevance_score": score,
                    "contains_degradation_curve": str(figure_type == "degradation_curve").lower(),
                    "contains_kinetic_plot": str(figure_type == "kinetic_plot").lower(),
                    "contains_bar_chart": str(figure_type == "bar_chart").lower(),
                    "manual_digitization_required": str(score > 0 and figure_type in {"degradation_curve", "kinetic_plot", "bar_chart"}).lower(),
                    "notes": "Page-level rendering; use for manual inspection/digitization.",
                }
            )
    return rows

# ==========================================
# 7. EXTRACTION RULES (formerly extraction_rules.py)
# ==========================================
PATTERNS: dict[str, re.Pattern[str]] = {
    "degradation_efficiency_pct": re.compile(r"\b(?:degradation|removal|decolori[sz]ation|efficiency)[^.\n]{0,80}?\b(\d{1,3}(?:\.\d+)?)\s*(?:%|percent)\b|\b(\d{1,3}(?:\.\d+)?)\s*(?:%|percent)\s+(?:degradation|removal|decolori[sz]ation)", re.IGNORECASE),
    "irradiation_time_min": re.compile(r"\b(?:irradiation|illumination|visible light|uv light|sunlight|after|within|for)\s+[^.\n]{0,50}?(\d+(?:\.\d+)?)\s*(min|minutes|h|hr|hours)\b", re.IGNORECASE),
    "k_app_value": re.compile(r"\b(?:k\s*[_-]?\s*app|kapp|rate constant)[^.\n]{0,80}?(\d+(?:\.\d+)?(?:\s*[x×]\s*10\s*[−-]?\s*\d+)?)\s*(?:min\s*[−-]?\s*1|min−1|h\s*[−-]?\s*1|h−1)", re.IGNORECASE),
    "initial_pH": re.compile(r"\bpH\s*(?:=|of|was|at)?\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE),
    "initial_dye_concentration": re.compile(r"\b(\d+(?:\.\d+)?(?:e[−-]?\d+)?)\s*(mg\s*/\s*L|ppm|mol\s*/\s*L|M|mM|µM|uM)\b", re.IGNORECASE),
    "catalyst_loading": re.compile(r"\b(\d+(?:\.\d+)?)\s*(g\s*/\s*L|mg\s*/\s*mL|mg\s*/\s*L|mg)\b", re.IGNORECASE),
    "wavelength_or_cutoff_nm": re.compile(r"(?:>|≥|<=|<|about|at|wavelength)?\s*(\d{3,4})\s*nm\b", re.IGNORECASE),
    "light_source_type": re.compile(r"\b(?:Xe|xenon|mercury|UV|LED|solar simulator|sunlight|visible light|UV light|halogen)\s+(?:lamp|light)?\b|\bsunlight\b|\bsolar simulator\b", re.IGNORECASE),
    "dark_adsorption": re.compile(r"\bdark adsorption\b|\badsorption-desorption\b|\bin the dark\b", re.IGNORECASE),
    "monitoring_wavelength_nm": re.compile(r"\b(?:monitored|absorbance|maximum|lambda|max|λmax)[^.\n]{0,60}?(\d{3,4})\s*nm\b", re.IGNORECASE),
    "control": re.compile(r"\b(?:photolysis|blank|control|without catalyst|dark control)\b", re.IGNORECASE),
}

DYE_PATTERNS: dict[str, re.Pattern[str]] = {
    "methylene blue": re.compile(r"\bmethylene blue\b|\bMB\b", re.IGNORECASE),
    "rhodamine B": re.compile(r"\brhodamine\s*B\b|\bRhB\b", re.IGNORECASE),
    "methyl orange": re.compile(r"\bmethyl orange\b|\bMO\b", re.IGNORECASE),
    "malachite green": re.compile(r"\bmalachite green\b|\bMG\b", re.IGNORECASE),
    "eriochrome black T": re.compile(r"\beriochrome black T\b|\bEBT\b", re.IGNORECASE),
    "Orange G": re.compile(r"\bOrange G\b", re.IGNORECASE),
}

EXCLUSION_PATTERNS = {
    "hydrogen_evolution_only": re.compile(r"\bhydrogen evolution\b|\bH2 evolution\b", re.IGNORECASE),
    "antibacterial_only": re.compile(r"\bantibacterial\b|\bantimicrobial\b", re.IGNORECASE),
    "phenol_only": re.compile(r"\bphenol\b", re.IGNORECASE),
    "pure_adsorption_without_irradiation": re.compile(r"\badsorption\b(?![^.\n]{0,80}(?:irradiation|light|photocatal))", re.IGNORECASE),
}

def split_paragraphs(text: str) -> Iterable[str]:
    for para in re.split(r"\n\s*\n|(?<=\.)\s+(?=[A-Z])", text):
        cleaned = re.sub(r"\s+", " ", para).strip()
        if len(cleaned) >= 40:
            yield cleaned

def matched_fields(snippet: str) -> list[str]:
    fields = [name for name, pattern in PATTERNS.items() if pattern.search(snippet)]
    fields.extend([f"dye:{name}" for name, pattern in DYE_PATTERNS.items() if pattern.search(snippet)])
    return fields

def mine_page_candidates(source_id: str, page_number: int, text: str) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for idx, snippet in enumerate(split_paragraphs(text), start=1):
        fields = matched_fields(snippet)
        if not fields:
            continue
        confidence = "medium" if {"degradation_efficiency_pct", "irradiation_time_min"} <= set(fields) else "low"
        candidates.append(
            {
                "source_id": source_id,
                "page_number": page_number,
                "source_location": f"page {page_number} paragraph {idx}",
                "snippet": snippet,
                "matched_fields": fields,
                "confidence": confidence,
                "manual_review_required": True,
            }
        )
    return candidates

def exclusion_reason(snippet: str) -> str:
    for reason, pattern in EXCLUSION_PATTERNS.items():
        if pattern.search(snippet):
            return reason
    return ""

# ==========================================
# 8. VALIDATION HELPERS (formerly validators.py)
# ==========================================
def blank(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value)) or str(value).strip() == ""

def as_float(value: Any) -> float | None:
    if blank(value):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None

def issue(level: str, record_id: str, source_id: str, field: str, message: str) -> dict[str, str]:
    return {"level": level, "record_id": record_id, "source_id": source_id, "field": field, "message": message}

def validate_records(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    for idx, row in df.iterrows():
        record_id = str(row.get("experiment_id", f"row-{idx + 1}"))
        source_id = str(row.get("source_id", ""))
        for field in REQUIRED_RECORD_FIELDS:
            if blank(row.get(field, "")):
                errors.append(issue("error", record_id, source_id, field, "Required field is blank."))

        numeric_rules = [
            ("degradation_efficiency_pct", 0, 100, True),
            ("irradiation_time_min", 0, None, False),
            ("C_over_C0_final", 0, 1.5, True),
            ("k_app_value", 0, None, False),
            ("initial_pH", 0, 14, True),
        ]
        for field, low, high, inclusive_low in numeric_rules:
            value = as_float(row.get(field, ""))
            if value is None:
                continue
            low_bad = value < low if inclusive_low else value <= low
            high_bad = high is not None and value > high
            if low_bad or high_bad:
                level = "warning" if field in {"C_over_C0_final", "initial_pH"} else "error"
                target = warnings if level == "warning" else errors
                target.append(issue(level, record_id, source_id, field, f"Numeric value {value} is outside expected range."))
            if field == "C_over_C0_final" and value > 1:
                warnings.append(issue("warning", record_id, source_id, field, "C/C0 above 1 requires an extraction note."))

        for field in ["light_regime", "catalyst_mode", "outcome_type", "analysis_method", "value_origin", "extraction_confidence"]:
            value = str(row.get(field, "")).strip()
            if value and value not in CONTROLLED_VOCABS[field]:
                errors.append(issue("error", record_id, source_id, field, f"Value '{value}' is not in controlled vocabulary."))
        for field in CONTROL_FIELDS:
            value = str(row.get(field, "")).strip()
            if value and value not in CONTROLLED_VOCABS["control"]:
                errors.append(issue("error", record_id, source_id, field, f"Value '{value}' must be yes/no/not_reported."))
        for field in BOOLEAN_FIELDS:
            value = str(row.get(field, "")).strip().lower()
            if value and value not in CONTROLLED_VOCABS["boolean"]:
                errors.append(issue("error", record_id, source_id, field, f"Value '{value}' must be true/false."))

        dye = str(row.get("dye_name", "")).lower()
        source_location_str = str(row.get("source_location", "")).lower()
        notes = str(row.get("extraction_notes", "")).lower()
        if str(row.get("single_dye_system", "")).strip().lower() == "false":
            warnings.append(issue("warning", record_id, source_id, "single_dye_system", "Likely invalid main record: not a single dye system."))
        if any(token in dye for token in ["mixture", "wastewater", "multiple dyes"]):
            warnings.append(issue("warning", record_id, source_id, "dye_name", "Dye name suggests mixture or wastewater."))
        if "review" in source_location_str and "table" in source_location_str:
            warnings.append(issue("warning", record_id, source_id, "source_location", "Source location suggests review table only."))
        if any(token in notes for token in ["hydrogen evolution", "antibacterial", "phenol only"]):
            warnings.append(issue("warning", record_id, source_id, "extraction_notes", "Snippet may be out of scope."))
        for field in ["source_id", "doi_or_url", "source_location", "value_origin"]:
            if blank(row.get(field, "")):
                errors.append(issue("error", record_id, source_id, field, "Missing provenance field."))

    return pd.DataFrame(errors), pd.DataFrame(warnings)
