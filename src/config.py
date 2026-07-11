"""Parse the config file, using defaults for unspecified values."""

from pathlib import Path
from typing import Any

import yaml

CONFIG_YAML_FILENAME = "config.yaml"
DATA_DIR = "data"
OUTPUT_DIR = "output"


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

    return config
