import re
from abc import ABC, abstractmethod
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

    def __init__(self, account_name, file_name, pagetexts):
        self.END_OF_ROW = "end_of_row"
        self.END_OF_ROW_TOKEN = "EOR"

        self.account_name = account_name
        self.file_name = file_name
        self.pagetexts = pagetexts
        self.classified_pagetexts = self._classify_pages(self.pagetexts)
        self.transactions = self._extract_transactions(
            self.classified_pagetexts["transactions"]
        )

    @abstractmethod
    def _classify_pages(self, pagetexts: list[str]) -> dict[str, list[str]]:
        pass

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
    def _classify_pages(self, pagetexts: list[str]) -> dict[str, list[str]]:
        classified_pagetexts = {}

        # Iterate through pages
        for pagetext in pagetexts:
            if re.findall("due by", pagetext, re.IGNORECASE):
                page_type = "summary"
            elif re.findall(
                "(Reward\nEarned\n.*)New Balance – [^\n]*\n", pagetext, re.DOTALL
            ):
                page_type = "transactions"
            else:
                page_type = "other"

            if page_type not in classified_pagetexts:
                classified_pagetexts[page_type] = [pagetext]
            else:
                classified_pagetexts[page_type].append(pagetext)

        return classified_pagetexts

    def _tabletext_extractor(self, pagetext: str) -> list[str]:
        # "New Balance – .*\n" indicates the end of this sequence, but we want to exclude that summary row
        tabletexts = re.findall(
            "(Reward\nEarned\n(?s:.)*\n).*\n.*\nNew Balance – .*\n", pagetext
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
    def __init__(self, account_name, file_name, pagetexts):
        super().__init__(account_name, file_name, pagetexts)

        # Extract the statement date to resolve the year of the transaction date
        statement_date_line = self.classified_pagetexts["summary"][0].split("\n")[1]
        self.statement_date = datetime.strptime(
            statement_date_line, "Statement date: %B %d, %Y "
        )

    def _classify_pages(self, pagetexts: list[str]) -> dict[str, list[str]]:
        classified_pagetexts = {}

        # Iterate through pages
        for pagetext in pagetexts:
            if re.findall("Balance from your last statement", pagetext):
                page_type = "summary"
            elif re.findall("TRANSACTION DESCRIPTION", pagetext):
                page_type = "transactions"
            else:
                page_type = "other"

            if page_type not in classified_pagetexts:
                classified_pagetexts[page_type] = [pagetext]
            else:
                classified_pagetexts[page_type].append(pagetext)

        return classified_pagetexts

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
