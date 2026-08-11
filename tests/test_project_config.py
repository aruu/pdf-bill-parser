"""Sanity checks for project configuration files changed in this PR.

These are not behavioral unit tests of application code, but lightweight
validation that the configuration files are syntactically valid and contain
the expected new settings (e.g. the `gspread` dependency and the
`ingest_output` config block).
"""

import json
import re
import tomllib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestPipfile:
    def test_is_valid_toml_and_declares_gspread_dependency(self):
        contents = (REPO_ROOT / "Pipfile").read_text()
        parsed = tomllib.loads(contents)

        assert "gspread" in parsed["packages"]

    def test_declares_expected_packages(self):
        contents = (REPO_ROOT / "Pipfile").read_text()
        parsed = tomllib.loads(contents)

        for package in ("pymupdf", "pandas", "pyyaml", "gspread"):
            assert package in parsed["packages"]


class TestPipfileLock:
    def test_is_valid_json(self):
        contents = (REPO_ROOT / "Pipfile.lock").read_text()
        parsed = json.loads(contents)

        assert "default" in parsed

    def test_gspread_is_locked_and_matches_pipfile_source(self):
        lock = json.loads((REPO_ROOT / "Pipfile.lock").read_text())

        assert "gspread" in lock["default"]
        assert "version" in lock["default"]["gspread"]
        assert lock["default"]["gspread"]["version"].startswith("==")

    def test_lock_includes_all_pipfile_packages(self):
        pipfile = tomllib.loads((REPO_ROOT / "Pipfile").read_text())
        lock = json.loads((REPO_ROOT / "Pipfile.lock").read_text())

        for package in pipfile["packages"]:
            assert package in lock["default"], f"{package} missing from Pipfile.lock"


class TestConfigExampleYaml:
    def test_declares_google_sheets_ingest_output(self):
        contents = (REPO_ROOT / "config-example.yaml").read_text()
        parsed = yaml.safe_load(contents)

        assert parsed["ingest_output"]["mode"] == "google_sheets"
        assert parsed["ingest_output"]["spreadsheet_name"] == "Transactions"
        assert parsed["ingest_output"]["worksheet_name"] == "Documents_RAW"

    def test_preserves_preexisting_mapping_sections(self):
        contents = (REPO_ROOT / "config-example.yaml").read_text()
        parsed = yaml.safe_load(contents)

        assert "account_mapping" in parsed
        assert "description_mapping" in parsed


class TestDevcontainerJson:
    """devcontainer.json permits `//` comments (JSONC), so it is parsed with
    comments stripped rather than a strict JSON parser."""

    @staticmethod
    def _load_jsonc(text: str) -> dict:
        without_comments = re.sub(r"//.*", "", text)
        return json.loads(without_comments)

    def test_is_valid_jsonc(self):
        contents = (REPO_ROOT / ".devcontainer" / "devcontainer.json").read_text()
        parsed = self._load_jsonc(contents)

        assert parsed["name"] == "pdf-bill-parser"

    def test_declares_pytest_settings(self):
        contents = (REPO_ROOT / ".devcontainer" / "devcontainer.json").read_text()
        parsed = self._load_jsonc(contents)

        settings = parsed["customizations"]["vscode"]["settings"]
        assert settings["python.testing.pytestEnabled"] is True
        assert settings["python.testing.unittestEnabled"] is False
        assert settings["python.testing.pytestArgs"] == ["tests"]

    def test_declares_pipenv_environment_manager(self):
        contents = (REPO_ROOT / ".devcontainer" / "devcontainer.json").read_text()
        parsed = self._load_jsonc(contents)

        settings = parsed["customizations"]["vscode"]["settings"]
        assert settings["python-envs.defaultEnvManager"] == "ms-python.python:pipenv"

    def test_preserves_existing_extensions(self):
        contents = (REPO_ROOT / ".devcontainer" / "devcontainer.json").read_text()
        parsed = self._load_jsonc(contents)

        extensions = parsed["customizations"]["vscode"]["extensions"]
        assert "charliermarsh.ruff" in extensions
        assert "redhat.vscode-yaml" in extensions