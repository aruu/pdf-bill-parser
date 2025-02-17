from pathlib import Path
import pandas as pd

if __name__ == "__main__":
    root_data_path = Path("data")
    root_output_path = Path("output")

    # First, iterate through all accounts and bills and output a TSV per bill
    for account_path in root_data_path.iterdir():
        print(account_path)
        for bill_path in account_path.iterdir():
            print(bill_path)

            # Extract the text by page
            # pagetexts = extract_pagetexts(file_path)
            pagetexts = ["asdf", "asdf"]

            # Parse the pagetexts into CSV format
            # The parser is responsible for extracting:
            # {account_name, file_name, transaction_date, description, amount}
            # and then optionally reversing the rows if this bill type is known to be chronologically reversed
            # csvtext = PagetextParser(pagetexts).get_csv()
            # PagetextParser(pagetexts, chronological_order = {"asc", "desc"})
            csvtext = "transaction_date,a,b\n2024-01-01,1,3\n2023-01-01,5,23\n"

            # Save the CSV in the output folder
            output_csv_path_parts = list(bill_path.parts)
            output_csv_path_parts[0] = "output"

            output_csv_path = Path(*output_csv_path_parts).with_suffix(".csv")
            output_csv_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_csv_path, "w") as f:
                f.write(csvtext)

    # Next, combine all CSVs for a given account into one CSV
    # stable sort in chronological order based on transaction_date
    for output_account_path in root_output_path.iterdir():
        print(output_account_path)

        if output_account_path.is_file():
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
        print(account_csv_path)
        list_input_dfs.append(pd.read_csv(account_csv_path))
    df_combined = pd.concat(list_input_dfs)
    df_combined = df_combined.sort_values(by="transaction_date", kind="stable")
    df_combined.to_csv(root_output_path / "final_output.csv", index=False)
