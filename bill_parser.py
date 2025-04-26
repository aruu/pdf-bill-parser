from abc import ABC, abstractmethod
import re
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
    def get_csv(self):
        # Iterate through pages
        for i, current_pagetext in enumerate(self.pagetexts, start=1):
            page_type = None

            if re.findall("due by", current_pagetext, re.IGNORECASE):
                page_type = "summary"

            elif re.findall("trans", current_pagetext, re.IGNORECASE) and re.findall(
                "\\$", current_pagetext, re.IGNORECASE
            ):
                page_type = "transactions"

            else:
                page_type = "other"

            if page_type == "transactions":
                raw_table_text = re.findall(
                    "(Reward\nEarned\n.*New Balance – [^\n]*\n)",
                    current_pagetext,
                    re.DOTALL,
                )[0]

                output = "account_name,file_name,transaction_date,description,amount\n"

                # Split the input text into lines and remove empty lines
                lines = [line for line in raw_table_text.split("\n")]

                # Initialize list to store transactions
                output_lines = []

                # Process lines in groups of 7 (each transaction spans multiple lines)
                i = 9  # Skip the header lines
                lines = lines[9:]
                mode = "reward"
                transaction_date = ""
                description = ""
                amount = ""
                for line in lines:
                    # Special pre-handling for description since it can be multi-line or include "–" to represent Uncategorized
                    if mode == "description":
                        if line == "–":
                            continue

                        pattern = r"\d{2}-\D{3}-\d{4}"
                        if re.match(pattern, line):
                            mode = "posted_date"
                        else:
                            description += " "
                            description += line

                    # Extract values from the lines
                    match mode:
                        case "reward":
                            mode = "amount"
                        case "amount":
                            amount = line.replace("$", "").replace(",", "")

                            mode = "description"
                            description = ""
                        case "posted_date":
                            mode = "transaction_date"
                        case "transaction_date":
                            transaction_date = line
                            # Wrap up and iterate to new row

                            mode = "reward"

                            transaction_date = datetime.strptime(
                                transaction_date, "%d-%b-%Y"
                            ).strftime("%Y-%m-%d")

                            output += f"{self.account_name},{self.file_name},{transaction_date},{description.strip()},{amount}\n"

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

        output = "account_name,file_name,transaction_date,description,amount\n"

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

                                output += f"{self.account_name},{self.file_name},{transaction_date},{description.strip()},{amount}\n"

        return output
