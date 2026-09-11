"""
Source-agnostic implementation of a table object.

The main purpose of this module is to provide a common interface for initializing,
reading, and appending to a table object. This is similar to DB-API except minimal
in scope and covering the use cases of CSVs and Google Sheets.
(Using a DB-API compliant library would be overkill for this project...or so I
initially thought, but this package seems quite enticing: https://github.com/betodealmeida/shillelagh)
"""

from abc import ABC, abstractmethod

import gspread
import pandas as pd

import google_sheets as gs


class Tbl(ABC):
    """
    A table object that a pipeline can use in a source-agnostic way.

    The table object can be used for database-like actions. It is up to the pipeline user
    to be aware of the specific parameters required for each subclass and to handle
    connection lifecycle.
    """

    def __init__(self, schema: pd.DataFrame) -> None:
        """
        Initialize the table object with the given configuration and schema.

        If the table does not exist, it is created. If the table already exists,
        the existing table is validated against the provided schema.

        Args:
            schema (pd.DataFrame): A DataFrame representing the schema of the table.
        """
        self.schema = schema
        if self._table_exists():
            self._validate_table()
        else:
            self._create_table()

    @abstractmethod
    def _table_exists(self) -> bool: ...

    @abstractmethod
    def _create_table(self) -> None:
        """
        Create the table with the given schema.

        Returns None on success, raise an Exception otherwise.
        """

    @abstractmethod
    def _validate_table(self) -> None:
        """
        Validate the actual schema against the expected schema.

        Returns None on success, raise an Exception otherwise.
        """

    @abstractmethod
    def _fetch_df(self) -> pd.DataFrame: ...

    @abstractmethod
    def _append(self, df: pd.DataFrame) -> None:
        """
        Append a DataFrame to the table.

        Returns None on success, raise an Exception otherwise.
        """

    def _validate_df(self, df: pd.DataFrame) -> None:
        """
        Validate the given DataFrame against the schema of the table.

        Returns None on success, raise an Exception otherwise.
        """
        df_header = df.columns.to_list()
        schema_header = self.schema.columns.to_list()
        if df_header != schema_header:
            raise ValueError(
                f"DataFrame header {df_header} does not match schema header {schema_header}."
            )

    def fetch_df(self) -> pd.DataFrame:
        """
        Fetch the entire table as a DataFrame.

        Returns:
            pd.DataFrame: A DataFrame containing the data from the table.
        """
        return self._fetch_df()

    def append(self, df: pd.DataFrame) -> None:
        """
        Validate and append a DataFrame to the table.

        Returns None on success, raise an Exception otherwise.
        """
        self._validate_df(df)
        self._append(df)


class TblCsv(Tbl):
    """A table object that represents a CSV file."""

    def __init__(self, config: dict, schema: pd.DataFrame):
        super().__init__(schema)

    def _table_exists(self) -> bool: ...

    def _create_table(self) -> None: ...

    def _validate_table(self) -> None: ...

    def _fetch_df(self) -> pd.DataFrame: ...

    def _append(self, df: pd.DataFrame) -> None: ...


class TblGoogleSheets(Tbl):
    """A table object that represents a Google Sheets worksheet."""

    def __init__(self, config: dict, schema: pd.DataFrame, gc: gspread.Client):
        self.gc = gc
        self.spreadsheet_name = config["spreadsheet_name"]
        self.worksheet_name = config["worksheet_name"]

        super().__init__(schema)

    def _table_exists(self) -> bool:
        sh = self.gc.open(self.spreadsheet_name)
        all_ws = [ws.title for ws in sh.worksheets()]
        return self.worksheet_name in all_ws

    def _create_table(self) -> None:
        gs.initialize_worksheet(
            self.gc,
            self.spreadsheet_name,
            self.worksheet_name,
            self.schema,
        )

    def _validate_table(self) -> None:
        schema_header = self.schema.columns.to_list()
        sh = self.gc.open(self.spreadsheet_name)
        ws = sh.worksheet(self.worksheet_name)

        # Validate that the structure matches the data being appended
        ws_header = ws.row_values(1)
        if ws_header != schema_header:
            raise ValueError(
                f"Worksheet header {ws_header} does not match schema header {schema_header}."
            )

    def _fetch_df(self) -> pd.DataFrame:
        return gs.fetch_df(
            self.gc,
            self.spreadsheet_name,
            self.worksheet_name,
        )

    def _append(self, df: pd.DataFrame) -> None:
        gs.append(
            self.gc,
            self.spreadsheet_name,
            self.worksheet_name,
            df,
        )
