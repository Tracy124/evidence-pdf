from dataclasses import asdict, dataclass


@dataclass
class DocumentMeta:
    company: str
    language: str
    year: str
    document_type: str
    source_filename: str
    company_source: str = "正文识别"
    year_source: str = "正文识别"


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
    currency: str
    amount_unit: str
    value_year: str
    source_filename: str
    page_number: int
    language: str
    year: str
    document_type: str
    matched_terms: str
    score: float
    excerpt: str
    evidence_filename: str = ""
    review_status: str = "待人工复核"

    def to_record(self) -> dict:
        return asdict(self)
