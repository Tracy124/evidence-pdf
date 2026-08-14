import re
import unicodedata
from typing import Optional, Union

from .indicators import IndicatorSpec, resolve_indicator
from .models import DocumentMeta, Evidence, PageText
from .utils import evidence_name


GROUPED_AMOUNT_RE = re.compile(
    r"(?<![\d])(?:\(?-?\d{1,3}(?:[,，]\d{3})+(?:\.\d+)?\)?)(?!\s*[%％项件个人岁座])"
)
PLAIN_CURRENCY_AMOUNT_RE = re.compile(
    r"(?:RMB|CNY|USD|HKD|EUR|JPY|US\$|HK\$|€|£|¥|￥|\$)\s*"
    r"-?\d+(?:[,，]\d{3})*(?:\.\d+)?",
    re.IGNORECASE,
)
UNIT_RE = re.compile(
    r"(?:单位\s*[:：]\s*)?(人民币|RMB|CNY|美元|USD|港元|HKD|欧元|EUR|日元|JPY)?\s*"
    r"(亿元|百万元|万元|千元|元|billions?|millions?|thousands?)",
    re.IGNORECASE,
)
CURRENCY_RE = re.compile(r"人民币|RMB|CNY|美元|USD|US\$|港元|HKD|HK\$|欧元|EUR|€|日元|JPY|¥|￥|£|\$", re.I)
NEGATIVE_CONTEXT_RE = re.compile(
    r"专利|項|项目数量|人數|人数|人员数量|员工数量|占比|比例|增长率|patents?|headcount|employees?",
    re.IGNORECASE,
)


def normalize(text: str, keep_newlines: bool = False) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    if keep_newlines:
        return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines())
    return re.sub(r"\s+", " ", text).strip()


def _matches(text: str, aliases: tuple[str, ...]) -> list[tuple[int, str]]:
    folded = text.casefold()
    hits = []
    for alias in aliases:
        needle = normalize(alias).casefold()
        start = 0
        while needle and (position := folded.find(needle, start)) >= 0:
            hits.append((position, alias))
            start = position + len(needle)
    return sorted(hits)


def _amount_candidates(text: str, start: int, end: int) -> list[tuple[int, str]]:
    window = text[start:end]
    candidates = []
    for pattern in (PLAIN_CURRENCY_AMOUNT_RE, GROUPED_AMOUNT_RE):
        for match in pattern.finditer(window):
            raw = normalize(match.group(0)).replace("，", ",")
            if re.fullmatch(r"\(?(?:19|20)\d{2}\)?", raw):
                continue
            candidates.append((start + match.start(), raw))
    return sorted(set(candidates), key=lambda item: item[0])


def _find_unit(context: str) -> tuple[str, str]:
    matches = list(UNIT_RE.finditer(context))
    if matches:
        currency, unit = matches[-1].groups()
        return currency or "原文未注明", unit
    currency = CURRENCY_RE.search(context)
    return (currency.group(0), "原文未注明") if currency else ("原文未注明", "原文未注明")


def _excerpt(text: str, position: int, radius: int = 240) -> str:
    start, end = max(0, position - radius), min(len(text), position + radius)
    return ("…" if start else "") + text[start:end].strip() + ("…" if end < len(text) else "")


def _page_candidate(
    page: PageText, previous_text: str, spec: IndicatorSpec, meta: DocumentMeta,
) -> Optional[dict]:
    text = normalize(page.text)
    if not text:
        return None
    hits = _matches(text, spec.aliases)
    best = None
    for position, alias in hits:
        scan_end = min(len(text), position + 520)
        amounts = _amount_candidates(text, position, scan_end)
        if not amounts:
            continue
        amount_position, value = amounts[0]
        between = text[position:amount_position]
        cue_found = any(cue.casefold() in between.casefold() or cue.casefold() in alias.casefold() for cue in spec.amount_cues)
        if not cue_found or (NEGATIVE_CONTEXT_RE.search(between) and not re.search(r"金额|金額|费用|費用|支出|expenditure|expense|cost", between, re.I)):
            continue
        unit_context = normalize(previous_text[-1800:] + " " + text[max(0, position - 220):amount_position + 80])
        currency, amount_unit = _find_unit(unit_context)
        exact_bonus = 2.0 if normalize(spec.canonical).casefold() in normalize(alias).casefold() else 0.5
        unit_bonus = 2.0 if amount_unit != "原文未注明" else 0.0
        score = round(5.0 + exact_bonus + unit_bonus + min(len(hits), 4) * 0.25, 2)
        candidate = {
            "score": score, "position": position, "alias": alias, "value": value,
            "currency": currency, "amount_unit": amount_unit, "text": text,
        }
        if best is None or candidate["score"] > best["score"]:
            best = candidate
    return best


def extract_evidence(
    pages: list[PageText], query: Union[str, IndicatorSpec], meta: DocumentMeta,
    max_pages: int = 3, min_score: float = 1.0, start_index: int = 1,
) -> list[Evidence]:
    spec = query if isinstance(query, IndicatorSpec) else resolve_indicator(query)
    ranked = []
    for page_index, page in enumerate(pages):
        previous_text = pages[page_index - 1].text if page_index else ""
        candidate = _page_candidate(page, previous_text, spec, meta)
        if candidate and candidate["score"] >= min_score:
            ranked.append((candidate["score"], page.page_number, candidate))
    ranked.sort(key=lambda item: (-item[0], item[1]))

    # If the requested metric itself appears with a valid amount, do not mix in
    # broader accounting aliases (for example, company-only R&D expenses).
    exact_ranked = [
        item for item in ranked
        if normalize(spec.canonical).casefold() in normalize(item[2]["alias"]).casefold()
    ]
    if exact_ranked:
        ranked = exact_ranked

    # The same annual-report value often appears in a summary and a detailed table.
    # Prefer the strongest, most explicit row so one fact does not become duplicates.
    deduplicated = []
    seen = set()
    for score, page_number, candidate in ranked:
        key = (candidate["value"], candidate["amount_unit"], meta.year)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append((score, page_number, candidate))

    results = []
    for offset, (score, page_number, candidate) in enumerate(deduplicated[:max_pages]):
        index = start_index + offset
        results.append(Evidence(
            index=index, company=meta.company, indicator=spec.canonical,
            value_candidate=candidate["value"], currency=candidate["currency"],
            amount_unit=candidate["amount_unit"], value_year=meta.year,
            source_filename=meta.source_filename, page_number=page_number,
            language=meta.language, year=meta.year, document_type=meta.document_type,
            matched_terms=candidate["alias"], score=score,
            excerpt=_excerpt(candidate["text"], candidate["position"]),
            evidence_filename=evidence_name(index, meta, page_number),
        ))
    return results
