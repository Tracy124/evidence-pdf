import re
import unicodedata

from .models import DocumentMeta, Evidence, PageText
from .utils import evidence_name


VALUE_RE = re.compile(
    r"(?:人民币|RMB|CNY|USD|US\$|HKD|€|£|¥|\$)?\s*"
    r"(?:\(?-?\d{1,3}(?:[,，]\d{3})+(?:\.\d+)?\)?|\(?-?\d+(?:\.\d+)?\)?)"
    r"\s*(?:亿元|万元|千元|百万元|million|billion|thousand|元|%|％)?",
    re.IGNORECASE,
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text or "")).strip()


def _term_hits(text: str, terms: list[str]) -> tuple[list[str], list[int]]:
    folded = text.casefold()
    hits, positions = [], []
    for term in terms:
        normalized_term = normalize(term)
        pos = folded.find(normalized_term.casefold())
        if pos >= 0:
            hits.append(term)
            positions.append(pos)
    return hits, positions


def _excerpt(text: str, position: int, radius: int = 180) -> str:
    start, end = max(0, position - radius), min(len(text), position + radius)
    prefix = "…" if start else ""
    suffix = "…" if end < len(text) else ""
    return prefix + text[start:end].strip() + suffix


def _value_candidate(text: str, position: int) -> str:
    window = text[max(0, position - 80): position + 220]
    candidates = []
    for match in VALUE_RE.finditer(window):
        value = normalize(match.group(0))
        if not value or re.fullmatch(r"\d{4}", value):
            continue
        distance = abs((max(0, position - 80) + match.start()) - position)
        candidates.append((distance, value))
    return min(candidates, default=(0, "待人工确认"))[1]


def extract_evidence(
    pages: list[PageText], terms: list[str], meta: DocumentMeta,
    max_pages: int = 3, min_score: float = 1.0, start_index: int = 1,
) -> list[Evidence]:
    normalized_pages = [(page, normalize(page.text)) for page in pages]
    ranked = []
    for page, text in normalized_pages:
        hits, positions = _term_hits(text, terms)
        if not hits:
            continue
        occurrences = sum(text.casefold().count(normalize(t).casefold()) for t in hits)
        score = round(len(hits) * 2 + min(occurrences, 8) * 0.25, 2)
        if score >= min_score:
            ranked.append((score, page.page_number, text, hits, min(positions)))
    ranked.sort(key=lambda item: (-item[0], item[1]))

    results = []
    indicator = " / ".join(terms)
    for offset, (score, page_number, text, hits, position) in enumerate(ranked[:max_pages]):
        index = start_index + offset
        results.append(Evidence(
            index=index, company=meta.company, indicator=indicator,
            value_candidate=_value_candidate(text, position),
            source_filename=meta.source_filename, page_number=page_number,
            language=meta.language, year=meta.year, document_type=meta.document_type,
            matched_terms="; ".join(hits), score=score,
            excerpt=_excerpt(text, position),
            evidence_filename=evidence_name(index, meta, page_number),
        ))
    return results
