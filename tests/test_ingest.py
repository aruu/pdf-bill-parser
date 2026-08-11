"""Tests for src/ingest.py."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

import ingest


def _make_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4 fake pdf content")


class TestInitializeOutputCsv:
    def test_creates_file_with_header_when_missing(self, tmp_path):
        output_dir = tmp_path / "output"

        ingest.initialize_output_csv(str(output_dir), "ingest_output.csv")

        output_path = output_dir / "ingest_output.csv"
        assert output_path.exists()
        assert output_path.read_text().strip() == "account,document,pages"

    def test_creates_parent_directories(self, tmp_path):
        output_dir = tmp_path / "nested" / "output"

        ingest.initialize_output_csv(str(output_dir), "ingest_output.csv")

        assert (output_dir / "ingest_output.csv").exists()

    def test_does_not_overwrite_existing_file(self, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        output_path = output_dir / "ingest_output.csv"
        output_path.write_text("account,document,pages\nacc1,doc1.pdf,{}\n")

        ingest.initialize_output_csv(str(output_dir), "ingest_output.csv")

        assert output_path.read_text() == "account,document,pages\nacc1,doc1.pdf,{}\n"


class TestInitializeOutputGoogleSheets:
    def test_initializes_worksheet_when_missing(self, monkeypatch):
        fake_gc = MagicMock()
        monkeypatch.setattr(ingest.gs, "connect", MagicMock(return_value=fake_gc))
        monkeypatch.setattr(
            ingest.gs, "list_worksheets", MagicMock(return_value=["OtherSheet"])
        )
        mock_init_ws = MagicMock()
        monkeypatch.setattr(ingest.gs, "initialize_worksheet", mock_init_ws)

        ingest.initialize_output_google_sheets("Transactions", "Documents_RAW")

        ingest.gs.list_worksheets.assert_called_once_with(fake_gc, "Transactions")
        mock_init_ws.assert_called_once_with(
            fake_gc, "Transactions", "Documents_RAW", ingest.TEMPLATE_RECORD
        )

    def test_does_not_reinitialize_existing_worksheet(self, monkeypatch):
        fake_gc = MagicMock()
        monkeypatch.setattr(ingest.gs, "connect", MagicMock(return_value=fake_gc))
        monkeypatch.setattr(
            ingest.gs, "list_worksheets", MagicMock(return_value=["Documents_RAW"])
        )
        mock_init_ws = MagicMock()
        monkeypatch.setattr(ingest.gs, "initialize_worksheet", mock_init_ws)

        ingest.initialize_output_google_sheets("Transactions", "Documents_RAW")

        mock_init_ws.assert_not_called()


class TestFetchDocumentIdsCsv:
    def test_returns_unique_account_document_pairs(self, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        output_path = output_dir / "ingest_output.csv"
        output_path.write_text(
            "account,document,pages\n"
            "acc1,doc1.pdf,{}\n"
            "acc1,doc1.pdf,{}\n"
            "acc2,doc2.pdf,{}\n"
        )

        result = ingest.fetch_document_ids_csv(str(output_dir), "ingest_output.csv")

        assert list(result.columns) == ["account", "document"]
        assert len(result) == 2
        pairs = set(zip(result["account"], result["document"]))
        assert pairs == {("acc1", "doc1.pdf"), ("acc2", "doc2.pdf")}

    def test_returns_empty_dataframe_when_no_rows(self, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        output_path = output_dir / "ingest_output.csv"
        output_path.write_text("account,document,pages\n")

        result = ingest.fetch_document_ids_csv(str(output_dir), "ingest_output.csv")

        assert list(result.columns) == ["account", "document"]
        assert len(result) == 0


class TestFetchDocumentIdsGoogleSheets:
    def test_returns_unique_account_document_pairs(self, monkeypatch):
        fake_gc = MagicMock()
        monkeypatch.setattr(ingest.gs, "connect", MagicMock(return_value=fake_gc))
        fake_df = pd.DataFrame(
            [
                {"account": "acc1", "document": "doc1.pdf", "pages": "{}"},
                {"account": "acc1", "document": "doc1.pdf", "pages": "{}"},
                {"account": "acc2", "document": "doc2.pdf", "pages": "{}"},
            ]
        )
        monkeypatch.setattr(ingest.gs, "fetch_df", MagicMock(return_value=fake_df))

        result = ingest.fetch_document_ids_google_sheets(
            "Transactions", "Documents_RAW"
        )

        ingest.gs.fetch_df.assert_called_once_with(
            fake_gc, "Transactions", "Documents_RAW"
        )
        assert list(result.columns) == ["account", "document"]
        assert len(result) == 2


class TestAppendCsv:
    def test_appends_rows_without_duplicating_header(self, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        output_path = output_dir / "ingest_output.csv"
        output_path.write_text("account,document,pages\nacc1,doc1.pdf,{}\n")

        df = pd.DataFrame(
            [{"account": "acc2", "document": "doc2.pdf", "pages": "{}"}]
        )
        ingest.append_csv(str(output_dir), "ingest_output.csv", df)

        content = output_path.read_text().strip().splitlines()
        assert content == [
            "account,document,pages",
            "acc1,doc1.pdf,{}",
            "acc2,doc2.pdf,{}",
        ]

    def test_raises_value_error_on_header_mismatch(self, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        output_path = output_dir / "ingest_output.csv"
        output_path.write_text("account,document,pages\n")

        df = pd.DataFrame([{"account": "acc2", "document": "doc2.pdf"}])

        with pytest.raises(ValueError, match="does not match"):
            ingest.append_csv(str(output_dir), "ingest_output.csv", df)

        # Original file should remain untouched
        assert output_path.read_text() == "account,document,pages\n"

    def test_appending_empty_dataframe_leaves_file_unchanged(self, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        output_path = output_dir / "ingest_output.csv"
        output_path.write_text("account,document,pages\nacc1,doc1.pdf,{}\n")

        df = pd.DataFrame(columns=["account", "document", "pages"])
        ingest.append_csv(str(output_dir), "ingest_output.csv", df)

        assert output_path.read_text() == "account,document,pages\nacc1,doc1.pdf,{}\n"


class TestAppendGoogleSheets:
    def test_delegates_to_google_sheets_append(self, monkeypatch):
        fake_gc = MagicMock()
        monkeypatch.setattr(ingest.gs, "connect", MagicMock(return_value=fake_gc))
        mock_append = MagicMock()
        monkeypatch.setattr(ingest.gs, "append", mock_append)

        df = pd.DataFrame([{"account": "acc1", "document": "doc1.pdf", "pages": "{}"}])
        ingest.append_google_sheets("Transactions", "Documents_RAW", df)

        mock_append.assert_called_once_with(fake_gc, "Transactions", "Documents_RAW", df)


class TestExtractPdfPages:
    def test_extracts_text_from_all_pages(self, monkeypatch, tmp_path):
        page0 = MagicMock()
        page0.get_text.return_value = "Page zero text"
        page1 = MagicMock()
        page1.get_text.return_value = "Page one text"

        mock_doc = MagicMock()
        mock_doc.pages.return_value = [page0, page1]
        mock_doc.__enter__.return_value = mock_doc
        mock_doc.__exit__.return_value = False

        mock_open = MagicMock(return_value=mock_doc)
        monkeypatch.setattr(ingest.pymupdf, "open", mock_open)

        doc_path = tmp_path / "statement.pdf"
        result = ingest.extract_pdf_pages(doc_path)

        mock_open.assert_called_once_with(doc_path)
        assert json.loads(result) == {"0": "Page zero text", "1": "Page one text"}

    def test_returns_empty_json_object_for_pdf_with_no_pages(self, monkeypatch, tmp_path):
        mock_doc = MagicMock()
        mock_doc.pages.return_value = []
        mock_doc.__enter__.return_value = mock_doc
        mock_doc.__exit__.return_value = False
        monkeypatch.setattr(ingest.pymupdf, "open", MagicMock(return_value=mock_doc))

        result = ingest.extract_pdf_pages(tmp_path / "empty.pdf")

        assert json.loads(result) == {}


class TestIngestPdfsValidation:
    def test_raises_on_invalid_output_mode(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid output mode"):
            ingest.ingest_pdfs(data_dir=str(tmp_path), output_mode="xml")

    def test_raises_when_csv_missing_output_dir(self, tmp_path):
        with pytest.raises(ValueError, match="output_dir is required"):
            ingest.ingest_pdfs(data_dir=str(tmp_path), output_mode="csv")

    def test_raises_when_google_sheets_missing_spreadsheet(self, tmp_path):
        with pytest.raises(ValueError, match="output_spreadsheet and output_worksheet"):
            ingest.ingest_pdfs(
                data_dir=str(tmp_path),
                output_mode="google_sheets",
                output_worksheet="Documents_RAW",
            )

    def test_raises_when_google_sheets_missing_worksheet(self, tmp_path):
        with pytest.raises(ValueError, match="output_spreadsheet and output_worksheet"):
            ingest.ingest_pdfs(
                data_dir=str(tmp_path),
                output_mode="google_sheets",
                output_spreadsheet="Transactions",
            )


class TestIngestPdfsCsvFlow:
    def _patch_extract(self, monkeypatch):
        monkeypatch.setattr(
            ingest,
            "extract_pdf_pages",
            lambda path: json.dumps({"0": f"text of {path.name}"}),
        )

    def test_ingests_new_pdfs_into_fresh_csv(self, monkeypatch, tmp_path):
        self._patch_extract(monkeypatch)
        data_dir = tmp_path / "data"
        _make_pdf(data_dir / "acc1" / "doc1.pdf")
        _make_pdf(data_dir / "acc2" / "doc2.pdf")
        output_dir = tmp_path / "output"

        ingest.ingest_pdfs(
            data_dir=str(data_dir),
            output_mode="csv",
            output_dir=str(output_dir),
        )

        output_path = output_dir / "ingest_output.csv"
        df = pd.read_csv(output_path)
        assert len(df) == 2
        assert set(zip(df["account"], df["document"])) == {
            ("acc1", "doc1.pdf"),
            ("acc2", "doc2.pdf"),
        }

    def test_is_idempotent_on_repeated_runs(self, monkeypatch, tmp_path):
        self._patch_extract(monkeypatch)
        data_dir = tmp_path / "data"
        _make_pdf(data_dir / "acc1" / "doc1.pdf")
        output_dir = tmp_path / "output"

        ingest.ingest_pdfs(
            data_dir=str(data_dir), output_mode="csv", output_dir=str(output_dir)
        )
        ingest.ingest_pdfs(
            data_dir=str(data_dir), output_mode="csv", output_dir=str(output_dir)
        )

        df = pd.read_csv(output_dir / "ingest_output.csv")
        assert len(df) == 1

    def test_only_appends_newly_added_pdfs(self, monkeypatch, tmp_path):
        self._patch_extract(monkeypatch)
        data_dir = tmp_path / "data"
        _make_pdf(data_dir / "acc1" / "doc1.pdf")
        output_dir = tmp_path / "output"

        ingest.ingest_pdfs(
            data_dir=str(data_dir), output_mode="csv", output_dir=str(output_dir)
        )

        _make_pdf(data_dir / "acc1" / "doc2.pdf")
        ingest.ingest_pdfs(
            data_dir=str(data_dir), output_mode="csv", output_dir=str(output_dir)
        )

        df = pd.read_csv(output_dir / "ingest_output.csv")
        assert len(df) == 2
        assert set(zip(df["account"], df["document"])) == {
            ("acc1", "doc1.pdf"),
            ("acc1", "doc2.pdf"),
        }

    def test_handles_no_pdfs_found(self, monkeypatch, tmp_path):
        self._patch_extract(monkeypatch)
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        output_dir = tmp_path / "output"

        ingest.ingest_pdfs(
            data_dir=str(data_dir), output_mode="csv", output_dir=str(output_dir)
        )

        df = pd.read_csv(output_dir / "ingest_output.csv")
        assert len(df) == 0
        assert list(df.columns) == ["account", "document", "pages"]

    def test_respects_custom_output_file_name(self, monkeypatch, tmp_path):
        self._patch_extract(monkeypatch)
        data_dir = tmp_path / "data"
        _make_pdf(data_dir / "acc1" / "doc1.pdf")
        output_dir = tmp_path / "output"

        ingest.ingest_pdfs(
            data_dir=str(data_dir),
            output_mode="csv",
            output_dir=str(output_dir),
            output_file="custom_output.csv",
        )

        assert (output_dir / "custom_output.csv").exists()
        assert not (output_dir / "ingest_output.csv").exists()

    def test_ignores_non_pdf_files_and_nested_structure(self, monkeypatch, tmp_path):
        self._patch_extract(monkeypatch)
        data_dir = tmp_path / "data"
        _make_pdf(data_dir / "acc1" / "doc1.pdf")
        (data_dir / "acc1" / "notes.txt").parent.mkdir(parents=True, exist_ok=True)
        (data_dir / "acc1" / "notes.txt").write_text("not a pdf")
        # File directly under data_dir (not inside an account folder) should be ignored
        (data_dir / "loose.pdf").write_bytes(b"%PDF-1.4")
        output_dir = tmp_path / "output"

        ingest.ingest_pdfs(
            data_dir=str(data_dir), output_mode="csv", output_dir=str(output_dir)
        )

        df = pd.read_csv(output_dir / "ingest_output.csv")
        assert len(df) == 1
        assert df.iloc[0]["document"] == "doc1.pdf"


class TestIngestPdfsGoogleSheetsFlow:
    def test_orchestrates_google_sheets_output(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            ingest,
            "extract_pdf_pages",
            lambda path: json.dumps({"0": f"text of {path.name}"}),
        )
        data_dir = tmp_path / "data"
        _make_pdf(data_dir / "acc1" / "doc1.pdf")
        _make_pdf(data_dir / "acc1" / "doc2.pdf")

        mock_init = MagicMock()
        mock_fetch_ids = MagicMock(
            return_value=pd.DataFrame(
                [{"account": "acc1", "document": "doc1.pdf"}]
            )
        )
        mock_append = MagicMock()
        monkeypatch.setattr(ingest, "initialize_output_google_sheets", mock_init)
        monkeypatch.setattr(ingest, "fetch_document_ids_google_sheets", mock_fetch_ids)
        monkeypatch.setattr(ingest, "append_google_sheets", mock_append)

        ingest.ingest_pdfs(
            data_dir=str(data_dir),
            output_mode="google_sheets",
            output_spreadsheet="Transactions",
            output_worksheet="Documents_RAW",
        )

        mock_init.assert_called_once_with("Transactions", "Documents_RAW")
        mock_fetch_ids.assert_called_once_with("Transactions", "Documents_RAW")
        mock_append.assert_called_once()
        call_args = mock_append.call_args[0]
        assert call_args[0] == "Transactions"
        assert call_args[1] == "Documents_RAW"
        appended_df = call_args[2]
        # doc1.pdf already exists per fetch_document_ids_google_sheets, so only
        # doc2.pdf should be appended.
        assert set(zip(appended_df["account"], appended_df["document"])) == {
            ("acc1", "doc2.pdf")
        }