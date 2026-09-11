"""
Source-agnostic implementation of a table object.

The main purpose of this module is to provide a common interface for initializing,
reading, and appending to a table object. This is similar to DB-API except minimal
in scope and covering the use cases of CSVs and Google Sheets.
(Using a DB-API compliant library would be overkill for this project...or so I
initially thought, but this package seems quite enticing: https://github.com/betodealmeida/shillelagh)
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path

import gspread
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        self.schema_header = schema.columns.to_list()
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
        if df_header != self.schema_header:
            raise ValueError(
                f"DataFrame header {df_header} does not match schema header {self.schema_header}."
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

    def __init__(
        self,
        config: dict,
        schema: pd.DataFrame,
        default_output_dir: str,
        default_output_file: str,
    ):
        self.output_dir = config.get("output_dir", default_output_dir)
        self.output_file = config.get("output_file", default_output_file)
        self.output_path = Path(self.output_dir) / self.output_file

        super().__init__(schema)

    def _table_exists(self) -> bool:
        return self.output_path.exists()

    def _create_table(self) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        schema_csv = pd.DataFrame(columns=self.schema_header).to_csv(index=False)
        with open(self.output_path, "x") as f:
            f.write(schema_csv)
        logger.info(
            f"Output CSV {self.output_path} does not exist. Initializing it with the correct schema."
        )

    def _validate_table(self) -> None:
        # Validate that the structure matches the data being appended
        csv_header = pd.read_csv(self.output_path, nrows=0).columns.to_list()
        if csv_header != self.schema_header:
            raise ValueError(
                f"CSV header {csv_header} does not match schema header {self.schema_header}."
            )

    def _fetch_df(self) -> pd.DataFrame:
        return pd.read_csv(self.output_path)

    def _append(self, df: pd.DataFrame) -> None:
        with open(self.output_path, "a") as f:
            f.write(df.to_csv(header=False, index=False))


class TblGoogleSheets(Tbl):
    """A table object that represents a Google Sheets worksheet."""

    def __init__(self, config: dict, schema: pd.DataFrame, gc: gspread.Client):
        self.spreadsheet_name = config["spreadsheet_name"]
        self.worksheet_name = config["worksheet_name"]
        self.spreadsheet = gc.open(self.spreadsheet_name)

        # Validate/initialize table
        super().__init__(schema)

        # Now store references to the actual table since it exists
        self.worksheet = self.spreadsheet.worksheet(self.worksheet_name)

    def _table_exists(self) -> bool:
        all_ws = [ws.title for ws in self.spreadsheet.worksheets()]
        return self.worksheet_name in all_ws

    def _create_table(self) -> None:
        ws = self.spreadsheet.add_worksheet(
            self.worksheet_name, rows=1, cols=len(self.schema_header)
        )
        ws.update([self.schema_header])
        logger.info(
            f"Output Google Sheets worksheet {self.worksheet_name} in spreadsheet {self.spreadsheet_name} does not exist. It was created and initialized with the correct schema."
        )

    def _validate_table(self) -> None:
        ws = self.spreadsheet.worksheet(self.worksheet_name)

        # Validate that the structure matches the data being appended
        ws_header = ws.row_values(1)
        if ws_header != self.schema_header:
            raise ValueError(
                f"Worksheet header {ws_header} does not match schema header {self.schema_header}."
            )

    def _fetch_df(self) -> pd.DataFrame:
        ws = self.worksheet
        return pd.DataFrame(
            ws.get_all_records(),
            columns=ws.row_values(1),
        )

    def _append(self, df: pd.DataFrame) -> None:
        self.worksheet.append_rows(df.to_numpy().tolist())
