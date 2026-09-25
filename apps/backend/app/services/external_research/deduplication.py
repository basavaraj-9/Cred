from __future__ import annotations

import re


def title_similarity(left: str, right: str) -> float:
    ignored = {"a", "an", "the", "limited", "ltd", "private", "pvt"}
    left_tokens = set(re.findall(r"[a-z0-9]+", left.casefold())) - ignored
    right_tokens = set(re.findall(r"[a-z0-9]+", right.casefold())) - ignored
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def near_duplicate_title(left: str, right: str, threshold: float = 0.8) -> bool:
    return title_similarity(left, right) >= threshold
