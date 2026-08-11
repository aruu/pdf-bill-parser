"""Tests for src/config.py."""

import pytest

from config import (
    CONFIG_YAML_FILENAME,
    DATA_DIR,
    ENV_VAR_GSPREAD_JSON,
    OUTPUT_DIR,
    get_config,
)


def _write_config(tmp_path, content):
    (tmp_path / CONFIG_YAML_FILENAME).write_text(content)


class TestGetConfig:
    def test_raises_file_not_found_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with pytest.raises(FileNotFoundError, match=CONFIG_YAML_FILENAME):
            get_config()

    def test_applies_defaults_when_unspecified(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path, "account_mapping: []\n")

        result = get_config()

        assert result["data_dir"] == DATA_DIR
        assert result["output_dir"] == OUTPUT_DIR
        assert result["env_var_gspread_json"] == ENV_VAR_GSPREAD_JSON

    def test_preserves_explicit_overrides(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write_config(
            tmp_path,
            "data_dir: custom_data\n"
            "output_dir: custom_output\n"
            "env_var_gspread_json: CUSTOM_ENV\n",
        )

        result = get_config()

        assert result["data_dir"] == "custom_data"
        assert result["output_dir"] == "custom_output"
        assert result["env_var_gspread_json"] == "CUSTOM_ENV"

    def test_preserves_other_keys_alongside_defaults(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write_config(
            tmp_path,
            "ingest_output:\n"
            "  mode: csv\n"
            "  file_name: out.csv\n",
        )

        result = get_config()

        assert result["ingest_output"] == {"mode": "csv", "file_name": "out.csv"}
        # Defaults are still applied alongside untouched custom keys.
        assert result["data_dir"] == DATA_DIR
        assert result["output_dir"] == OUTPUT_DIR
        assert result["env_var_gspread_json"] == ENV_VAR_GSPREAD_JSON

    def test_only_reads_config_from_current_working_directory(
        self, tmp_path, monkeypatch
    ):
        other_dir = tmp_path / "elsewhere"
        other_dir.mkdir()
        _write_config(other_dir, "foo: bar\n")
        monkeypatch.chdir(tmp_path)

        with pytest.raises(FileNotFoundError):
            get_config()

    def test_empty_config_file_raises_attribute_error(self, tmp_path, monkeypatch):
        # yaml.safe_load("") returns None, and calling .setdefault() on None
        # is expected to fail loudly rather than silently return {}.
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path, "")

        with pytest.raises(AttributeError):
            get_config()