from __future__ import annotations

from dataclasses import dataclass

from sklearn.compose import ColumnTransformer  # type: ignore[import-untyped]
from sklearn.impute import SimpleImputer  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # type: ignore[import-untyped]


@dataclass(frozen=True)
class FeatureLayout:
    names: list[str]
    numeric_indices: list[int]
    categorical_indices: list[int]


def infer_feature_layout(feature_rows: list[dict[str, object]]) -> FeatureLayout:
    names = sorted({name for row in feature_rows for name in row})
    categorical: list[int] = []
    numeric: list[int] = []
    for index, name in enumerate(names):
        values = [row.get(name) for row in feature_rows if row.get(name) is not None]
        if any(isinstance(value, str) for value in values):
            categorical.append(index)
        else:
            numeric.append(index)
    return FeatureLayout(names, numeric, categorical)


def matrix(feature_rows: list[dict[str, object]], layout: FeatureLayout) -> list[list[object]]:
    return [[row.get(name) for name in layout.names] for row in feature_rows]


def build_preprocessor(layout: FeatureLayout, *, scale_numeric: bool) -> ColumnTransformer:
    numeric_steps: list[tuple[str, object]] = [
        (
            "imputer",
            SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
        )
    ]
    if scale_numeric:
        numeric_steps.append(("scaler", StandardScaler()))
    numeric = Pipeline(numeric_steps)
    categorical = Pipeline(
        [
            (
                "imputer",
                SimpleImputer(
                    strategy="constant", fill_value="__MISSING__", keep_empty_features=True
                ),
            ),
            ("encoder", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        [
            ("numeric", numeric, layout.numeric_indices),
            ("categorical", categorical, layout.categorical_indices),
        ],
        remainder="drop",
    )
