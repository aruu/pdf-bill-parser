"""Parse the config file, using defaults for unspecified values."""

from pathlib import Path
from typing import Any

import yaml

CONFIG_YAML_FILENAME = "config.yaml"
DATA_DIR = "data"
OUTPUT_DIR = "output"

# Expected environment variables are specified here primarily so that all hard-coded
# values are in one place, not because it actually needs to be adjusted.
# Rather, all global locations, env vars, etc will be referenced from the config object.
ENV_VAR_GSPREAD_JSON = "GSPREAD_JSON"


def get_config() -> dict[str, Any]:
    """Parse the config file, using defaults for unspecified values."""
    config_path = Path(CONFIG_YAML_FILENAME)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file {CONFIG_YAML_FILENAME} not found.")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Use default values for unspecified config values
    config.setdefault("data_dir", DATA_DIR)
    config.setdefault("output_dir", OUTPUT_DIR)
    config.setdefault("env_var_gspread_json", ENV_VAR_GSPREAD_JSON)

    return config
