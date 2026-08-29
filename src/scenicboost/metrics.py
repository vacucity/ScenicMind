from __future__ import annotations

import numpy as np


def regression_metrics(actual, predicted) -> dict[str, float]:
    y = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    if y.shape != p.shape:
        raise ValueError("actual 和 predicted 的形状不一致")
    error = p - y
    absolute = np.abs(error)
    nonzero = y != 0
    return {
        "rows": int(len(y)),
        "mae": float(np.mean(absolute)),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "wape": float(absolute.sum() / max(np.abs(y).sum(), 1.0) * 100),
        "mape": float(np.mean(absolute[nonzero] / np.abs(y[nonzero])) * 100) if nonzero.any() else float("nan"),
        "bias": float(np.mean(error)),
    }

