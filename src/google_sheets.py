"""Helper functions to make saving data to Google Sheets more seamless."""

import json
import os

import gspread
import pandas as pd

from config import get_config


def get_gspread_client() -> gspread.Client:
    """Authenticate using service account credentials and return a Client object."""
    config = get_config()
    gspread_credentials = json.loads(os.environ[config["env_var_gspread_json"]])
    return gspread.service_account_from_dict(gspread_credentials)


def append_to_google_sheets(
    gc: gspread.Client,
    spreadsheet_name: str,
    worksheet_name: str,
    df: pd.DataFrame,
) -> None:
    """Append data to a specified Google Sheet.
    The function will validate that the structure matches the data
    being appended and raise an Exception if it doesn't.
    If the worksheet doesn't exist, it will be created.

    Args:
        gc (gspread.Client): Authenticated gspread client.
        spreadsheet_name (str): Name of the Google Sheet.
        worksheet_name (str): Name of the worksheet within the Google Sheet.
        df (pd.DataFrame): DataFrame containing the data to append.
    """

    df_header = df.columns.to_list()
    sh = gc.open(spreadsheet_name)

    try:
        # Access the worksheet, validate that the structure matches the data being appended
        ws = sh.worksheet(worksheet_name)
        ws_header = ws.row_values(1)

        if ws_header != df_header:
            raise ValueError(
                f"Worksheet header {ws_header} does not match DataFrame header {df_header}."
            )

    except gspread.exceptions.WorksheetNotFound:
        # If the worksheet doesn't exist, create it and initialize just the header
        ws = sh.add_worksheet(worksheet_name, rows=1, cols=len(df_header))
        ws.update([df_header])

    # Append data to the worksheet
    ws.append_rows(df.to_numpy().tolist())
