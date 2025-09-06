# %%
import re
from pathlib import Path
from typing import Type

import pandas as pd
import pymupdf
import yaml

from bill_parser import BillParser, BillParserA, BillParserB, BillParserC, BillParserD

PARSER_MAPPING: dict[str, Type[BillParser]] = {
    "BillParserA": BillParserA,
    "BillParserB": BillParserB,
    "BillParserC": BillParserC,
    "BillParserD": BillParserD,
}

CONFIG_YAML_FILENAME = "config.yaml"
DATA_DIR = "data"
OUTPUT_DIR = "output"
FINAL_OUTPUT_FILENAME = "final_output.csv"
FINAL_CATEGORIZED_FILENAME = "final_categorized.csv"


# %%
if __name__ == "__main__":
    root_data_path = Path(DATA_DIR)
    root_output_path = Path(OUTPUT_DIR)

    # Parse YAML config file. This specifies:
    # - which folder name patterns to use with which Parser classes
    # - which transaction description patterns to assign to which categories
    with open(CONFIG_YAML_FILENAME, "r") as f:
        config = yaml.safe_load(f)

    account_mapping = config["account_mapping"]
    description_mapping = config["description_mapping"]

    # First, iterate through all accounts and bills and output a TSV per bill
    for account_path in root_data_path.iterdir():
        # Determine the BillParser class to use based on the account name
        parser = None
        for mapping in account_mapping:
            # Use the first pattern that matches
            if re.search(mapping["pattern"], account_path.name):
                parser = PARSER_MAPPING[mapping["parser"]]
                break
        if parser is None:
            raise ValueError(f"No parser found for account {account_path.name}")

        for bill_path in account_path.iterdir():
            print(bill_path)

            # Open the PDF and extract the text from each page
            doc = pymupdf.open(bill_path)
            pagetexts = [page.get_text() for page in doc.pages()]
            doc.close()

            # Parse the pagetexts into CSV format
            bill_parser = parser(
                account_path.name,
                bill_path.name,
                pagetexts,
            )
            csvtext = bill_parser.get_csv_text()

            # Save the CSV in the output folder
            output_csv_path_parts = list(bill_path.parts)
            output_csv_path_parts[0] = OUTPUT_DIR

            output_csv_path = Path(*output_csv_path_parts).with_suffix(".csv")
            output_csv_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_csv_path, "w") as f:
                f.write(csvtext)

    # Next, combine all CSVs for a given account into one CSV
    # stable sort in chronological order based on transaction_date
    for output_account_path in root_output_path.iterdir():
        if not output_account_path.is_dir():
            # This is not a directory
            continue

        # Combine all CSVs into one
        list_input_dfs = []
        for csv_path in output_account_path.glob("*.csv"):
            print(csv_path)
            list_input_dfs.append(pd.read_csv(csv_path, dtype=str))
        df_combined = pd.concat(list_input_dfs)
        df_combined = df_combined.sort_values(by="transaction_date", kind="stable")
        df_combined.to_csv(output_account_path.with_suffix(".csv"), index=False)

    # Combine all account CSVs into an overall CSV
    # stable sort in chronological order based on transaction_date
    list_input_dfs = []
    for account_csv_path in root_output_path.glob("*.csv"):
        if account_csv_path.name in [FINAL_OUTPUT_FILENAME, FINAL_CATEGORIZED_FILENAME]:
            continue
        print(account_csv_path)
        list_input_dfs.append(pd.read_csv(account_csv_path, dtype=str))
    df_combined = pd.concat(list_input_dfs)
    df_combined = df_combined.sort_values(by="transaction_date", kind="stable")
    df_combined.to_csv(root_output_path / FINAL_OUTPUT_FILENAME, index=False)

    # Finally, categorize the transactions based on the description patterns
    df_final = pd.read_csv(root_output_path / FINAL_OUTPUT_FILENAME, dtype=str)
    df_final_categorized = df_final.copy()
    df_final_categorized["category"] = None

    # Map according to patterns specified in the YAML config
    for pattern, category in description_mapping.items():
        df_final_categorized.loc[
            df_final_categorized["category"].isna()
            & df_final_categorized["description"].str.contains(pattern),
            "category",
        ] = category

    # If still uncategorized, assign "Uncategorized"
    df_final_categorized.loc[
        df_final_categorized["category"].isna(),
        "category",
    ] = "Uncategorized"

    # Select the output columns and save to CSV
    df_final_categorized = df_final_categorized[
        [
            "transaction_date",
            "category",
            "description",
            "amount",
            "account_name",
            "file_name",
        ]
    ]
    df_final_categorized.to_csv(
        root_output_path / FINAL_CATEGORIZED_FILENAME, index=False
    )
