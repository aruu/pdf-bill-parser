import re
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime

import pandas as pd


class BillParser(ABC):
    """
    Parse pagetext into a CSV format.

    The parser is responsible for extracting fields in the format:
    {account_name, file_name, transaction_date, description, amount}
    and then ensuring that the data is in chronologically ascending order.

    Usage:
        csvtext = BillParser(account_name, file_name, pagetexts).get_csv()
    """

    # Constants for page types
    PAGE_TYPE_SUMMARY = "summary"
    PAGE_TYPE_TRANSACTIONS = "transactions"
    PAGE_TYPE_OTHER = "other"

    # Constants for transaction table processing
    END_OF_ROW = "end_of_row"
    END_OF_ROW_TOKEN = "EOR"

    def __init__(self, account_name, file_name, pagetexts):
        self.account_name = account_name
        self.file_name = file_name
        self.pagetexts = pagetexts
        self.classified_pagetexts = self._classify_pages(self.pagetexts)
        self.statement_date = self._extract_statement_date(
            self.classified_pagetexts["summary"][0]
        )
        self.transactions = self._extract_transactions(
            self.classified_pagetexts["transactions"]
        )

    @property
    @abstractmethod
    def PAGE_TYPE_REGEXES(self) -> dict[str, str]:
        """Returns a dictionary of regex patterns for classifying pages.
        The keys are the regex patterns used for classification, and the values
        are the page types (e.g., 'summary', 'transactions', 'other').
        """
        pass

    def _classify_pages(self, pagetexts: list[str]) -> dict[str, list[str]]:
        """Classify pages based on the provided regex patterns.
        This method iterates through the pagetexts and classifies each page
        into 'summary', 'transactions', or 'other' based on the regex patterns
        defined in the `PAGE_TYPE_REGEXES` property.

        Args:
            pagetexts (list[str]): List of text content from PDF pages.

        Returns:
            dict[str, list[str]]: A dictionary where keys are page types and values
            are lists of pagetexts belonging to that type.
        """

        classified_pagetexts: dict[str, list[str]] = defaultdict(list)

        # Iterate through pages, assign to first matching type or OTHER
        for pagetext in pagetexts:
            classification = self.PAGE_TYPE_OTHER
            for regex, page_type in self.PAGE_TYPE_REGEXES.items():
                if re.search(regex, pagetext):
                    classification = page_type
                    break
            classified_pagetexts[classification].append(pagetext)

        return dict(classified_pagetexts)

    @property
    @abstractmethod
    def STATEMENT_DATE_REGEX(self) -> str:
        """Returns the regex pattern used to extract the statement date from the summary page."""
        pass

    @property
    @abstractmethod
    def STATEMENT_DATE_FORMAT(self) -> str:
        """Returns the format string used to parse the statement date."""
        pass

    def _extract_statement_date(self, summary_pagetext: str) -> datetime:
        """Extract the statement date from the summary page text.
        This method uses the `STATEMENT_DATE_REGEX` to find the date string
        and then parses it using the `STATEMENT_DATE_FORMAT`.

        Args:
            summary_pagetext (str): The text content of the summary page.

        Returns:
            datetime: The parsed statement date.
        """
        statement_date_str = re.findall(self.STATEMENT_DATE_REGEX, summary_pagetext)[0]
        return datetime.strptime(statement_date_str, self.STATEMENT_DATE_FORMAT)

    def _extract_transactions(self, pagetexts: list[str]) -> pd.DataFrame:
        transaction_tables = []

        for pagetext in pagetexts:
            tabletexts = self._tabletext_extractor(pagetext)
            for tabletext in tabletexts:
                transaction_tables.append(self._parse_transaction_table(tabletext))

        transactions_all = pd.concat(transaction_tables)

        return transactions_all

    @abstractmethod
    def _tabletext_extractor(self, pagetext: str) -> list[str]:
        pass

    @abstractmethod
    def _parse_transaction_table(self, tabletext: str) -> pd.DataFrame:
        pass

    @abstractmethod
    def _pre_process_transactions(self, transactions: pd.DataFrame) -> pd.DataFrame:
        pass

    def get_csv_text(self):
        transactions = self._pre_process_transactions(self.transactions)
        transactions["account_name"] = self.account_name
        transactions["file_name"] = self.file_name

        # Select the standard output columns
        csv_text = transactions[
            ["transaction_date", "description", "amount", "account_name", "file_name"]
        ].to_csv(index=False)
        return csv_text


class BillParserA(BillParser):
    PAGE_TYPE_REGEXES = {  # type: ignore
        "due by": BillParser.PAGE_TYPE_SUMMARY,
        "Transaction\nDate": BillParser.PAGE_TYPE_TRANSACTIONS,
    }
    STATEMENT_DATE_REGEX = ".* to (.*)\nStatement period"  # type: ignore
    STATEMENT_DATE_FORMAT = "%b %d, %Y"  # type: ignore

    def _tabletext_extractor(self, pagetext: str) -> list[str]:
        # "New Balance – .*\n" indicates the end of this sequence, but we want to exclude that summary row
        tabletexts = re.findall(
            "(Reward\nEarned\n(?s:.)*\n)New Balance – .*\n", pagetext
        )

        return tabletexts

    def _parse_transaction_table(self, tabletext: str) -> pd.DataFrame:
        # Split the input text into lines - these can be treated as input into a state machine
        lines = tabletext.splitlines()

        transactions = []
        initial_state = "reward_earned"

        buffer = {}
        state = initial_state

        # Skip the header lines
        lines = lines[9:]

        # Sometimes there are additional header lines that we need to skip
        if re.match(r"^Interest rates$", lines[0]):
            lines = lines[17:]

        # State machine like processing
        while lines:
            match state:
                case "reward_earned":
                    buffer["reward_earned"] = lines.pop(0)
                    state = "amount"
                case "amount":
                    buffer["amount"] = lines.pop(0)
                    state = "category"
                case "category":
                    # Special handling since it can include "–" to represent Uncategorized
                    # Otherwise this is actually the start of the description so don't consume the line
                    if lines[0] != "–":
                        buffer["category"] = ""
                    else:
                        buffer["category"] = lines.pop(0)
                    state = "description"
                case "description":
                    # The description can be multi-line so we're not actually sure when it ends, until we reach the posted_date
                    if re.match(r"\d{2}-\D{3}-\d{4}", lines[0]):
                        state = "posted_date"
                        continue
                    if "description" not in buffer:
                        buffer["description"] = lines.pop(0)
                    else:
                        buffer["description"] += lines.pop(0)
                case "posted_date":
                    buffer["posted_date"] = lines.pop(0)
                    state = "transaction_date"
                case "transaction_date":
                    buffer["transaction_date"] = lines.pop(0)
                    state = self.END_OF_ROW
                    # Need a placeholder token to process the end of the row
                    lines.insert(0, self.END_OF_ROW_TOKEN)
                case self.END_OF_ROW:
                    transactions.append(buffer.copy())
                    buffer = {}
                    state = initial_state
                    lines.pop(0)

        return pd.DataFrame(transactions)

    def _pre_process_transactions(self, transactions: pd.DataFrame) -> pd.DataFrame:
        transactions["transaction_date"] = pd.to_datetime(
            transactions["transaction_date"], format="%d-%b-%Y"
        ).dt.strftime("%Y-%m-%d")
        transactions["amount"] = (
            transactions["amount"].str.replace("$", "").str.replace(",", "")
        )
        return transactions


class BillParserB(BillParser):
    PAGE_TYPE_REGEXES = {  # type: ignore
        "Balance from your last statement": BillParser.PAGE_TYPE_SUMMARY,
        "TRANSACTION DESCRIPTION": BillParser.PAGE_TYPE_TRANSACTIONS,
    }
    STATEMENT_DATE_REGEX = "Statement date: (.*) "  # type: ignore
    STATEMENT_DATE_FORMAT = "%B %d, %Y"  # type: ignore

    def _tabletext_extractor(self, pagetext: str) -> list[str]:
        tabletexts = re.findall(
            r"(TRANSACTION\nDATE\n.*?\.\d\d\n) ?Total",
            pagetext,
            re.DOTALL,
        )

        return tabletexts

    def _parse_transaction_table(self, tabletext: str) -> pd.DataFrame:
        # Split the input text into lines - these can be treated as input into a state machine
        lines = tabletext.splitlines()

        transactions = []
        initial_state = "transaction_date"

        buffer = {}
        state = initial_state

        # Skip the header lines
        lines = lines[6:]

        # Sometimes there is an additional header line that we need to skip
        if re.match(r"^Purchases - Card #", lines[0]):
            lines.pop(0)

        # State machine like processing
        while lines:
            match state:
                case "transaction_date":
                    buffer["transaction_date"] = lines.pop(0)
                    state = "posting_date"
                case "posting_date":
                    line = lines.pop(0)
                    buffer["posting_date"] = line[0:6]

                    # Occassionally, the description starts on this line
                    remaining_line = line[6:]
                    if remaining_line:
                        # Remove the first character since it is a space after the date
                        lines.insert(0, remaining_line[1:])

                    state = "transaction_description"
                case "transaction_description":
                    # The description can be multi-line so we're not actually sure when it ends, until we reach the amount
                    if re.match(r".*\d\.\d\d", lines[0]):
                        state = "amount"
                        continue
                    if "transaction_description" not in buffer:
                        buffer["transaction_description"] = lines.pop(0)
                    else:
                        buffer["transaction_description"] += " " + lines.pop(0)
                case "amount":
                    buffer["amount"] = lines.pop(0)
                    state = self.END_OF_ROW
                    # Need a placeholder token to process the end of the row
                    lines.insert(0, self.END_OF_ROW_TOKEN)
                case self.END_OF_ROW:
                    transactions.append(buffer.copy())
                    buffer = {}
                    state = initial_state
                    lines.pop(0)

        return pd.DataFrame(transactions)

    def _pre_process_transactions(self, transactions: pd.DataFrame) -> pd.DataFrame:
        transactions["description"] = transactions["transaction_description"]
        transactions["amount"] = transactions["amount"].str.replace(",", "")

        # Determine the year from the statement date
        transactions["transaction_date_year"] = self.statement_date.year
        if self.statement_date.month == 1:
            transactions.loc[
                transactions["transaction_date"].apply(lambda x: "Dec" in x),
                "transaction_date_year",
            ] -= 1

        transactions["transaction_date"] = pd.to_datetime(
            transactions["transaction_date"]
            + " "
            + transactions["transaction_date_year"].astype(str),
            format="%b %d %Y",
        )
        return transactions


class BillParserC(BillParser):
    PAGE_TYPE_REGEXES = {  # type: ignore
        "Summary of your account": BillParser.PAGE_TYPE_SUMMARY,
        "Transactions since your last statement": BillParser.PAGE_TYPE_TRANSACTIONS,
    }
    STATEMENT_DATE_REGEX = "Statement date\n(.*)\n"  # type: ignore
    STATEMENT_DATE_FORMAT = "%b. %d, %Y"  # type: ignore

    def _tabletext_extractor(self, pagetext: str) -> list[str]:
        tabletexts = re.findall(
            r"(TRANS\nDATE\n(?s:.)*)(?:\(continued on next page\)|Subtotal for )",
            pagetext,
        )

        return tabletexts

    def _parse_transaction_table(self, tabletext: str) -> pd.DataFrame:
        # Split the input text into lines - these can be treated as input into a state machine
        lines = tabletext.splitlines()

        transactions = []
        initial_state = "transaction_date"

        buffer = {}
        state = initial_state

        # Skip the header lines
        lines = lines[6:]

        # Sometimes there is an additional header line that we need to skip
        if re.match(r"^Card number: XXXX XXXX XXXX", lines[0]):
            lines.pop(0)

        # State machine like processing
        while lines:
            match state:
                case "transaction_date":
                    line = lines.pop(0)
                    parts = line.split()
                    # The posting date could be on the same line - if so, push it back onto the stack
                    if len(parts) == 4:
                        lines.insert(0, parts[2] + " " + parts[3])
                    buffer["transaction_date"] = parts[0] + " " + parts[1]
                    state = "posting_date"
                case "posting_date":
                    line = lines.pop(0)
                    parts = line.split()
                    buffer["posting_date"] = parts[0] + " " + parts[1]
                    state = "description"
                case "description":
                    # The description can be multi-line so we're not actually sure when it ends, until we reach the amount
                    if re.match(r"^[\d,]*\.\d\d (\xa0CR)?$", lines[0]):
                        state = "amount"
                        continue
                    # There seems to be a variable amount of spaces in the description - clean it up
                    if "description" not in buffer:
                        buffer["description"] = " ".join(lines.pop(0).split())
                    else:
                        buffer["description"] += " " + " ".join(lines.pop(0).split())
                case "amount":
                    buffer["amount"] = lines.pop(0).strip()
                    state = self.END_OF_ROW
                    # Need a placeholder token to process the end of the row
                    lines.insert(0, self.END_OF_ROW_TOKEN)
                case self.END_OF_ROW:
                    transactions.append(buffer.copy())
                    buffer = {}
                    state = initial_state
                    lines.pop(0)

        return pd.DataFrame(transactions)

    def _pre_process_transactions(self, transactions: pd.DataFrame) -> pd.DataFrame:
        transactions["amount"] = (
            transactions["amount"]
            .str.replace(",", "")
            .apply(lambda x: "-" + x.replace(" \xa0CR", "") if " \xa0CR" in x else x)
        )

        # Determine the year from the statement date
        transactions["transaction_date_year"] = self.statement_date.year
        if self.statement_date.month == 1:
            transactions.loc[
                transactions["transaction_date"].apply(lambda x: "Dec." in x),
                "transaction_date_year",
            ] -= 1

        transactions["transaction_date"] = pd.to_datetime(
            transactions["transaction_date"]
            + ", "
            + transactions["transaction_date_year"].astype(str),
            format="%b. %d, %Y",
        )
        return transactions


class BillParserD(BillParser):
    PAGE_TYPE_REGEXES = {  # type: ignore
        "Your account at a glance": BillParser.PAGE_TYPE_SUMMARY,
        "Transactions from": BillParser.PAGE_TYPE_TRANSACTIONS,
    }
    STATEMENT_DATE_REGEX = ".* statement period\n.* to (.*)"  # type: ignore
    STATEMENT_DATE_FORMAT = "%B %d, %Y"  # type: ignore

    def _tabletext_extractor(self, pagetext: str) -> list[str]:
        tabletexts = re.findall(
            r"(Trans\ndate\n.*?\.\d\d\n)Total",
            pagetext,
            re.DOTALL,
        )

        return tabletexts

    def _parse_transaction_table(self, tabletext: str) -> pd.DataFrame:
        mode = "payments"

        # Split the input text into lines - these can be treated as input into a state machine
        lines = tabletext.splitlines()

        transactions = []
        initial_state = "transaction_date"

        buffer = {}
        state = initial_state

        # Skip the header lines
        lines = lines[5:]
        # Sometimes there is an additional header line
        # This indicates we are parsing a charges and credits table
        if lines[0] == "Spend Categories":
            mode = "charges_and_credits"
            lines = lines[3:]
        else:
            lines.pop(0)

        # State machine like processing
        while lines:
            match state:
                case "transaction_date":
                    buffer["transaction_date"] = lines.pop(0)
                    state = "posting_date"
                case "posting_date":
                    line = lines.pop(0)
                    buffer["posting_date"] = line[0:6]

                    # Occassionally, the description starts on this line
                    remaining_line = line[6:]
                    if remaining_line:
                        # Remove the first character since it is a space after the date
                        lines.insert(0, remaining_line[1:])

                    state = "transaction_description"
                case "transaction_description":
                    # There seems to be a variable amount of spaces in the description - clean it up
                    description = " ".join(lines.pop(0).split())
                    # It can sometime start with "Ý ", so we need to remove this
                    if description.startswith("Ý "):
                        description = description[2:]
                    buffer["transaction_description"] = description
                    if mode == "payments":
                        state = "amount"
                    else:
                        state = "category"
                case "category":
                    buffer["category"] = lines.pop(0)
                    state = "amount"
                case "amount":
                    if mode == "payments":
                        buffer["amount"] = "-" + lines.pop(0)
                    else:
                        buffer["amount"] = lines.pop(0)
                    state = self.END_OF_ROW
                    # Need a placeholder token to process the end of the row
                    lines.insert(0, self.END_OF_ROW_TOKEN)
                case self.END_OF_ROW:
                    transactions.append(buffer.copy())
                    buffer = {}
                    state = initial_state
                    lines.pop(0)

        return pd.DataFrame(transactions)

    def _pre_process_transactions(self, transactions: pd.DataFrame) -> pd.DataFrame:
        transactions["description"] = transactions["transaction_description"]
        transactions["amount"] = transactions["amount"].str.replace(",", "")

        # Determine the year from the statement date
        transactions["transaction_date_year"] = self.statement_date.year
        if self.statement_date.month == 1:
            transactions.loc[
                transactions["transaction_date"].apply(lambda x: "Dec" in x),
                "transaction_date_year",
            ] -= 1

        transactions["transaction_date"] = pd.to_datetime(
            transactions["transaction_date"]
            + " "
            + transactions["transaction_date_year"].astype(str),
            format="%b %d %Y",
        )
        return transactions
