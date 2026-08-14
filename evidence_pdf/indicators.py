from dataclasses import dataclass


@dataclass(frozen=True)
class IndicatorSpec:
    canonical: str
    aliases: tuple[str, ...]
    amount_cues: tuple[str, ...]


R_AND_D = IndicatorSpec(
    canonical="研发投入",
    aliases=(
        "研发投入金额", "研发投入总额", "研发投入", "研发费用", "研究与开发费用",
        "研發投入金額", "研發投入", "研發費用",
        "R&D expenditure", "R&D expenses", "R&D costs",
        "research and development expenditure", "research and development expenditures",
        "research and development expenses", "research and development costs",
        "research and development spending",
        "研究開発費", "研究開発費用", "연구개발비", "연구 개발 비용",
        "Forschungs- und Entwicklungskosten", "F&E-Aufwendungen",
        "dépenses de recherche et développement", "frais de R&D",
        "gastos de investigación y desarrollo", "despesas de pesquisa e desenvolvimento",
    ),
    amount_cues=(
        "金额", "金額", "费用", "費用", "支出", "投入", "成本",
        "expenditure", "expenditures", "expense", "expenses", "cost", "costs", "spending",
        "研究開発費", "연구개발비", "kosten", "aufwendungen", "dépenses", "frais", "gastos", "despesas",
    ),
)


CATALOG = (R_AND_D,)


def resolve_indicator(query: str) -> IndicatorSpec:
    normalized = " ".join((query or "").strip().casefold().split())
    for spec in CATALOG:
        candidates = (spec.canonical,) + spec.aliases
        if any(normalized == " ".join(item.casefold().split()) for item in candidates):
            return spec
    # Unknown indicators still work as exact-term searches. They deliberately do
    # not receive invented synonyms; this keeps the result explainable.
    clean = (query or "").strip()
    return IndicatorSpec(clean, (clean,), (clean,))


def alias_preview(spec: IndicatorSpec, limit: int = 12) -> str:
    return "、".join(spec.aliases[:limit])
