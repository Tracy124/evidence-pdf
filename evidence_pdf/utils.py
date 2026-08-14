import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import List, Optional

from .models import DocumentMeta, PageText


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


def _content_sample(pages: Optional[List[PageText]], limit: int = 12) -> str:
    if not pages:
        return ""
    return "\n".join(page.text for page in pages[:limit] if page.text)


def _infer_company(text: str) -> str:
    candidates: Counter[str] = Counter()
    zh_pattern = re.compile(r"([\u4e00-\u9fffA-Za-z0-9（）()·&]{2,50}(?:股份有限公司|有限责任公司|有限公司))")
    en_pattern = re.compile(
        r"([A-Z][A-Za-z0-9&.,'()\- ]{1,80}(?:Company Limited|Co\.,? Ltd\.?|Limited|Ltd\.?|Inc\.?|Corporation|Corp\.?))"
    )
    for line_number, raw_line in enumerate(text.splitlines()):
        line = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", raw_line)).strip()
        for pattern in (zh_pattern, en_pattern):
            for match in pattern.findall(line):
                candidate = match.strip(" ,.;:-")
                bonus = 5 if line_number < 8 else 1
                candidates[candidate] += bonus
    return candidates.most_common(1)[0][0] if candidates else "待人工确认"


def _infer_report_year(text: str) -> str:
    patterns = (
        r"((?:19|20)\d{2})\s*年\s*(?:年度报告|年报)",
        r"(?:年度报告|年报)\s*[（(]?\s*((?:19|20)\d{2})",
        r"(?:Annual\s+Report|Form\s+10-K)\s*(?:for\s+)?((?:19|20)\d{2})",
        r"for\s+the\s+(?:financial\s+)?year\s+ended[^\n]{0,60}?((?:19|20)\d{2})",
    )
    years: Counter[str] = Counter()
    for pattern in patterns:
        years.update(re.findall(pattern, text, flags=re.IGNORECASE))
    return years.most_common(1)[0][0] if years else "待人工确认"


def infer_meta(
    filename: str, pages: Optional[List[PageText]] = None,
    company: str = "", year: str = "", document_type: str = "",
) -> DocumentMeta:
    sample = _content_sample(pages)
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", sample))
    latin_count = len(re.findall(r"[A-Za-z]", sample))
    language = "中文" if cjk_count >= max(20, latin_count * 0.15) else "英文"
    detected_type = document_type.strip() or next(
        (name for name in ("年度报告", "年报", "财务报告", "招股说明书", "招股书", "ESG报告", "审计报告") if name in sample[:8000]),
        "Annual Report" if re.search(r"Annual\s+Report", sample[:8000], re.I) else "PDF",
    )
    detected_company = company.strip() or _infer_company(sample)
    detected_year = year.strip() or _infer_report_year(sample)
    return DocumentMeta(
        company=detected_company,
        language=language,
        year=detected_year,
        document_type=detected_type,
        source_filename=filename,
        company_source="用户填写" if company.strip() else "正文识别",
        year_source="用户填写" if year.strip() else "正文识别",
    )


def evidence_name(index: int, meta: DocumentMeta, page_number: int) -> str:
    pieces = [
        f"{index:03d}", meta.company, meta.language, meta.year,
        meta.document_type, f"p{page_number}",
    ]
    return "_".join(safe_filename(p) for p in pieces) + ".pdf"
