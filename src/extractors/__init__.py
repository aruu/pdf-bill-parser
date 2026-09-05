from extractors.base import Extractor
from extractors.extractor_c import ExtractorC

EXTRACTOR_MAPPING: dict[str, type[Extractor]] = {
    # "ExtractorA": ExtractorA,
    # "ExtractorB": ExtractorB,
    "ExtractorC": ExtractorC,
    # "ExtractorD": ExtractorD,
    # "ExtractorE": ExtractorE,
}
