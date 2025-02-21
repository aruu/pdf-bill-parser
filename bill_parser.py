from abc import ABC, abstractmethod


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
