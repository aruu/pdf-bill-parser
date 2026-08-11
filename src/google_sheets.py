"""Helper functions to make saving data to Google Sheets more seamless."""

import json
import os

import gspread
import pandas as pd

from config import get_config


def connect() -> gspread.Client:
    """Authenticate using service account credentials and return a Client object."""
    config = get_config()
    gspread_credentials = json.loads(os.environ[config["env_var_gspread_json"]])
    return gspread.service_account_from_dict(gspread_credentials)


def initialize_worksheet(
    gc: gspread.Client,
    spreadsheet_name: str,
    worksheet_name: str,
    df: pd.DataFrame,
) -> None:
    """Initialize a worksheet with the specified name and header structure.

    Args:
        gc (gspread.Client): Authenticated gspread client.
        spreadsheet_name (str): Name of the Google Sheet.
        worksheet_name (str): Name of the worksheet within the Google Sheet.
        df (pd.DataFrame): DataFrame containing the header structure to initialize the worksheet with.
    """

    df_header = df.columns.to_list()

    sh = gc.open(spreadsheet_name)
    ws = sh.add_worksheet(worksheet_name, rows=1, cols=len(df_header))
    ws.update([df_header])


def list_worksheets(
    gc: gspread.Client,
    spreadsheet_name: str,
) -> list[str]:
    """List all worksheets in the specified Google Sheet.

    Args:
        gc (gspread.Client): Authenticated gspread client.
        spreadsheet_name (str): Name of the Google Sheet.

    Returns:
        list[str]: A list of worksheet names in the specified Google Sheet.
    """

    sh = gc.open(spreadsheet_name)
    return [ws.title for ws in sh.worksheets()]


def fetch_df(
    gc: gspread.Client,
    spreadsheet_name: str,
    worksheet_name: str,
) -> pd.DataFrame:
    """Fetch the specified Google Sheets worksheet as a DataFrame.

    Args:
        gc (gspread.Client): Authenticated gspread client.
        spreadsheet_name (str): Name of the Google Sheet.
        worksheet_name (str): Name of the worksheet within the Google Sheet.

    Returns:
        pd.DataFrame: A DataFrame containing the data from the specified worksheet.
    """

    sh = gc.open(spreadsheet_name)
    ws = sh.worksheet(worksheet_name)
    return pd.DataFrame(
        ws.get_all_records(),
        columns=ws.row_values(1),
    )


def append(
    gc: gspread.Client,
    spreadsheet_name: str,
    worksheet_name: str,
    df: pd.DataFrame,
) -> None:
    """Append data to a specified Google Sheet.
    The function will validate that the structure matches the data
    being appended and raise an Exception if it doesn't.

    Args:
        gc (gspread.Client): Authenticated gspread client.
        spreadsheet_name (str): Name of the Google Sheet.
        worksheet_name (str): Name of the worksheet within the Google Sheet.
        df (pd.DataFrame): DataFrame containing the data to append.
    """

    df_header = df.columns.to_list()
    sh = gc.open(spreadsheet_name)
    ws = sh.worksheet(worksheet_name)

    # Validate that the structure matches the data being appended
    ws_header = ws.row_values(1)
    if ws_header != df_header:
        raise ValueError(
            f"Worksheet header {ws_header} does not match DataFrame header {df_header}."
        )

    # Append data to the worksheet
    ws.append_rows(df.to_numpy().tolist())
