"""Extract transactions data from each document JSON."""

import json
import logging
import os
import re
from typing import Any

import gspread
import pandas as pd

from config import get_config
from extractors import EXTRACTOR_MAPPING
from tbl import TblCsv, TblGoogleSheets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INGEST_SCHEMA = pd.DataFrame(columns=["account", "document", "pages"])
EXTRACT_SCHEMA = pd.DataFrame(columns=["account", "document", "pages", "transactions"])


def extract_transactions(row: pd.Series) -> str:
    """Extract transactions data from a single document JSON.

    Args:
        row (pd.Series): A row from the DataFrame containing the document data.

    Returns:
        str: A CSV string containing the extracted transaction data.
    """
    # Placeholder implementation - replace with actual transaction extraction logic

    document_dict = row.to_dict()
    pages_json = document_dict["pages"]
    pages = json.loads(pages_json)

    config = get_config()
    account_mapping = config["account_mapping"]

    # Determine the Extractor class to use based on the account name
    extractor = None
    for mapping in account_mapping:
        # Use the first pattern that matches
        if re.search(mapping["pattern"], document_dict["account"]):
            extractor = EXTRACTOR_MAPPING[mapping["extractor"]]
            break
    if extractor is None:
        return EXTRACT_SCHEMA.to_csv(index=False)
        raise ValueError(f"No extractor found for account {document_dict['account']}")

    extractor_instance = extractor(
        account_name=document_dict["account"],
        file_name=document_dict["document"],
        pagetexts=list(pages.values()),
    )
    return extractor_instance.get_csv_text()


def extract():
    """Extract transactions data from each document JSON.

    This wrapper function executes the extract pipeline with Google Sheets input and output.
    """
    config = get_config()
    tbl_ingest_config: dict[str, Any] = config["ingest"]
    tbl_extract_config: dict[str, Any] = config["extract"]

    if "google_sheets" in [
        tbl_ingest_config["db_type"],
        tbl_extract_config["db_type"],
    ]:
        gspread_credentials = json.loads(os.environ[config["env_var_gspread_json"]])
        gc = gspread.service_account_from_dict(gspread_credentials)

    match tbl_ingest_config["db_type"]:
        case "csv":
            tbl_ingest = TblCsv(
                tbl_ingest_config,
                schema=INGEST_SCHEMA,
                default_output_dir=config["output_dir"],
                default_output_file="ingest.csv",
            )
        case "google_sheets":
            tbl_ingest = TblGoogleSheets(
                tbl_ingest_config,
                schema=INGEST_SCHEMA,
                gc=gc,  # pyright: ignore[reportPossiblyUnboundVariable]
            )
        case _:
            raise ValueError(
                f"Invalid db_type for 'ingest': {tbl_ingest_config['db_type']}. Must be 'csv' or 'google_sheets'."
            )

    match tbl_extract_config["db_type"]:
        case "csv":
            tbl_extract = TblCsv(
                tbl_extract_config,
                schema=EXTRACT_SCHEMA,
                default_output_dir=config["output_dir"],
                default_output_file="extract.csv",
            )
        case "google_sheets":
            tbl_extract = TblGoogleSheets(
                tbl_extract_config,
                schema=EXTRACT_SCHEMA,
                gc=gc,  # pyright: ignore[reportPossiblyUnboundVariable]
            )
        case _:
            raise ValueError(
                f"Invalid db_type for 'extract': {tbl_extract_config['db_type']}. Must be 'csv' or 'google_sheets'."
            )

    # Fetch the input data from the ingest output
    df_ingested = tbl_ingest.fetch_df()

    # Fetch the current document IDs from the output target
    df_extracted_ids = tbl_extract.fetch_df()[["account", "document"]].drop_duplicates()

    # Filter out documents that are already present in the output target
    df_ingested = df_ingested.merge(
        df_extracted_ids,
        on=["account", "document"],
        how="left_anti",
    )

    # Perform the extraction for each document
    if df_ingested.empty:
        logger.info("No new documents to extract.")
        return
    df_extracted = df_ingested.copy()
    df_extracted["transactions"] = df_extracted.apply(extract_transactions, axis=1)

    # Output to the specified target
    tbl_extract.append(df_extracted)

    # Log the document IDs of the extracted documents for traceability
    for _, row in df_extracted.iterrows():
        logger.info(
            f"Extracted document: account={row['account']}, document={row['document']}"
        )


if __name__ == "__main__":
    extract()
