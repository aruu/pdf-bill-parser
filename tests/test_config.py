"""Tests for src/config.py."""

from pathlib import Path

import pytest

import config

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path, monkeypatch):
    """Run every test in this module from an isolated, empty directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write_config(tmp_path, contents: str) -> None:
    (tmp_path / config.CONFIG_YAML_FILENAME).write_text(contents)


class TestGetConfig:
    def test_raises_file_not_found_when_config_missing(self, tmp_path):
        assert not (tmp_path / config.CONFIG_YAML_FILENAME).exists()

        with pytest.raises(FileNotFoundError, match="config.yaml"):
            config.get_config()

    def test_applies_all_defaults_when_unspecified(self, tmp_path):
        write_config(
            tmp_path,
            """
            account_mapping: []
            description_mapping: {}
            """,
        )

        result = config.get_config()

        assert result["data_dir"] == config.DATA_DIR
        assert result["output_dir"] == config.OUTPUT_DIR
        assert result["env_var_gspread_json"] == config.ENV_VAR_GSPREAD_JSON

    def test_preserves_explicit_values_over_defaults(self, tmp_path):
        write_config(
            tmp_path,
            """
            data_dir: my_data
            output_dir: my_output
            env_var_gspread_json: MY_CUSTOM_ENV_VAR
            """,
        )

        result = config.get_config()

        assert result["data_dir"] == "my_data"
        assert result["output_dir"] == "my_output"
        assert result["env_var_gspread_json"] == "MY_CUSTOM_ENV_VAR"

    def test_partial_override_only_replaces_specified_defaults(self, tmp_path):
        write_config(
            tmp_path,
            """
            data_dir: custom_data
            """,
        )

        result = config.get_config()

        assert result["data_dir"] == "custom_data"
        assert result["output_dir"] == config.OUTPUT_DIR
        assert result["env_var_gspread_json"] == config.ENV_VAR_GSPREAD_JSON

    def test_preserves_arbitrary_config_keys(self, tmp_path):
        write_config(
            tmp_path,
            """
            ingest_output:
              mode: google_sheets
              spreadsheet_name: Transactions
              worksheet_name: Documents_RAW
            """,
        )

        result = config.get_config()

        assert result["ingest_output"]["mode"] == "google_sheets"
        assert result["ingest_output"]["spreadsheet_name"] == "Transactions"
        assert result["ingest_output"]["worksheet_name"] == "Documents_RAW"

    def test_matches_config_example_yaml_shape(self, tmp_path):
        """The example config shipped in the repo should parse without error
        and produce the expected ingest_output settings."""
        contents = (REPO_ROOT / "config-example.yaml").read_text()
        write_config(tmp_path, contents)

        result = config.get_config()

        assert result["ingest_output"]["mode"] == "google_sheets"
        assert result["ingest_output"]["spreadsheet_name"] == "Transactions"
        assert result["ingest_output"]["worksheet_name"] == "Documents_RAW"
        assert result["data_dir"] == config.DATA_DIR
        assert result["output_dir"] == config.OUTPUT_DIR