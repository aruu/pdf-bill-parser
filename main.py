if __name__ == "__main__":

    # For each file
    for file_path in 'data/account/filename.pdf':
        # Extract the text by page
        pagetexts = ["asdf", "asdf"]
        pagetexts = extract_pagetexts(file_path)

        # Parse the pagetexts into TSV format
        # The parser is responsible for extracting:
        # {account_name, file_name, transaction_date, description, amount}
        # and then optionally reversing the rows if this bill type is known to be chronologically reversed
        tsvtext = PagetextParser(pagetexts).get_tsv()
        # PagetextParser(pagetexts, chronological_order = {"asc", "desc"})

        # Save the TSV in the output folder
        output_path = re.sub('data', 'output', pdf_path)
        output_path = re.sub('.pdf$', '.tsv', output_path)

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(output)

    # Combine all TSVs for a given account into one TSV
    # stable sort in chronological order based on transaction_date

    # Combine all account TSVs into an overall TSV
    # stable sort in chronological order based on transaction_date
