"""Tests for src/ingest.py."""

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

import ingest

TEMPLATE_COLUMNS = ["account", "document", "pages"]


def _make_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4 fake pdf content")


class TestInitializeOutputCsv:
    def test_creates_file_with_template_header_when_missing(self, tmp_path):
        ingest.initialize_output_csv(str(tmp_path), "out.csv")

        output_path = tmp_path / "out.csv"
        assert output_path.exists()
        df = pd.read_csv(output_path)
        assert list(df.columns) == TEMPLATE_COLUMNS
        assert df.empty

    def test_creates_parent_directories_when_missing(self, tmp_path):
        nested_dir = tmp_path / "nested" / "dir"

        ingest.initialize_output_csv(str(nested_dir), "out.csv")

        assert (nested_dir / "out.csv").exists()

    def test_does_not_overwrite_existing_file(self, tmp_path):
        output_path = tmp_path / "out.csv"
        output_path.write_text("account,document,pages\nacc1,doc1,{}\n")

        ingest.initialize_output_csv(str(tmp_path), "out.csv")

        assert output_path.read_text() == "account,document,pages\nacc1,doc1,{}\n"


class TestFetchDocumentIdsCsv:
    def test_returns_unique_account_document_pairs(self, tmp_path):
        output_path = tmp_path / "out.csv"
        output_path.write_text(
            "account,document,pages\n"
            "acc1,doc1,{}\n"
            "acc1,doc1,{}\n"
            "acc2,doc2,{}\n"
        )

        result = ingest.fetch_document_ids_csv(str(tmp_path), "out.csv")

        assert list(result.columns) == ["account", "document"]
        assert len(result) == 2
        assert set(map(tuple, result.to_numpy())) == {
            ("acc1", "doc1"),
            ("acc2", "doc2"),
        }

    def test_returns_empty_frame_for_empty_csv(self, tmp_path):
        output_path = tmp_path / "out.csv"
        output_path.write_text("account,document,pages\n")

        result = ingest.fetch_document_ids_csv(str(tmp_path), "out.csv")

        assert list(result.columns) == ["account", "document"]
        assert result.empty


class TestAppendCsv:
    def test_appends_rows_when_header_matches(self, tmp_path):
        output_path = tmp_path / "out.csv"
        output_path.write_text("account,document,pages\n")
        new_rows = pd.DataFrame([{"account": "acc1", "document": "doc1", "pages": "{}"}])

        ingest.append_csv(str(tmp_path), "out.csv", new_rows)

        result = pd.read_csv(output_path)
        assert len(result) == 1
        assert result.iloc[0]["account"] == "acc1"
        assert result.iloc[0]["document"] == "doc1"

    def test_raises_value_error_on_header_mismatch(self, tmp_path):
        output_path = tmp_path / "out.csv"
        output_path.write_text("account,document,pages\n")
        new_rows = pd.DataFrame([{"account": "acc1", "wrong_column": "x"}])

        with pytest.raises(ValueError, match="does not match"):
            ingest.append_csv(str(tmp_path), "out.csv", new_rows)

    def test_appends_nothing_for_empty_dataframe(self, tmp_path):
        output_path = tmp_path / "out.csv"
        output_path.write_text("account,document,pages\n")
        empty_df = pd.DataFrame(columns=TEMPLATE_COLUMNS)

        ingest.append_csv(str(tmp_path), "out.csv", empty_df)

        result = pd.read_csv(output_path)
        assert result.empty


class TestInitializeOutputGoogleSheets:
    def test_initializes_worksheet_when_missing(self, monkeypatch):
        mock_gc = MagicMock()
        monkeypatch.setattr(ingest.gs, "connect", lambda: mock_gc)
        monkeypatch.setattr(ingest.gs, "list_worksheets", lambda gc, name: ["Other"])
        mock_init = MagicMock()
        monkeypatch.setattr(ingest.gs, "initialize_worksheet", mock_init)

        ingest.initialize_output_google_sheets("Sheet1", "NewTab")

        mock_init.assert_called_once()
        call_args = mock_init.call_args[0]
        assert call_args[0] is mock_gc
        assert call_args[1] == "Sheet1"
        assert call_args[2] == "NewTab"
        assert call_args[3] is ingest.TEMPLATE_RECORD

    def test_skips_initialization_when_worksheet_exists(self, monkeypatch):
        mock_gc = MagicMock()
        monkeypatch.setattr(ingest.gs, "connect", lambda: mock_gc)
        monkeypatch.setattr(
            ingest.gs, "list_worksheets", lambda gc, name: ["ExistingTab"]
        )
        mock_init = MagicMock()
        monkeypatch.setattr(ingest.gs, "initialize_worksheet", mock_init)

        ingest.initialize_output_google_sheets("Sheet1", "ExistingTab")

        mock_init.assert_not_called()


class TestFetchDocumentIdsGoogleSheets:
    def test_returns_unique_account_document_pairs(self, monkeypatch):
        mock_gc = MagicMock()
        monkeypatch.setattr(ingest.gs, "connect", lambda: mock_gc)
        fetched = pd.DataFrame(
            [
                {"account": "acc1", "document": "doc1", "pages": "{}"},
                {"account": "acc1", "document": "doc1", "pages": "{}"},
            ]
        )
        monkeypatch.setattr(
            ingest.gs, "fetch_df", lambda gc, spreadsheet, worksheet: fetched
        )

        result = ingest.fetch_document_ids_google_sheets("Sheet1", "Tab1")

        assert list(result.columns) == ["account", "document"]
        assert len(result) == 1


class TestAppendGoogleSheets:
    def test_delegates_to_google_sheets_append(self, monkeypatch):
        mock_gc = MagicMock()
        monkeypatch.setattr(ingest.gs, "connect", lambda: mock_gc)
        mock_append = MagicMock()
        monkeypatch.setattr(ingest.gs, "append", mock_append)
        df = pd.DataFrame([{"account": "acc1", "document": "doc1", "pages": "{}"}])

        ingest.append_google_sheets("Sheet1", "Tab1", df)

        mock_append.assert_called_once()
        call_args = mock_append.call_args[0]
        assert call_args[0] is mock_gc
        assert call_args[1] == "Sheet1"
        assert call_args[2] == "Tab1"
        assert call_args[3] is df


class TestExtractPdfPages:
    def test_returns_json_mapping_page_index_to_text(self, monkeypatch, tmp_path):
        fake_page_0 = MagicMock()
        fake_page_0.get_text.return_value = "Page one text"
        fake_page_1 = MagicMock()
        fake_page_1.get_text.return_value = "Page two text"

        fake_doc = MagicMock()
        fake_doc.pages.return_value = iter([fake_page_0, fake_page_1])
        fake_doc.__enter__.return_value = fake_doc
        fake_doc.__exit__.return_value = False

        mock_open = MagicMock(return_value=fake_doc)
        monkeypatch.setattr(ingest.pymupdf, "open", mock_open)

        doc_path = tmp_path / "sample.pdf"
        result = ingest.extract_pdf_pages(doc_path)

        mock_open.assert_called_once_with(doc_path)
        assert json.loads(result) == {"0": "Page one text", "1": "Page two text"}

    def test_returns_empty_object_when_document_has_no_pages(
        self, monkeypatch, tmp_path
    ):
        fake_doc = MagicMock()
        fake_doc.pages.return_value = iter([])
        fake_doc.__enter__.return_value = fake_doc
        fake_doc.__exit__.return_value = False
        monkeypatch.setattr(ingest.pymupdf, "open", MagicMock(return_value=fake_doc))

        result = ingest.extract_pdf_pages(tmp_path / "empty.pdf")

        assert json.loads(result) == {}


class TestIngestPdfsValidation:
    def test_raises_for_invalid_output_mode(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid output mode"):
            ingest.ingest_pdfs(data_dir=str(tmp_path), output_mode="xml")

    def test_raises_when_csv_mode_missing_output_dir(self, tmp_path):
        with pytest.raises(ValueError, match="output_dir is required"):
            ingest.ingest_pdfs(data_dir=str(tmp_path), output_mode="csv")

    def test_raises_when_google_sheets_mode_missing_spreadsheet(self, tmp_path):
        with pytest.raises(
            ValueError, match="output_spreadsheet and output_worksheet"
        ):
            ingest.ingest_pdfs(
                data_dir=str(tmp_path),
                output_mode="google_sheets",
                output_worksheet="Tab1",
            )

    def test_raises_when_google_sheets_mode_missing_worksheet(self, tmp_path):
        with pytest.raises(
            ValueError, match="output_spreadsheet and output_worksheet"
        ):
            ingest.ingest_pdfs(
                data_dir=str(tmp_path),
                output_mode="google_sheets",
                output_spreadsheet="Sheet1",
            )


class TestIngestPdfsCsvMode:
    def test_ingests_only_new_documents(self, tmp_path, monkeypatch, caplog):
        data_dir = tmp_path / "data"
        _make_pdf(data_dir / "account1" / "doc1.pdf")
        _make_pdf(data_dir / "account1" / "doc2.pdf")
        _make_pdf(data_dir / "account2" / "doc3.pdf")
        # Non-pdf files and files directly under data_dir (not one level
        # nested under an account folder) must be ignored by the glob.
        (data_dir / "account1" / "notes.txt").write_text("ignore me")
        (data_dir / "top_level.pdf").write_bytes(b"%PDF ignore")

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "ingest_output.csv").write_text(
            "account,document,pages\naccount1,doc1.pdf,{}\n"
        )

        monkeypatch.setattr(
            ingest, "extract_pdf_pages", lambda path: json.dumps({"0": path.name})
        )

        with caplog.at_level(logging.INFO):
            ingest.ingest_pdfs(
                data_dir=str(data_dir),
                output_mode="csv",
                output_dir=str(output_dir),
            )

        result = pd.read_csv(output_dir / "ingest_output.csv")
        assert len(result) == 3
        ingested_pairs = set(map(tuple, result[["account", "document"]].to_numpy()))
        assert ingested_pairs == {
            ("account1", "doc1.pdf"),
            ("account1", "doc2.pdf"),
            ("account2", "doc3.pdf"),
        }
        assert "Ingested 2 new documents" in caplog.text

    def test_initializes_output_file_when_missing_and_no_pdfs_found(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        output_dir = tmp_path / "output"

        ingest.ingest_pdfs(
            data_dir=str(data_dir),
            output_mode="csv",
            output_dir=str(output_dir),
        )

        output_path = output_dir / "ingest_output.csv"
        assert output_path.exists()
        result = pd.read_csv(output_path)
        assert result.empty
        assert list(result.columns) == TEMPLATE_COLUMNS

    def test_respects_custom_output_file_name(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        output_dir = tmp_path / "output"

        ingest.ingest_pdfs(
            data_dir=str(data_dir),
            output_mode="csv",
            output_dir=str(output_dir),
            output_file="custom_name.csv",
        )

        assert (output_dir / "custom_name.csv").exists()
        assert not (output_dir / "ingest_output.csv").exists()


class TestIngestPdfsGoogleSheetsMode:
    def test_ingests_only_new_documents(self, tmp_path, monkeypatch):
        data_dir = tmp_path / "data"
        _make_pdf(data_dir / "account1" / "doc1.pdf")
        _make_pdf(data_dir / "account1" / "doc2.pdf")

        mock_gc = MagicMock()
        monkeypatch.setattr(ingest.gs, "connect", lambda: mock_gc)
        monkeypatch.setattr(
            ingest.gs, "list_worksheets", lambda gc, name: ["Documents_RAW"]
        )
        mock_initialize_worksheet = MagicMock()
        monkeypatch.setattr(
            ingest.gs, "initialize_worksheet", mock_initialize_worksheet
        )
        existing = pd.DataFrame([{"account": "account1", "document": "doc1.pdf"}])
        monkeypatch.setattr(
            ingest.gs, "fetch_df", lambda gc, spreadsheet, worksheet: existing
        )
        mock_append = MagicMock()
        monkeypatch.setattr(ingest.gs, "append", mock_append)
        monkeypatch.setattr(
            ingest, "extract_pdf_pages", lambda path: json.dumps({"0": path.name})
        )

        ingest.ingest_pdfs(
            data_dir=str(data_dir),
            output_mode="google_sheets",
            output_spreadsheet="Transactions",
            output_worksheet="Documents_RAW",
        )

        mock_initialize_worksheet.assert_not_called()
        mock_append.assert_called_once()
        call_args = mock_append.call_args[0]
        assert call_args[0] is mock_gc
        assert call_args[1] == "Transactions"
        assert call_args[2] == "Documents_RAW"
        appended_df = call_args[3]
        assert appended_df[["account", "document"]].to_numpy().tolist() == [
            ["account1", "doc2.pdf"]
        ]

    def test_initializes_worksheet_when_missing(self, tmp_path, monkeypatch):
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        mock_gc = MagicMock()
        monkeypatch.setattr(ingest.gs, "connect", lambda: mock_gc)
        monkeypatch.setattr(ingest.gs, "list_worksheets", lambda gc, name: [])
        mock_initialize_worksheet = MagicMock()
        monkeypatch.setattr(
            ingest.gs, "initialize_worksheet", mock_initialize_worksheet
        )
        monkeypatch.setattr(
            ingest.gs,
            "fetch_df",
            lambda gc, spreadsheet, worksheet: pd.DataFrame(
                columns=["account", "document"]
            ),
        )
        mock_append = MagicMock()
        monkeypatch.setattr(ingest.gs, "append", mock_append)

        ingest.ingest_pdfs(
            data_dir=str(data_dir),
            output_mode="google_sheets",
            output_spreadsheet="Transactions",
            output_worksheet="Documents_RAW",
        )

        mock_initialize_worksheet.assert_called_once()
        call_args = mock_initialize_worksheet.call_args[0]
        assert call_args[0] is mock_gc
        assert call_args[1] == "Transactions"
        assert call_args[2] == "Documents_RAW"
        assert call_args[3] is ingest.TEMPLATE_RECORD
        mock_append.assert_called_once()