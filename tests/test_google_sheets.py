"""Tests for src/google_sheets.py."""

import json
from unittest.mock import MagicMock

import pandas as pd
import pytest

import google_sheets as gs


class TestConnect:
    def test_connect_parses_credentials_and_returns_client(self, monkeypatch):
        credentials = {"type": "service_account", "project_id": "my-project"}
        monkeypatch.setattr(
            gs,
            "get_config",
            lambda: {"env_var_gspread_json": "MY_GSPREAD_ENV"},
        )
        monkeypatch.setenv("MY_GSPREAD_ENV", json.dumps(credentials))

        fake_client = MagicMock(name="gspread_client")
        mock_from_dict = MagicMock(return_value=fake_client)
        monkeypatch.setattr(gs.gspread, "service_account_from_dict", mock_from_dict)

        result = gs.connect()

        mock_from_dict.assert_called_once_with(credentials)
        assert result is fake_client

    def test_connect_raises_when_env_var_missing(self, monkeypatch):
        monkeypatch.setattr(
            gs,
            "get_config",
            lambda: {"env_var_gspread_json": "UNSET_ENV_VAR"},
        )
        monkeypatch.delenv("UNSET_ENV_VAR", raising=False)

        with pytest.raises(KeyError):
            gs.connect()

    def test_connect_raises_on_invalid_json(self, monkeypatch):
        monkeypatch.setattr(
            gs,
            "get_config",
            lambda: {"env_var_gspread_json": "BAD_JSON_ENV"},
        )
        monkeypatch.setenv("BAD_JSON_ENV", "not valid json")

        with pytest.raises(json.JSONDecodeError):
            gs.connect()


class TestInitializeWorksheet:
    def test_creates_worksheet_with_correct_dimensions_and_header(self):
        df = pd.DataFrame(columns=["account", "document", "pages"])
        mock_ws = MagicMock()
        mock_sh = MagicMock()
        mock_sh.add_worksheet.return_value = mock_ws
        mock_gc = MagicMock()
        mock_gc.open.return_value = mock_sh

        gs.initialize_worksheet(mock_gc, "MySpreadsheet", "MyWorksheet", df)

        mock_gc.open.assert_called_once_with("MySpreadsheet")
        mock_sh.add_worksheet.assert_called_once_with("MyWorksheet", rows=1, cols=3)
        mock_ws.update.assert_called_once_with([["account", "document", "pages"]])

    def test_handles_empty_column_dataframe(self):
        df = pd.DataFrame()
        mock_ws = MagicMock()
        mock_sh = MagicMock()
        mock_sh.add_worksheet.return_value = mock_ws
        mock_gc = MagicMock()
        mock_gc.open.return_value = mock_sh

        gs.initialize_worksheet(mock_gc, "MySpreadsheet", "MyWorksheet", df)

        mock_sh.add_worksheet.assert_called_once_with("MyWorksheet", rows=1, cols=0)
        mock_ws.update.assert_called_once_with([[]])


class TestListWorksheets:
    def test_returns_titles_of_all_worksheets(self):
        ws1 = MagicMock(title="Sheet1")
        ws2 = MagicMock(title="Documents_RAW")
        mock_sh = MagicMock()
        mock_sh.worksheets.return_value = [ws1, ws2]
        mock_gc = MagicMock()
        mock_gc.open.return_value = mock_sh

        result = gs.list_worksheets(mock_gc, "MySpreadsheet")

        mock_gc.open.assert_called_once_with("MySpreadsheet")
        assert result == ["Sheet1", "Documents_RAW"]

    def test_returns_empty_list_when_no_worksheets(self):
        mock_sh = MagicMock()
        mock_sh.worksheets.return_value = []
        mock_gc = MagicMock()
        mock_gc.open.return_value = mock_sh

        result = gs.list_worksheets(mock_gc, "MySpreadsheet")

        assert result == []


class TestFetchDf:
    def test_builds_dataframe_from_records_and_header(self):
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = [
            {"account": "acc1", "document": "doc1.pdf", "pages": "{}"},
            {"account": "acc2", "document": "doc2.pdf", "pages": "{}"},
        ]
        mock_ws.row_values.return_value = ["account", "document", "pages"]
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws
        mock_gc = MagicMock()
        mock_gc.open.return_value = mock_sh

        result = gs.fetch_df(mock_gc, "MySpreadsheet", "MyWorksheet")

        mock_gc.open.assert_called_once_with("MySpreadsheet")
        mock_sh.worksheet.assert_called_once_with("MyWorksheet")
        mock_ws.row_values.assert_called_once_with(1)
        assert list(result.columns) == ["account", "document", "pages"]
        assert len(result) == 2
        assert result.iloc[0]["account"] == "acc1"

    def test_returns_empty_dataframe_with_header_when_no_records(self):
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = []
        mock_ws.row_values.return_value = ["account", "document", "pages"]
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws
        mock_gc = MagicMock()
        mock_gc.open.return_value = mock_sh

        result = gs.fetch_df(mock_gc, "MySpreadsheet", "MyWorksheet")

        assert list(result.columns) == ["account", "document", "pages"]
        assert len(result) == 0


class TestAppend:
    def test_appends_rows_when_header_matches(self):
        df = pd.DataFrame(
            [{"account": "acc1", "document": "doc1.pdf", "pages": "{}"}]
        )
        mock_ws = MagicMock()
        mock_ws.row_values.return_value = ["account", "document", "pages"]
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws
        mock_gc = MagicMock()
        mock_gc.open.return_value = mock_sh

        gs.append(mock_gc, "MySpreadsheet", "MyWorksheet", df)

        mock_gc.open.assert_called_once_with("MySpreadsheet")
        mock_sh.worksheet.assert_called_once_with("MyWorksheet")
        mock_ws.append_rows.assert_called_once_with(
            [["acc1", "doc1.pdf", "{}"]]
        )

    def test_raises_value_error_when_header_mismatches(self):
        df = pd.DataFrame(
            [{"account": "acc1", "document": "doc1.pdf"}]
        )
        mock_ws = MagicMock()
        mock_ws.row_values.return_value = ["account", "document", "pages"]
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws
        mock_gc = MagicMock()
        mock_gc.open.return_value = mock_sh

        with pytest.raises(ValueError, match="does not match"):
            gs.append(mock_gc, "MySpreadsheet", "MyWorksheet", df)

        mock_ws.append_rows.assert_not_called()

    def test_does_not_append_when_dataframe_is_empty(self):
        df = pd.DataFrame(columns=["account", "document", "pages"])
        mock_ws = MagicMock()
        mock_ws.row_values.return_value = ["account", "document", "pages"]
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws
        mock_gc = MagicMock()
        mock_gc.open.return_value = mock_sh

        gs.append(mock_gc, "MySpreadsheet", "MyWorksheet", df)

        mock_ws.append_rows.assert_called_once_with([])