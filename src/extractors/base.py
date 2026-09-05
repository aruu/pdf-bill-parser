import re
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime

import pandas as pd

# Constants for page types
PAGE_TYPE_SUMMARY = "summary"
PAGE_TYPE_TRANSACTIONS = "transactions"
PAGE_TYPE_OTHER = "other"

# Constants for transaction table processing
END_OF_ROW = "end_of_row"
END_OF_ROW_TOKEN = "EOR"


class Extractor(ABC):
    """
    Parse pagetext into a CSV format.

    The parser is responsible for extracting fields in the format:
    {account_name, file_name, transaction_date, description, amount}
    and then ensuring that the data is in chronologically ascending order.

    Usage:
        csvtext = BillParser(account_name, file_name, pagetexts).get_csv()
    """

    # Class variables that must be defined in subclasses
    PAGE_TYPE_REGEXES: Mapping[str, str]
    """Dictionary of regex patterns for classifying pages.
    Keys are regex patterns, and values are the corresponding page types 
    (e.g., 'summary', 'transactions', 'other').
    """
    STATEMENT_DATE_REGEX: str
    """Regex pattern used to extract the statement date from the summary page."""
    STATEMENT_DATE_FORMAT: str
    """Format string used to parse the statement date."""

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)

        # Ensure subclasses define required class variables
        required_class_vars = [
            "PAGE_TYPE_REGEXES",
            "STATEMENT_DATE_REGEX",
            "STATEMENT_DATE_FORMAT",
        ]
        for var in required_class_vars:
            if not hasattr(cls, var):
                raise TypeError(f"{cls.__name__} must define class variable {var}")

    @classmethod
    def _classify_pages(cls, pagetexts: list[str]) -> dict[str, list[str]]:
        """Classify pages based on the provided regex patterns.
        This method iterates through the pagetexts and classifies each page
        into 'summary', 'transactions', or 'other' based on the regex patterns
        defined in the `PAGE_TYPE_REGEXES`.

        Args:
            pagetexts (list[str]): List of text content from PDF pages.

        Returns:
            dict[str, list[str]]: A dictionary where keys are page types and values
            are lists of pagetexts belonging to that type.
        """

        classified_pagetexts: dict[str, list[str]] = defaultdict(list)

        # Iterate through pages, assign to first matching type or OTHER
        for pagetext in pagetexts:
            classification = PAGE_TYPE_OTHER
            for regex, page_type in cls.PAGE_TYPE_REGEXES.items():
                if re.search(regex, pagetext):
                    classification = page_type
                    break
            classified_pagetexts[classification].append(pagetext)

        return dict(classified_pagetexts)

    @classmethod
    def _extract_statement_date(cls, summary_pagetext: str) -> datetime:
        """Extract the statement date from the summary page text.
        This method uses the `STATEMENT_DATE_REGEX` to find the date string
        and then parses it using the `STATEMENT_DATE_FORMAT`.

        Args:
            summary_pagetext (str): The text content of the summary page.

        Returns:
            datetime: The parsed statement date.
        """
        statement_date_str = re.findall(cls.STATEMENT_DATE_REGEX, summary_pagetext)[0]
        return datetime.strptime(statement_date_str, cls.STATEMENT_DATE_FORMAT)  # noqa: DTZ007

    @classmethod
    def _extract_transactions(cls, pagetexts: list[str]) -> pd.DataFrame:

        transaction_tables = []
        for pagetext in pagetexts:
            tabletexts = cls._tabletext_extractor(pagetext)
            for tabletext in tabletexts:
                transaction_tables.append(cls._parse_transaction_table(tabletext))

        transactions_all = pd.concat(transaction_tables)

        return transactions_all

    @classmethod
    @abstractmethod
    def _tabletext_extractor(cls, pagetext: str) -> list[str]:
        pass

    @classmethod
    @abstractmethod
    def _parse_transaction_table(cls, tabletext: str) -> pd.DataFrame:
        pass

    @classmethod
    @abstractmethod
    def _pre_process_transactions(
        cls, transactions: pd.DataFrame, statement_date: datetime
    ) -> pd.DataFrame:
        pass

    @classmethod
    def extract_transactions_csv(cls, pagetexts: list[str]) -> str:
        """Extract transactions data from the provided pagetexts.

        Args:
            pagetexts (list[str]): List of text content from PDF pages.
        Returns:
            str: A CSV string containing the extracted transaction data.
        """
        classified_pagetexts = cls._classify_pages(pagetexts)
        statement_date = cls._extract_statement_date(classified_pagetexts["summary"][0])
        transactions = cls._extract_transactions(classified_pagetexts["transactions"])
        transactions = cls._pre_process_transactions(transactions, statement_date)

        # Select the output columns
        return transactions[["transaction_date", "description", "amount"]].to_csv(
            index=False
        )
