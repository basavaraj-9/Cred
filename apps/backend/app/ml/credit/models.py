from __future__ import annotations

from typing import Any

from sklearn.ensemble import RandomForestClassifier  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from xgboost import XGBClassifier  # type: ignore[import-untyped]

from app.ml.credit.preprocessing import FeatureLayout, build_preprocessor

MODEL_VERSIONS = {
    "logistic_regression": "credit_logreg_v1",
    "random_forest": "credit_random_forest_v1",
    "xgboost": "credit_xgboost_v1",
}


def build_candidate(
    name: str,
    layout: FeatureLayout,
    config: dict[str, object],
    *,
    seed: int,
    scale_pos_weight: float,
) -> Pipeline:
    if name == "logistic_regression":
        params = config[name]
        assert isinstance(params, dict)
        classifier: Any = LogisticRegression(
            max_iter=int(params["max_iter"]),
            class_weight=str(params["class_weight"]),
            C=float(params["C"]),
            random_state=seed,
        )
        scale = True
    elif name == "random_forest":
        params = config[name]
        assert isinstance(params, dict)
        classifier = RandomForestClassifier(
            n_estimators=int(params["n_estimators"]),
            max_depth=int(params["max_depth"]),
            min_samples_leaf=int(params["min_samples_leaf"]),
            class_weight=str(params["class_weight"]),
            random_state=seed,
            n_jobs=1,
        )
        scale = False
    elif name == "xgboost":
        params = config[name]
        assert isinstance(params, dict)
        classifier = XGBClassifier(
            n_estimators=int(params["n_estimators"]),
            max_depth=int(params["max_depth"]),
            learning_rate=float(params["learning_rate"]),
            subsample=float(params["subsample"]),
            colsample_bytree=float(params["colsample_bytree"]),
            objective=str(params["objective"]),
            eval_metric=str(params["eval_metric"]),
            n_jobs=int(params["n_jobs"]),
            scale_pos_weight=scale_pos_weight,
            random_state=seed,
        )
        scale = False
    else:
        raise ValueError(f"Unknown credit model family: {name}")
    return Pipeline(
        [
            ("preprocessor", build_preprocessor(layout, scale_numeric=scale)),
            ("classifier", classifier),
        ]
    )


def feature_diagnostics(model: Pipeline) -> dict[str, float]:
    preprocessor = model.named_steps["preprocessor"]
    classifier = model.named_steps["classifier"]
    names = list(preprocessor.get_feature_names_out())
    if hasattr(classifier, "coef_"):
        values = classifier.coef_[0]
    elif hasattr(classifier, "feature_importances_"):
        values = classifier.feature_importances_
    else:
        return {}
    pairs = sorted(zip(names, values), key=lambda item: abs(float(item[1])), reverse=True)
    return {str(name): float(value) for name, value in pairs}
