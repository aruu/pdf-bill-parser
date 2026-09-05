import re
from datetime import datetime
from types import MappingProxyType

import pandas as pd

import extractors.base as extract


class ExtractorC(extract.Extractor):
    PAGE_TYPE_REGEXES = MappingProxyType(
        {
            "Summary of your account": extract.PAGE_TYPE_SUMMARY,
            "Transactions since your last statement": extract.PAGE_TYPE_TRANSACTIONS,
        }
    )
    STATEMENT_DATE_REGEX = "Statement date\n(.*)\n"
    STATEMENT_DATE_FORMAT = "%b. %d, %Y"

    @classmethod
    def _tabletext_extractor(cls, pagetext: str) -> list[str]:
        tabletexts = re.findall(
            r"(TRANS\nDATE\n(?s:.)*?)(?:\(continued on next page\)|Subtotal for )",
            pagetext,
        )

        return tabletexts

    @classmethod
    def _parse_transaction_table(cls, tabletext: str) -> pd.DataFrame:
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
                    if re.match(r"^[\d,]*\.\d\d ?(\xa0CR)?$", lines[0]):
                        state = "amount"
                        continue
                    # There seems to be a variable amount of spaces in the description - clean it up
                    if "description" not in buffer:
                        buffer["description"] = " ".join(lines.pop(0).split())
                    else:
                        buffer["description"] += " " + " ".join(lines.pop(0).split())
                case "amount":
                    buffer["amount"] = lines.pop(0)
                    state = extract.END_OF_ROW
                    # Need a placeholder token to process the end of the row
                    lines.insert(0, extract.END_OF_ROW_TOKEN)
                case _ if state == extract.END_OF_ROW:
                    transactions.append(buffer.copy())
                    buffer = {}
                    state = initial_state
                    lines.pop(0)

        return pd.DataFrame(transactions)

    @classmethod
    def _pre_process_transactions(
        cls, transactions: pd.DataFrame, statement_date: datetime
    ) -> pd.DataFrame:

        transactions["amount"] = (
            transactions["amount"]
            .str.replace(",", "")
            .apply(
                lambda x: (
                    "-" + x.replace("\xa0CR", "").strip()
                    if "\xa0CR" in x
                    else x.strip()
                )
            )
        )

        # Determine the year from the statement date
        transactions["transaction_date_year"] = statement_date.year
        if statement_date.month == 1:
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
