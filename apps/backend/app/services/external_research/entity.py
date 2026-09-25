from __future__ import annotations

import re

LEGAL_SUFFIXES = {"limited", "ltd", "private", "pvt", "inc", "llc", "corp", "corporation"}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.casefold())
        if token not in LEGAL_SUFFIXES and len(token) > 1
    }


def entity_match(target: str, candidate: str, aliases: tuple[str, ...] = ()) -> tuple[str, float]:
    names = (target, *aliases)
    normalized_candidate = " ".join(sorted(_tokens(candidate)))
    for name in names:
        if normalized_candidate == " ".join(sorted(_tokens(name))):
            return "MATCHED", 1.0
    target_tokens = _tokens(target)
    candidate_tokens = _tokens(candidate)
    if not target_tokens or not candidate_tokens:
        return "AMBIGUOUS", 0.4
    score = len(target_tokens & candidate_tokens) / len(target_tokens | candidate_tokens)
    if score >= 0.8:
        return "MATCHED", round(score, 4)
    if score >= 0.5:
        return "AMBIGUOUS", round(score, 4)
    return "MISMATCH", round(score, 4)
