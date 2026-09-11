"""Ingest PDFs into JSON and save the data in the specified target."""

import json
import logging
import os
from pathlib import Path
from typing import Any

import gspread
import pandas as pd
import pymupdf

from config import get_config
from tbl import TblCsv, TblGoogleSheets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INGEST_SCHEMA = pd.DataFrame(columns=["account", "document", "pages"])


def extract_pdf_pages(doc_path: Path) -> str:
    """Extracts text from all pages of a PDF and returns it as a JSON string."""
    with pymupdf.open(doc_path) as doc:
        return json.dumps(
            {index: page.get_text() for index, page in enumerate(doc.pages())}
        )


def ingest() -> None:
    """Ingest PDFs into JSON and save the data in the specified target."""

    config = get_config()
    data_dir = config["data_dir"]
    tbl_ingest_config: dict[str, Any] = config["ingest"]

    match tbl_ingest_config["db_type"]:
        case "csv":
            tbl_ingest = TblCsv(
                tbl_ingest_config,
                schema=INGEST_SCHEMA,
                default_output_dir=config["output_dir"],
                default_output_file="ingest.csv",
            )
        case "google_sheets":
            gspread_credentials = json.loads(os.environ[config["env_var_gspread_json"]])
            gc = gspread.service_account_from_dict(gspread_credentials)
            tbl_ingest = TblGoogleSheets(
                tbl_ingest_config,
                schema=INGEST_SCHEMA,
                gc=gc,  # pyright: ignore[reportPossiblyUnboundVariable]
            )
        case _:
            raise ValueError(
                f"Invalid db_type for 'ingest': {tbl_ingest_config['db_type']}. Must be 'csv' or 'google_sheets'."
            )

    # Fetch the current document IDs from the output target
    df_document_ids = tbl_ingest.fetch_df()[["account", "document"]].drop_duplicates()

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
    df_documents = pd.DataFrame(records)

    # Filter out documents that are already present in the output target
    df_documents = df_documents.merge(
        df_document_ids,
        on=["account", "document"],
        how="left_anti",
    )
    if df_documents.empty:
        logger.info("No new documents to ingest.")
        return

    # Output to the specified target
    tbl_ingest.append(df_documents)

    logger.info(
        f"Ingested {len(df_documents)} new documents from `{data_dir}/` into {tbl_ingest_config['db_type']}."
    )
    # Log the document IDs of the ingested documents for traceability
    for _, row in df_documents.iterrows():
        logger.info(
            f"Ingested document: account={row['account']}, document={row['document']}"
        )


if __name__ == "__main__":
    ingest()
