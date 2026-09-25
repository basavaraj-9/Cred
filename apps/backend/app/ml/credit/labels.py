from app.ml.credit.label_policy import label_policy
from app.ml.credit.schemas import LabelResult
from app.models.credit_ml import CreditMLObservation, CreditOutcome
from app.models.enums import CreditLabelQuality, CreditLabelStatus, VerificationStatus


def assign_label(observation: CreditMLObservation, outcomes: list[CreditOutcome]) -> LabelResult:
    policy = label_policy()
    relevant = [
        row
        for row in outcomes
        if row.company_id == observation.company_id
        and row.observation_date == observation.observation_date
    ]
    qualities = {row.label_quality for row in relevant}
    quality = next(iter(qualities)) if len(qualities) == 1 else CreditLabelQuality.UNKNOWN
    if (
        any(row.verification_status == VerificationStatus.CONFLICTING for row in relevant)
        or len(qualities) > 1
    ):
        return LabelResult(None, CreditLabelStatus.CONFLICTING, quality, None)
    defaults = [
        row
        for row in relevant
        if row.outcome_type.value in policy["default_events"]
        and row.outcome_date
        and observation.outcome_window_start <= row.outcome_date <= observation.outcome_window_end
    ]
    complete = [
        row
        for row in relevant
        if row.outcome_type.value in policy["non_default_evidence"]
        and row.outcome_date
        and row.outcome_date >= observation.outcome_window_end
    ]
    if defaults and complete:
        return LabelResult(None, CreditLabelStatus.CONFLICTING, quality, None)
    if defaults:
        row = min(defaults, key=lambda item: item.outcome_date or observation.outcome_window_end)
        return LabelResult(1, CreditLabelStatus.LABELED_POSITIVE, row.label_quality, row.id)
    if complete:
        row = min(complete, key=lambda item: item.outcome_date or observation.outcome_window_end)
        return LabelResult(0, CreditLabelStatus.LABELED_NEGATIVE, row.label_quality, row.id)
    if any(row.outcome_type.value in policy["review_events"] for row in relevant):
        return LabelResult(None, CreditLabelStatus.NEEDS_REVIEW, quality, None)
    return LabelResult(None, CreditLabelStatus.CENSORED, quality, None)
