from pathlib import Path
import pandas as pd
from bill_parser import DummyBillParser

DATA_DIR = "data"
OUTPUT_DIR = "output"
FINAL_OUTPUT_FILENAME = "final_output.csv"

if __name__ == "__main__":
    root_data_path = Path(DATA_DIR)
    root_output_path = Path(OUTPUT_DIR)

    # First, iterate through all accounts and bills and output a TSV per bill
    for account_path in root_data_path.iterdir():
        for bill_path in account_path.iterdir():
            print(bill_path)

            # Extract the text by page
            # pagetexts = extract_pagetexts(file_path)
            pagetexts = ["asdf", "asdf"]

            # Parse the pagetexts into CSV format
            csvtext = DummyBillParser(
                account_path.name,
                bill_path.name,
                pagetexts,
            ).get_csv()

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
            list_input_dfs.append(pd.read_csv(csv_path))
        df_combined = pd.concat(list_input_dfs)
        df_combined = df_combined.sort_values(by="transaction_date", kind="stable")
        df_combined.to_csv(output_account_path.with_suffix(".csv"), index=False)

    # Finally, combine all account CSVs into an overall CSV
    # stable sort in chronological order based on transaction_date
    list_input_dfs = []
    for account_csv_path in root_output_path.glob("*.csv"):
        if account_csv_path.name == FINAL_OUTPUT_FILENAME:
            continue
        print(account_csv_path)
        list_input_dfs.append(pd.read_csv(account_csv_path))
    df_combined = pd.concat(list_input_dfs)
    df_combined = df_combined.sort_values(by="transaction_date", kind="stable")
    df_combined.to_csv(root_output_path / FINAL_OUTPUT_FILENAME, index=False)
