from app.services.credit_engine.policy import credit_policy
from app.services.credit_engine.schemas import AnomalyFeature


def suppress_overlaps(anomalies: dict[str, AnomalyFeature]) -> dict[str, AnomalyFeature]:
    selected = dict(anomalies)
    for group in credit_policy()["suppression_groups"]:
        present = [name for name in group if name in selected]
        for suppressed in present[1:]:
            selected.pop(suppressed, None)
    return selected
