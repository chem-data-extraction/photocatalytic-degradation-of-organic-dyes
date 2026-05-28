#!/usr/bin/env python3
"""
Photocatalysis Data Extraction and Cleaning Pipeline Orchestrator.
Automates the full pipeline sequentially with modular stage selection,
parameter propagation, and timestamped log directories.
"""

import os
import sys
import argparse
import subprocess
import time
from datetime import datetime

# Allow importing from scripts folder
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
from scripts.utils.logger import get_logger
from scripts.utils.env import load_dotenv

def parse_args(remaining_argv=None):
    """Parses command line arguments for the pipeline orchestrator."""
    parser = argparse.ArgumentParser(
        description="End-to-end Photocatalysis Data Extraction and Cleaning Pipeline Orchestrator."
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="config/default.yaml",
        help="Path to YAML configuration file (default: config/default.yaml)."
    )
    
    return parser.parse_args(remaining_argv)

def validate_environment(stages_to_run, yaml_config, logger):
    """Performs early sanity checks on files and environment variables."""
    has_warnings = False
    
    pipeline_conf = yaml_config.get("pipeline", {})
    stages_conf = yaml_config.get("stages", {})
    
    # Check pdf directory for PDF processing stages
    if "merge-si" in stages_to_run:
        merge_si_conf = stages_conf.get("merge_si", {})
        pdf_dir = merge_si_conf.get("pdf_dir", "data/raw/pdf")
        if not os.path.exists(pdf_dir) or not os.listdir(pdf_dir):
            logger.warning(f"The raw PDF directory '{pdf_dir}' is missing or empty. merge-si stage may have no work to do.")
            has_warnings = True
    elif "ingest" in stages_to_run:
        ingest_conf = stages_conf.get("ingest", {})
        pdf_dir = ingest_conf.get("pdf_dir", "data/interim/pdf")
        if "merge-si" not in stages_to_run:
            if not os.path.exists(pdf_dir) or not os.listdir(pdf_dir):
                logger.warning(f"The PDF directory '{pdf_dir}' is missing or empty. Ingest stage may have no work to do.")
                has_warnings = True

    # Check schema file for extraction/clean stages
    schema_stages = {"extract", "merge", "clean"}
    if any(stage in stages_to_run for stage in schema_stages):
        schema_path = pipeline_conf.get("schema_file", "schemas/schema.json")
        if not os.path.exists(schema_path):
            logger.error(f"Required schema file '{schema_path}' is missing. Aborting pipeline.")
            sys.exit(1)

    # Check API keys
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if "extract" in stages_to_run and not api_key:
        logger.error("GEMINI_API_KEY or GOOGLE_API_KEY is not set. Data extraction stage requires a Gemini API key. Aborting pipeline.")
        sys.exit(1)
        
    download_conf = stages_conf.get("download", {})
    if "download" in stages_to_run and download_conf.get("filter_mode", "llm") == "llm" and not api_key:
        logger.warning("GEMINI_API_KEY is not set, but Zenodo filter mode is set to 'llm'. The download script might bypass LLM filtering.")
        has_warnings = True

    # Check MinerU token
    if "ingest" in stages_to_run and not os.environ.get("MINERU_TOKEN"):
        logger.warning("MINERU_TOKEN is not set. MinerU will run in Flash (free/limited layout preview) mode instead of Precision Mode.")
        has_warnings = True

    if has_warnings:
        logger.info("Proceeding with pipeline execution despite warnings...\n")

def run_stage(stage_name, script_path, args_list, env, logger):
    """Executes a single pipeline stage script as an isolated subprocess."""
    banner = "=" * 80
    logger.plain(f"\n{banner}")
    logger.plain(f"Starting Stage: {stage_name.upper()} ({script_path})")
    logger.plain(f"{banner}\n")
    
    cmd = [sys.executable, script_path] + args_list
    logger.info(f"Running command: {' '.join(cmd)}")
    
    start_time = time.time()
    try:
        # Run subprocess and let output stream directly to console to maintain tty colors/progress bars
        result = subprocess.run(cmd, env=env, check=True)
        duration = time.time() - start_time
        logger.success(f"Stage '{stage_name}' completed successfully in {duration:.2f}s.")
        return "SUCCESS", duration
    except subprocess.CalledProcessError as e:
        duration = time.time() - start_time
        logger.error(f"Stage '{stage_name}' failed with exit code {e.returncode} after {duration:.2f}s.")
        return "FAILED", duration
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Failed to execute stage '{stage_name}': {e} after {duration:.2f}s.")
        return "ERROR", duration

def main():
    # Load env variables from .env
    load_dotenv()
    
    # 1. Quick parse only the --config parameter
    conf_parser = argparse.ArgumentParser(add_help=False)
    conf_parser.add_argument("--config", default="config/default.yaml")
    conf_args, remaining_argv = conf_parser.parse_known_args()
    
    # Load defaults from config
    from scripts.utils.config import load_config
    yaml_config = load_config(conf_args.config)
    
    # 2. Complete parsing of arguments
    args = parse_args(remaining_argv)
    
    # Initialize run timestamp and create a run-specific logs folder (hardcoded to 'logs')
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    pipeline_log_dir = os.path.abspath(os.path.join("logs", run_id))
    os.makedirs(pipeline_log_dir, exist_ok=True)
    
    # Configure env for subprocesses to inherit PIPELINE_LOG_DIR
    env = os.environ.copy()
    env["PIPELINE_LOG_DIR"] = pipeline_log_dir
    
    # Initialize orchestrator logger (it will log to both console and logs/run_<ts>/pipeline.log)
    logger = get_logger("pipeline", log_file=os.path.join(pipeline_log_dir, "pipeline.log"))
    
    logger.plain(f"=== Photocatalysis Pipeline Orchestrator ===")
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Log directory: {pipeline_log_dir}")
    
    # Define all available stages in order
    all_stages = [
        "merge-si",
        "ingest",
        "extract",
        "download",
        "merge",
        "clean"
    ]
    
    # Determine stages to run
    pipeline_conf = yaml_config.get("pipeline", {})
    stages_config_val = pipeline_conf.get("stages", "all")
    if not stages_config_val:
        stages_config_val = "all"
        
    if isinstance(stages_config_val, list):
        stages_to_run = [s.strip().lower() for s in stages_config_val if isinstance(s, str)]
    elif isinstance(stages_config_val, str):
        if stages_config_val.strip().lower() == "all":
            stages_to_run = all_stages.copy()
        else:
            stages_to_run = [s.strip().lower() for s in stages_config_val.split(",") if s.strip()]
    else:
        stages_to_run = all_stages.copy()
        
    # Validate selected stages
    invalid_stages = set(stages_to_run) - set(all_stages)
    if invalid_stages:
        logger.error(f"Invalid stage(s) specified in config: {', '.join(invalid_stages)}")
        logger.info(f"Available stages: {', '.join(all_stages)}")
        sys.exit(1)
            
    if not stages_to_run:
        logger.warning("No stages left to run. Exiting.")
        sys.exit(0)
        
    logger.info(f"Pipeline execution plan: {' -> '.join(stages_to_run)}")
    
    # Perform early validation checks
    validate_environment(stages_to_run, yaml_config, logger)
    
    # Get stage configuration dictionary
    stages_conf = yaml_config.get("stages", {})
    ingest_conf = stages_conf.get("ingest", {})
    extract_conf = stages_conf.get("extract", {})
    
    # Propagate force options for ingest and extract stages
    ingest_force = ingest_conf.get("force", False)
    extract_force = extract_conf.get("force", False)
    
    # Map stage names to script paths and arguments
    stage_configs = {
        "merge-si": {
            "script": "scripts/merge_si.py",
            "args": ["--config", conf_args.config]
        },
        "ingest": {
            "script": "scripts/ingest.py",
            "args": ["--config", conf_args.config] + (["--force"] if ingest_force else [])
        },
        "extract": {
            "script": "scripts/extract.py",
            "args": ["--config", conf_args.config] + (["--force"] if extract_force else [])
        },
        "download": {
            "script": "scripts/download_zenodo.py",
            "args": ["--config", conf_args.config]
        },
        "merge": {
            "script": "scripts/merge_extracted.py",
            "args": ["--config", conf_args.config]
        },
        "clean": {
            "script": "scripts/clean_and_validate.py",
            "args": ["--config", conf_args.config]
        }
    }
    
    results = {}
    total_start_time = time.time()
    aborted = False
    
    # Execute stages sequentially
    for stage in stages_to_run:
        config = stage_configs[stage]
        status, duration = run_stage(
            stage_name=stage,
            script_path=config["script"],
            args_list=config["args"],
            env=env,
            logger=logger
        )
        
        results[stage] = {
            "status": status,
            "duration": duration,
            "log": os.path.join(pipeline_log_dir, f"{os.path.basename(config['script']).replace('.py', '.log')}")
        }
        
        if status != "SUCCESS":
            logger.error(f"Pipeline execution aborted at stage '{stage}'.")
            aborted = True
            break
            
    total_duration = time.time() - total_start_time
    
    # Log any skipped/unexecuted stages in the final table
    for stage in all_stages:
        if stage not in results:
            results[stage] = {
                "status": "SKIPPED",
                "duration": 0.0,
                "log": "N/A"
            }
            
    # Print the Final Summary Table
    banner = "=" * 80
    logger.plain(f"\n{banner}")
    logger.plain(f"Pipeline Run Summary ({run_id})")
    logger.plain(f"{banner}")
    logger.plain(f"{'Stage':<15} | {'Status':<10} | {'Duration':<10} | {'Log File'}")
    logger.plain("-" * 80)
    for stage in all_stages:
        res = results[stage]
        status_str = res["status"]
        dur_str = f"{res['duration']:.2f}s" if res["status"] != "SKIPPED" else "-"
        log_path = os.path.relpath(res["log"]) if res["log"] != "N/A" else "-"
        logger.plain(f"{stage:<15} | {status_str:<10} | {dur_str:<10} | {log_path}")
    logger.plain("-" * 80)
    logger.plain(f"Total Duration: {total_duration:.2f}s")
    
    if aborted:
        logger.error("Pipeline run failed.")
        sys.exit(1)
    else:
        logger.success("Pipeline run finished successfully!")
        final_csv = yaml_config.get("stages", {}).get("clean", {}).get("output_file", "data/processed/final_cleaned_dataset.csv")
        logger.info(f"Final cleaned dataset is saved at: {final_csv}")

if __name__ == "__main__":
    main()
