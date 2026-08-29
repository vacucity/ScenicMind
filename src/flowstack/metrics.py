from __future__ import annotations

import numpy as np


def regression_metrics(y_true, y_pred) -> dict[str, float]:
    """与 baseline 完全一致的五项评估指标。"""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    return {
        "R2": 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
        "MAPE(%)": float(np.mean(np.abs((y_true - y_pred) / np.maximum(y_true, 1e-9))) * 100),
        "WAPE(%)": float(np.abs(y_true - y_pred).sum() / y_true.sum() * 100),
        "RMSE": float(np.sqrt(np.mean((y_true - y_pred) ** 2))),
        "MAE": float(np.mean(np.abs(y_true - y_pred))),
    }
