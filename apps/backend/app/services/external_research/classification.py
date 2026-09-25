from __future__ import annotations

import re


def classify_legal_event(text: str) -> tuple[str, str]:
    value = text.casefold()
    rules = (
        (r"dismissed|acquitted|charges? withdrawn", "LEGAL_CASE_DISMISSED", "NEUTRAL"),
        (r"convicted|found guilty", "LEGAL_CONVICTION_REPORTED", "NEGATIVE"),
        (r"penalt(?:y|ies)|fine imposed|monetary sanction", "REGULATORY_PENALTY_ORDER", "NEGATIVE"),
        (
            r"under investigation|investigation opened|probe opened",
            "REGULATORY_INVESTIGATION_REPORTED",
            "REVIEW",
        ),
        (r"alleged|allegation|accused", "LEGAL_ALLEGATION_REPORTED", "REVIEW"),
    )
    for pattern, code, impact in rules:
        if re.search(pattern, value):
            return code, impact
    return "LEGAL_STATUS_UNCERTAIN", "REVIEW"


def classify_rating_action(text: str) -> str:
    value = text.casefold()
    rules = (
        (r"downgrad", "DOWNGRADE"),
        (r"upgrad", "UPGRADE"),
        (r"withdraw", "WITHDRAWN"),
        (r"affirm", "AFFIRMED"),
        (r"outlook.+(?:revis|chang)|(?:revis|chang).+outlook", "OUTLOOK_CHANGE"),
    )
    return next((action for pattern, action in rules if re.search(pattern, value)), "UNKNOWN")


def classify_outlook(text: str) -> tuple[str, str]:
    value = text.casefold()
    positive = any(word in value for word in ("growth", "strong demand", "improving", "positive"))
    negative = any(word in value for word in ("decline", "weak demand", "pressure", "negative"))
    if positive and negative:
        return "OUTLOOK_MIXED", "MIXED"
    if positive:
        return "OUTLOOK_POSITIVE", "POSITIVE"
    if negative:
        return "OUTLOOK_NEGATIVE", "NEGATIVE"
    return "OUTLOOK_UNCERTAIN", "REVIEW"
