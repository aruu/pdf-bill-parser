from pathlib import Path

if __name__ == "__main__":
    data_path = Path("data")

    # First, iterate through all accounts and bills and output a TSV per bill
    for account_path in data_path.iterdir():
        print(account_path)
        for bill_path in account_path.iterdir():
            print(bill_path)

            # Extract the text by page
            # pagetexts = extract_pagetexts(file_path)
            pagetexts = ["asdf", "asdf"]

            # Parse the pagetexts into TSV format
            # The parser is responsible for extracting:
            # {account_name, file_name, transaction_date, description, amount}
            # and then optionally reversing the rows if this bill type is known to be chronologically reversed
            # tsvtext = PagetextParser(pagetexts).get_tsv()
            # PagetextParser(pagetexts, chronological_order = {"asc", "desc"})
            tsvtext = "a\tb\n1\t3\n"

            # Save the TSV in the output folder
            output_path_parts = list(bill_path.parts)
            output_path_parts[0] = "output"
            output_path_parts[2] = f"{bill_path.stem}.tsv"

            output_path = Path(*output_path_parts)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(tsvtext)

    # Next, combine all TSVs for a given account into one TSV
    # stable sort in chronological order based on transaction_date

    # Finally, combine all account TSVs into an overall TSV
    # stable sort in chronological order based on transaction_date
