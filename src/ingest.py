"""Ingest PDFs into JSON and save the data in the specified target."""

import json
import logging
from pathlib import Path
from typing import Literal

import pandas as pd
import pymupdf

import google_sheets as gs
from config import get_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TEMPLATE_RECORD = pd.DataFrame(columns=["account", "document", "pages"])


def initialize_output_csv(
    output_dir: str,
    output_file: str,
) -> None:
    """Initialize the specified output CSV."""
    output_path = Path(output_dir) / output_file

    if not output_path.exists():
        logger.info(
            f"Output CSV {output_path} does not exist. Initializing it with the correct schema."
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        documents_csv = TEMPLATE_RECORD.to_csv(index=False)
        with open(output_path, "x") as f:
            f.write(documents_csv)


def initialize_output_google_sheets(
    spreadsheet_name: str,
    worksheet_name: str,
) -> None:
    """Initialize the specified output Google Sheets worksheet."""
    gc = gs.connect()
    all_ws = gs.list_worksheets(gc, spreadsheet_name)

    if worksheet_name not in all_ws:
        logger.info(
            f"Output Google Sheets worksheet {worksheet_name} in spreadsheet {spreadsheet_name} does not exist. Initializing it with the correct schema."
        )
        gs.initialize_worksheet(gc, spreadsheet_name, worksheet_name, TEMPLATE_RECORD)


def fetch_document_ids_csv(
    output_dir: str,
    output_file: str,
) -> pd.DataFrame:
    """Fetch the existing document IDs from the specified CSV."""
    output_path = Path(output_dir) / output_file
    return pd.read_csv(output_path)[["account", "document"]].drop_duplicates()


def fetch_document_ids_google_sheets(
    spreadsheet_name: str,
    worksheet_name: str,
) -> pd.DataFrame:
    """Fetch the existing document IDs from the specified Google Sheets worksheet."""
    # Technically it's a bit wasteful to fetch the entire worksheet just to get the document IDs,
    # but it's a trade-off for simplicity and maintainability.
    gc = gs.connect()
    return gs.fetch_df(gc, spreadsheet_name, worksheet_name)[
        ["account", "document"]
    ].drop_duplicates()


def append_csv(
    output_dir: str,
    output_file: str,
    df: pd.DataFrame,
) -> None:
    """Append new rows to the specified CSV."""
    output_path = Path(output_dir) / output_file

    # Validate that the structure matches the data being appended
    csv_header = pd.read_csv(output_path, nrows=0).columns.to_list()
    df_header = df.columns.to_list()
    if csv_header != df_header:
        raise ValueError(
            f"CSV header {csv_header} does not match DataFrame header {df_header}."
        )

    with open(output_path, "a") as f:
        f.write(df.to_csv(header=False, index=False))


def append_google_sheets(
    spreadsheet_name: str,
    worksheet_name: str,
    df: pd.DataFrame,
) -> None:
    """Append new rows to the specified Google Sheets worksheet."""
    gc = gs.connect()
    gs.append(gc, spreadsheet_name, worksheet_name, df)


def extract_pdf_pages(doc_path: Path) -> str:
    """Extracts text from all pages of a PDF and returns it as a JSON string."""
    with pymupdf.open(doc_path) as doc:
        return json.dumps(
            {index: page.get_text() for index, page in enumerate(doc.pages())}
        )


def ingest_pdfs(
    data_dir: str,
    output_mode: Literal["csv", "google_sheets"],
    output_dir: str = "",
    output_file: str = "ingest_output.csv",
    output_spreadsheet: str = "",
    output_worksheet: str = "",
) -> None:
    """Ingest PDFs into JSON and save the data in the specified target.

    One of the following output modes must be specified: "csv" or "google_sheets".
    If the mode is "csv", then output_dir must be specified, and output_file can be overridden
    from its default value of "ingest_output.csv".
    If the mode is "google_sheets", then output_spreadsheet and output_worksheet must be specified.

    Args:
        data_dir (str): The directory containing the PDF files to ingest.
        output_mode (Literal["csv", "google_sheets"]): The mode for outputting the data.
        output_dir (str): The directory where the output will be saved.
        output_file (str): The name of the output file. Defaults to "ingest_output.csv".
        output_spreadsheet (str): The name of the Google Sheets spreadsheet to save the data to.
        output_worksheet (str): The name of the worksheet to save the data to.

    Returns:
        None
    """

    if output_mode not in ["csv", "google_sheets"]:
        raise ValueError(
            f"Invalid output mode: {output_mode}. Must be 'csv' or 'google_sheets'."
        )
    if output_mode == "csv" and not output_dir:
        raise ValueError("output_dir is required when output_mode is 'csv'.")
    if output_mode == "google_sheets" and (
        not output_spreadsheet or not output_worksheet
    ):
        raise ValueError(
            "output_spreadsheet and output_worksheet are required when "
            "output_mode is 'google_sheets'."
        )

    # Check that the target outputs exist and initialize if they don't
    # Then fetch the current document IDs from the output target
    match output_mode:
        case "csv":
            initialize_output_csv(output_dir, output_file)
            df_document_ids = fetch_document_ids_csv(output_dir, output_file)
        case "google_sheets":
            initialize_output_google_sheets(output_spreadsheet, output_worksheet)
            df_document_ids = fetch_document_ids_google_sheets(
                output_spreadsheet, output_worksheet
            )

    # Iterate through all accounts and documents
    # Use .glob() to flatten the nested loops and filter explicitly for PDFs
    pdf_paths = Path(data_dir).glob("*/*.pdf")
    records = [
        {
            "account": path.parent.name,
            "document": path.name,
            "pages": extract_pdf_pages(path),
        }
        for path in pdf_paths
    ]
    # Ensure the DataFrame has the correct schema even when no PDFs are found.
    df_documents = pd.DataFrame(records)
    if df_documents.empty:
        df_documents = TEMPLATE_RECORD.copy()
    # Filter out documents that are already present in the output target
    df_documents = df_documents.merge(
        df_document_ids,
        on=["account", "document"],
        how="left_anti",
    )

    # Output to the specified target
    match output_mode:
        case "csv":
            append_csv(output_dir, output_file, df_documents)
        case "google_sheets":
            append_google_sheets(output_spreadsheet, output_worksheet, df_documents)

    logger.info(
        f"Ingested {len(df_documents)} new documents from `{data_dir}/` into {output_mode}."
    )
    # Log the document IDs of the ingested documents for traceability
    for _, row in df_documents.iterrows():
        logger.info(
            f"Ingested document: account={row['account']}, document={row['document']}"
        )


if __name__ == "__main__":
    config = get_config()
    match config["ingest_output"]["mode"]:
        case "csv":
            if "file_name" in config["ingest_output"]:
                ingest_pdfs(
                    data_dir=config["data_dir"],
                    output_mode="csv",
                    output_dir=config["output_dir"],
                    output_file=config["ingest_output"]["file_name"],
                )
            else:
                ingest_pdfs(
                    data_dir=config["data_dir"],
                    output_mode="csv",
                    output_dir=config["output_dir"],
                )

        case "google_sheets":
            ingest_pdfs(
                data_dir=config["data_dir"],
                output_mode="google_sheets",
                output_spreadsheet=config["ingest_output"]["spreadsheet_name"],
                output_worksheet=config["ingest_output"]["worksheet_name"],
            )
