"""Tests for src/google_sheets.py."""

import json
from unittest.mock import MagicMock

import pandas as pd
import pytest

import google_sheets


class TestConnect:
    def test_builds_client_from_env_credentials(self, monkeypatch):
        creds = {"type": "service_account", "project_id": "proj"}
        monkeypatch.setattr(
            google_sheets,
            "get_config",
            lambda: {"env_var_gspread_json": "TEST_GSPREAD_JSON"},
        )
        monkeypatch.setenv("TEST_GSPREAD_JSON", json.dumps(creds))
        sentinel_client = object()
        mock_factory = MagicMock(return_value=sentinel_client)
        monkeypatch.setattr(
            google_sheets.gspread, "service_account_from_dict", mock_factory
        )

        result = google_sheets.connect()

        mock_factory.assert_called_once_with(creds)
        assert result is sentinel_client

    def test_raises_key_error_when_env_var_missing(self, monkeypatch):
        monkeypatch.setattr(
            google_sheets,
            "get_config",
            lambda: {"env_var_gspread_json": "MISSING_ENV_VAR"},
        )
        monkeypatch.delenv("MISSING_ENV_VAR", raising=False)

        with pytest.raises(KeyError):
            google_sheets.connect()

    def test_raises_json_decode_error_for_malformed_credentials(self, monkeypatch):
        monkeypatch.setattr(
            google_sheets,
            "get_config",
            lambda: {"env_var_gspread_json": "TEST_GSPREAD_JSON"},
        )
        monkeypatch.setenv("TEST_GSPREAD_JSON", "not-valid-json")

        with pytest.raises(json.JSONDecodeError):
            google_sheets.connect()


class TestInitializeWorksheet:
    def test_creates_worksheet_with_header_row(self):
        df = pd.DataFrame(columns=["account", "document", "pages"])
        mock_ws = MagicMock()
        mock_sh = MagicMock()
        mock_sh.add_worksheet.return_value = mock_ws
        mock_gc = MagicMock()
        mock_gc.open.return_value = mock_sh

        google_sheets.initialize_worksheet(mock_gc, "MySheet", "NewTab", df)

        mock_gc.open.assert_called_once_with("MySheet")
        mock_sh.add_worksheet.assert_called_once_with("NewTab", rows=1, cols=3)
        mock_ws.update.assert_called_once_with([["account", "document", "pages"]])


class TestListWorksheets:
    def test_returns_worksheet_titles(self):
        mock_ws1 = MagicMock(title="Sheet1")
        mock_ws2 = MagicMock(title="Sheet2")
        mock_sh = MagicMock()
        mock_sh.worksheets.return_value = [mock_ws1, mock_ws2]
        mock_gc = MagicMock()
        mock_gc.open.return_value = mock_sh

        result = google_sheets.list_worksheets(mock_gc, "MySheet")

        assert result == ["Sheet1", "Sheet2"]
        mock_gc.open.assert_called_once_with("MySheet")

    def test_returns_empty_list_when_no_worksheets(self):
        mock_sh = MagicMock()
        mock_sh.worksheets.return_value = []
        mock_gc = MagicMock()
        mock_gc.open.return_value = mock_sh

        assert google_sheets.list_worksheets(mock_gc, "MySheet") == []


class TestFetchDf:
    def test_returns_dataframe_with_worksheet_header(self):
        records = [
            {"account": "acc1", "document": "doc1"},
            {"account": "acc2", "document": "doc2"},
        ]
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = records
        mock_ws.row_values.return_value = ["account", "document"]
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws
        mock_gc = MagicMock()
        mock_gc.open.return_value = mock_sh

        result = google_sheets.fetch_df(mock_gc, "MySheet", "Tab1")

        expected = pd.DataFrame(records, columns=["account", "document"])
        pd.testing.assert_frame_equal(result, expected)
        mock_gc.open.assert_called_once_with("MySheet")
        mock_sh.worksheet.assert_called_once_with("Tab1")

    def test_returns_empty_dataframe_when_no_records(self):
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = []
        mock_ws.row_values.return_value = ["account", "document"]
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws
        mock_gc = MagicMock()
        mock_gc.open.return_value = mock_sh

        result = google_sheets.fetch_df(mock_gc, "MySheet", "Tab1")

        assert list(result.columns) == ["account", "document"]
        assert result.empty


class TestAppend:
    def test_appends_rows_when_header_matches(self):
        df = pd.DataFrame([{"account": "acc1", "document": "doc1"}])
        mock_ws = MagicMock()
        mock_ws.row_values.return_value = ["account", "document"]
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws
        mock_gc = MagicMock()
        mock_gc.open.return_value = mock_sh

        google_sheets.append(mock_gc, "MySheet", "Tab1", df)

        mock_ws.append_rows.assert_called_once_with([["acc1", "doc1"]])

    def test_raises_value_error_when_header_mismatch(self):
        df = pd.DataFrame([{"account": "acc1", "document": "doc1"}])
        mock_ws = MagicMock()
        mock_ws.row_values.return_value = ["account", "different_column"]
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws
        mock_gc = MagicMock()
        mock_gc.open.return_value = mock_sh

        with pytest.raises(ValueError, match="does not match"):
            google_sheets.append(mock_gc, "MySheet", "Tab1", df)

        mock_ws.append_rows.assert_not_called()

    def test_appends_multiple_rows_in_order(self):
        df = pd.DataFrame(
            [
                {"account": "acc1", "document": "doc1"},
                {"account": "acc2", "document": "doc2"},
            ]
        )
        mock_ws = MagicMock()
        mock_ws.row_values.return_value = ["account", "document"]
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws
        mock_gc = MagicMock()
        mock_gc.open.return_value = mock_sh

        google_sheets.append(mock_gc, "MySheet", "Tab1", df)

        mock_ws.append_rows.assert_called_once_with(
            [["acc1", "doc1"], ["acc2", "doc2"]]
        )