from extractors.base import BillParser, BillParserC

EXTRACTOR_MAPPING: dict[str, type[BillParser]] = {
    # "BillParserA": BillParserA,
    # "BillParserB": BillParserB,
    "BillParserC": BillParserC,
    # "BillParserD": BillParserD,
    # "BillParserE": BillParserE,
}
