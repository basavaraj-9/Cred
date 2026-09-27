from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationCaseResult:
    expected_source_types: frozenset[str]
    retrieved_source_types: tuple[str, ...]
    cited_source_types: tuple[str, ...]
    answer_status: str
    unsupported_claim_count: int


def evaluate(results: list[EvaluationCaseResult], *, k: int = 5) -> dict[str, float | int]:
    """Calculate retrieval and grounding metrics from observed, persisted results."""
    if not results:
        return {"case_count": 0}
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    hits: list[float] = []
    citation_precisions: list[float] = []
    citation_recalls: list[float] = []
    cited_cases = 0
    unsupported = 0
    for result in results:
        expected = result.expected_source_types
        retrieved = result.retrieved_source_types[:k]
        matched = expected.intersection(retrieved)
        recalls.append(len(matched) / len(expected) if expected else 1.0)
        first = next((index for index, value in enumerate(retrieved, 1) if value in expected), None)
        reciprocal_ranks.append(1 / first if first else 0.0)
        hits.append(1.0 if matched else 0.0)
        cited = set(result.cited_source_types)
        if cited:
            cited_cases += 1
        citation_precisions.append(len(cited.intersection(expected)) / len(cited) if cited else 0.0)
        citation_recalls.append(
            len(cited.intersection(expected)) / len(expected) if expected else 1.0
        )
        unsupported += result.unsupported_claim_count
    total = len(results)
    return {
        "case_count": total,
        "recall_at_k": round(sum(recalls) / total, 4),
        "mrr": round(sum(reciprocal_ranks) / total, 4),
        "hit_rate_at_k": round(sum(hits) / total, 4),
        "citation_precision": round(sum(citation_precisions) / total, 4),
        "citation_recall": round(sum(citation_recalls) / total, 4),
        "citation_coverage": round(cited_cases / total, 4),
        "unsupported_claim_rate": round(unsupported / total, 4),
    }
