import re
import unicodedata
from pathlib import Path

from .models import DocumentMeta


INVALID_FILENAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def safe_filename(value: str, fallback: str = "未知") -> str:
    value = unicodedata.normalize("NFKC", value or "").strip()
    value = INVALID_FILENAME.sub("-", value)
    value = re.sub(r"\s+", "-", value).strip(" .-")
    return value[:80] or fallback


def split_terms(raw: str) -> list[str]:
    seen: set[str] = set()
    terms = []
    for item in re.split(r"[,，;；\n]+", raw):
        term = re.sub(r"\s+", " ", item).strip()
        key = term.casefold()
        if term and key not in seen:
            seen.add(key)
            terms.append(term)
    return terms


def infer_meta(filename: str, company: str = "", year: str = "", document_type: str = "") -> DocumentMeta:
    stem = Path(filename).stem
    detected_year = re.search(r"(?:19|20)\d{2}", stem)
    language = "中文" if re.search(r"[\u4e00-\u9fff]", stem) else "英文"
    detected_type = document_type or next(
        (name for name in ("年度报告", "年报", "财务报告", "招股书", "ESG报告", "审计报告") if name in stem),
        "PDF",
    )
    detected_company = company.strip()
    if not detected_company:
        cleaned = re.sub(r"(?:19|20)\d{2}", "", stem)
        for token in (
            "年度报告", "年报", "财务报告", "招股书", "ESG报告", "审计报告",
            "Annual Report", "annual report", "Financial Report", "financial report",
        ):
            cleaned = cleaned.replace(token, "")
        detected_company = re.sub(r"[_\- ]+", " ", cleaned).strip() or "未知企业"
    return DocumentMeta(
        company=detected_company,
        language=language,
        year=year.strip() or (detected_year.group(0) if detected_year else "未知年份"),
        document_type=detected_type,
        source_filename=filename,
    )


def evidence_name(index: int, meta: DocumentMeta, page_number: int) -> str:
    pieces = [
        f"{index:03d}", meta.company, meta.language, meta.year,
        meta.document_type, f"p{page_number}",
    ]
    return "_".join(safe_filename(p) for p in pieces) + ".pdf"
