from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pandas as pd

from src.scenicboost.config import CalibrationConfig, load_config
from src.scenicboost.export import build_agent_contexts, build_forecast_actual
from src.scenicboost.model import SceneResidualCalibrator
from src.scenicboost.schema import select_model_features, validate_forecast_safe_columns
from src.scenicboost.training import rolling_folds


def test_model_features_exclude_target_and_quality_metadata():
    frame = pd.DataFrame(
        {
            "date": ["2025-01-01"],
            "visitors": [100],
            "target_source": ["official"],
            "quality_score": [1.0],
            "holiday_name": ["元旦"],
            "visitors_lag_1": [90],
        }
    )
    features, categorical = select_model_features(frame)
    assert features == ["holiday_name", "visitors_lag_1"]
    assert categorical == ["holiday_name"]


def test_forecast_safe_guard_rejects_realized_weather():
    try:
        validate_forecast_safe_columns(["visitors_lag_1", "actual_temp_max"])
    except ValueError as exc:
        assert "当天实况字段" in str(exc)
    else:
        raise AssertionError("actual_* should be rejected")


def test_scene_calibrator_shrinks_and_selects_specific_scene():
    rows = pd.DataFrame(
        {
            "holiday_name": ["国庆节"] * 6,
            "is_official_holiday": [1] * 6,
            "holiday_day_index": [1] * 6,
            "is_weekend": [0] * 6,
        }
    )
    calibrator = SceneResidualCalibrator(
        CalibrationConfig(minimum_samples=5, shrinkage=6.0, max_absolute_adjustment=6000)
    ).fit(rows, np.asarray([1000, 1000, 1000, 1000, 1000, 1000]))
    value, key = calibrator.adjustment_for(rows.iloc[0])
    assert key == "holiday:国庆节:day:1"
    assert value == 500.0


def test_rolling_folds_never_train_on_validation_or_future(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"backtest": {"folds": 3, "validation_days": 10, "minimum_training_days": 50}}),
        encoding="utf-8",
    )
    config = load_config(config_path)
    folds = list(rolling_folds(100, config))
    assert len(folds) == 3
    for _, train, validation in folds:
        assert train.max() < validation.min()


def test_export_contract_keeps_prediction_and_actual_together():
    predictions = pd.DataFrame(
        {"date": ["2025-01-01"], "predicted_visitors": [120], "model_version": ["v1"]}
    )
    actuals = pd.DataFrame({"date": ["2025-01-01"], "visitors": [100]})
    comparison = build_forecast_actual(predictions, actuals)
    assert comparison.loc[0, "error"] == 20
    assert comparison.loc[0, "absolute_percentage_error"] == 20
    contexts = build_agent_contexts(comparison)
    assert contexts["daily"][0]["metrics"]["actual_visitors"] == 100

