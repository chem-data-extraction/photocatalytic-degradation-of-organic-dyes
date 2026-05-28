import os
import sys

try:
    import yaml
except ImportError:
    yaml = None

def load_config(config_path="config/default.yaml"):
    """Loads configuration from a YAML file."""
    if not os.path.exists(config_path):
        return {}
    if yaml is None:
        print("Warning: 'pyyaml' is not installed. Using built-in defaults.", file=sys.stderr)
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Error loading config file '{config_path}': {e}", file=sys.stderr)
        return {}

def get_config_and_argv():
    """Helper to parse --config, load YAML config, and return them with remaining argv."""
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", default="config/default.yaml", help="Path to config file")
    args, remaining_argv = parser.parse_known_args()
    config_dict = load_config(args.config)
    return config_dict, args.config, remaining_argv

