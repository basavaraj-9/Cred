from __future__ import annotations

from typing import Any

from sklearn.calibration import CalibratedClassifierCV  # type: ignore[import-untyped]


def calibrate_sigmoid(
    model: Any, train_x: list[list[object]], train_y: list[int]
) -> tuple[Any, str, str | None]:
    class_counts = [train_y.count(label) for label in set(train_y)]
    if len(class_counts) < 2 or min(class_counts) < 2:
        model.fit(train_x, train_y)
        return model, "unavailable", "Training split needs at least two examples per class"
    calibrated = CalibratedClassifierCV(model, method="sigmoid", cv=min(3, min(class_counts)))
    calibrated.fit(train_x, train_y)
    return calibrated, "sigmoid", None
