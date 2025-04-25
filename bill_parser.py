from abc import ABC, abstractmethod
import re
from datetime import datetime


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
                print(f"Summary page found on page {i}")
                page_type = "summary"

            elif re.findall("trans", current_pagetext, re.IGNORECASE) and re.findall(
                "\\$", current_pagetext, re.IGNORECASE
            ):
                print(f"Transactions page found on page {i}")
                page_type = "transactions"

            else:
                print(f"Other page found on page {i}")
                page_type = "other"

            if page_type == "transactions":
                print(
                    re.findall(
                        "(Reward\nEarned\n.*New Balance – [^\n]*\n)",
                        current_pagetext,
                        re.DOTALL,
                    )[0]
                )

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
                            print(f"mode: '{mode}', line: '{line}'")
                            description += " "
                            description += line

                    # Extract values from the lines
                    match mode:
                        case "reward":
                            print(f"mode: '{mode}', line: '{line}'")
                            mode = "amount"
                        case "amount":
                            amount = line.replace("$", "").replace(",", "")
                            print(f"mode: '{mode}', line: '{line}'")
                            mode = "description"
                            description = ""
                        case "posted_date":
                            print(f"mode: '{mode}', line: '{line}'")
                            mode = "transaction_date"
                        case "transaction_date":
                            transaction_date = line
                            # Wrap up and iterate to new row
                            print(f"mode: '{mode}', line: '{line}'")
                            mode = "reward"

                            transaction_date = datetime.strptime(
                                transaction_date, "%d-%b-%Y"
                            ).strftime("%Y-%m-%d")

                            output += f"{self.account_name},{self.file_name},{transaction_date},{description.strip()},${amount}\n"

        return output
