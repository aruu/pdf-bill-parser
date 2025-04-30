from abc import ABC, abstractmethod
import re
import pandas as pd
from datetime import datetime, date


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
        self.account_name = account_name
        self.file_name = file_name
        self.pagetexts = pagetexts

    @abstractmethod
    def get_csv(self):
        pass


class DummyBillParser(BillParser):
    def get_csv(self):
        return (
            "account_name,file_name,transaction_date,description,amount\n"
            f"{self.account_name},{self.file_name},2023-01-01,desc,3\n"
            f"{self.account_name},{self.file_name},2024-01-01,desc,5\n"
        )


class BillParserA(BillParser):
    def parse_lines(self, lines):
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
                    if buffer.get("description"):
                        buffer["description"] += " " + lines.pop(0)
                    else:
                        buffer["description"] = lines.pop(0)
                case "posted_date":
                    buffer["posted_date"] = lines.pop(0)
                    state = "transaction_date"
                case "transaction_date":
                    buffer["transaction_date"] = lines.pop(0)
                    state = "end_of_row"
                case "end_of_row":
                    transactions.append(buffer.copy())
                    buffer = {}
                    state = initial_state

        return pd.DataFrame(transactions)

    def tabletext_to_csv(self, tabletext):
        # Split the input text into lines - these can be treated as input into a state machine
        lines = tabletext.splitlines()
        transactions = self.parse_lines(lines)

        # Compile the transactions into the standard format
        transactions["account_name"] = self.account_name
        transactions["file_name"] = self.file_name
        transactions["transaction_date"] = pd.to_datetime(
            transactions["transaction_date"], format="%d-%b-%Y"
        ).dt.strftime("%Y-%m-%d")
        transactions["amount"] = (
            transactions["amount"].str.replace("$", "").str.replace(",", "")
        )

        # Select the standard output columns
        output = transactions[
            ["transaction_date", "description", "amount", "account_name", "file_name"]
        ].to_csv(index=False)
        return output

    def get_csv(self):
        # Iterate through pages
        for i, pagetext in enumerate(self.pagetexts, start=1):
            if re.findall("due by", pagetext, re.IGNORECASE):
                page_type = "summary"

            elif re.findall(
                "(Reward\nEarned\n.*)New Balance – [^\n]*\n", pagetext, re.DOTALL
            ):
                page_type = "transactions"
                tabletext = re.findall(
                    "(Reward\nEarned\n.*)New Balance – [^\n]*\n",
                    pagetext,
                    re.DOTALL,
                )[0]
                output = self.tabletext_to_csv(tabletext)

            else:
                page_type = "other"

        return output


class BillParserB(BillParser):
    def extract_statement_date(self):
        for i, current_pagetext in enumerate(self.pagetexts, start=1):
            if re.findall("Balance from your last statement", current_pagetext):
                line = current_pagetext.split("\n")[1]
                return datetime.strptime(line, "Statement date: %B %d, %Y ")

    def get_csv(self):
        # Extract the statement date to resolve the year of the transaction date
        statement_date = self.extract_statement_date()

        output = "transaction_date,description,amount,account_name,file_name\n"

        for i, current_pagetext in enumerate(self.pagetexts, start=1):
            page_type = None

            if re.findall("Balance from your last statement", current_pagetext):
                page_type = "summary"

            elif re.findall("TRANSACTION DESCRIPTION", current_pagetext):
                page_type = "transactions"

            else:
                page_type = "other"

            if page_type == "transactions":
                raw_table_texts = re.findall(
                    r"(TRANSACTION\nDATE\n.*?\.\d\d\n) ?Total",
                    current_pagetext,
                    re.DOTALL,
                )

                for raw_table_text in raw_table_texts:
                    # Split the input text into lines and remove empty lines
                    lines = [line for line in raw_table_text.strip().split("\n")]

                    # Process lines in groups of 7 (each transaction spans multiple lines)
                    i = 6  # Skip the header lines
                    lines = lines[6:]
                    mode = "transaction_date"
                    transaction_date = ""
                    description = ""
                    amount = ""
                    for line in lines:
                        # Skip title line that is sometimes present
                        if re.match(r"^Purchases - Card #", line):
                            continue

                        # Special pre-handling for description since it can be multi-line
                        if mode == "transaction_description":
                            if re.match(r".*\.\d\d$", line):
                                mode = "amount"
                            else:
                                description += line

                        # Extract values from the lines
                        match mode:
                            case "transaction_date":
                                transaction_date = line
                                mode = "posting_date"
                            case "posting_date":
                                mode = "transaction_description"

                                # Occassionally, the description starts on this line
                                if len(line) != 6:
                                    description = line[6:]
                                else:
                                    description = ""
                            case "amount":
                                amount = line.replace(",", "")
                                mode = "transaction_date"

                                # Wrap up and iterate to new row
                                # Determine the year from the statement date
                                statement_date_month = statement_date.month
                                statement_date_year = statement_date.year
                                transaction_date_month = datetime.strptime(
                                    transaction_date.split(" ")[0], "%b"
                                ).month
                                transaction_date_day = datetime.strptime(
                                    transaction_date.split(" ")[1], "%d"
                                ).day

                                if (
                                    transaction_date_month != statement_date_month
                                ) and (statement_date_month == 1):
                                    # Transaction is in December of the previous year
                                    transaction_date_year = statement_date_year - 1
                                else:
                                    # Transaction is in the same year as the statement date
                                    transaction_date_year = statement_date_year

                                transaction_date = date(
                                    transaction_date_year,
                                    transaction_date_month,
                                    transaction_date_day,
                                ).strftime("%Y-%m-%d")

                                output += f"{transaction_date},{description.strip()},{amount},{self.account_name},{self.file_name}\n"

        return output
