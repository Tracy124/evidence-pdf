from dataclasses import asdict, dataclass


@dataclass
class DocumentMeta:
    company: str
    language: str
    year: str
    document_type: str
    source_filename: str


@dataclass
class PageText:
    page_number: int
    text: str


@dataclass
class Evidence:
    index: int
    company: str
    indicator: str
    value_candidate: str
    source_filename: str
    page_number: int
    language: str
    year: str
    document_type: str
    matched_terms: str
    score: float
    excerpt: str
    evidence_filename: str = ""

    def to_record(self) -> dict:
        return asdict(self)
