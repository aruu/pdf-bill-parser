"""Ingest PDFs into JSON and save the data in the target destination."""

import json
from pathlib import Path
from typing import Literal

import pandas as pd
import pymupdf

from config import get_config
from google_sheets import append_to_google_sheets, get_gspread_client


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
    """Ingest PDFs into JSON and save the data in the target destination as a table.

    One of the following output modes must be specified: "csv" or "google_sheets".
    If the mode is "csv", then output_dir must be specified, and output_file can be overridden
    from its default value of "ingest_output.csv".
    If the mode is "google_sheets", then output_spreadsheet and output_worksheet must be specified.

    Args:
        data_dir (str): The directory containing the PDF files to ingest.
        output_mode (Literal["csv", "google_sheets"]): The mode for outputting the data.
        output_dir (str): The directory where the output JSON files will be saved.
        output_file (str): The name of the output file. Defaults to "ingest_output.csv".
        output_spreadsheet (str): The name of the Google Spreadsheet to save the data to.
        output_worksheet (str): The name of the worksheet in the Google Spreadsheet to save the data to.

    Returns:
        None
    """

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
    documents_df = pd.DataFrame(records, columns=["account", "document", "pages"])

    # Output to the specified destination
    match output_mode:
        case "csv":
            documents_csv = documents_df.to_csv(index=False)
            output_path = Path(output_dir) / output_file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(documents_csv)

        case "google_sheets":
            gc = get_gspread_client()
            append_to_google_sheets(
                gc=gc,
                spreadsheet_name=output_spreadsheet,
                worksheet_name=output_worksheet,
                df=documents_df,
            )

        case _:
            raise ValueError(
                f"Invalid output mode: {output_mode}. Must be 'csv' or 'google_sheets'."
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
