from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd

from scenicmind.scenicboost.config import ScenicBoostConfig
from scenicmind.scenicboost.metrics import regression_metrics
from scenicmind.scenicboost.model import ScenicBoostModel, SceneResidualCalibrator
from scenicmind.scenicboost.schema import select_model_features, validate_training_frame


def rolling_folds(length: int, config: ScenicBoostConfig) -> Iterator[tuple[int, np.ndarray, np.ndarray]]:
    width = config.backtest.validation_days
    requested_start = length - config.backtest.folds * width
    first_validation = max(config.backtest.minimum_training_days, requested_start)
    if first_validation >= length:
        raise ValueError("数据量不足以创建滚动回测窗口")
    fold = 0
    for start in range(first_validation, length, width):
        end = min(start + width, length)
        if end <= start:
            continue
        fold += 1
        yield fold, np.arange(0, start), np.arange(start, end)


def build_sample_weights(frame: pd.DataFrame, config: ScenicBoostConfig) -> np.ndarray:
    settings = {
        "normal": 1.0,
        "weekend": 1.15,
        "summer_vacation": 1.25,
        "official_holiday": 1.5,
        "capacity_restricted": 1.25,
        **config.sample_weights,
    }
    weights = np.full(len(frame), float(settings["normal"]), dtype=float)
    rules = [
        ("is_weekend", "weekend"),
        ("is_summer_vacation", "summer_vacation"),
        ("is_official_holiday", "official_holiday"),
        ("capacity_restricted", "capacity_restricted"),
    ]
    for column, key in rules:
        if column not in frame:
            continue
        mask = pd.to_numeric(frame[column], errors="coerce").fillna(0).to_numpy(dtype=float) > 0
        weights[mask] = np.maximum(weights[mask], float(settings[key]))
    return weights


def train_with_backtest(
    frame: pd.DataFrame,
    config: ScenicBoostConfig,
    artifact_directory: str | Path,
) -> tuple[ScenicBoostModel, pd.DataFrame, dict]:
    data = validate_training_frame(
        frame,
        date_column=config.date_column,
        target_column=config.target_column,
    )
    feature_names, categorical = select_model_features(
        data,
        date_column=config.date_column,
        target_column=config.target_column,
    )
    oof_parts: list[pd.DataFrame] = []
    prior_rows: list[pd.DataFrame] = []
    prior_raw: list[np.ndarray] = []
    fold_metrics: list[dict] = []
    best_iterations: list[int] = []

    for fold, train_index, validation_index in rolling_folds(len(data), config):
        train = data.iloc[train_index].copy()
        validation = data.iloc[validation_index].copy()
        fold_model = ScenicBoostModel(config)
        fold_model.feature_names = feature_names
        fold_model.categorical_features = categorical
        fold_model.fit(
            train,
            eval_frame=validation,
            sample_weight=build_sample_weights(train, config),
        )
        raw = fold_model.raw_predict(validation)
        best_iteration = int(fold_model.estimator.get_best_iteration())
        if best_iteration >= 0:
            best_iterations.append(best_iteration + 1)

        # Strict sequential calibration: a fold only sees residuals from older folds.
        if prior_rows:
            history_rows = pd.concat(prior_rows, ignore_index=True)
            history_raw = np.concatenate(prior_raw)
            fold_model.fit_calibrator(history_rows, history_raw)
        components = fold_model.predict_components(validation)
        actual = validation[config.target_column].to_numpy(dtype=float)
        part = components.copy()
        part["actual_visitors"] = actual
        part["fold"] = fold
        part["forecast_origin"] = (
            pd.to_datetime(validation[config.date_column]) - pd.Timedelta(days=1)
        ).dt.strftime("%Y-%m-%d").to_numpy()
        oof_parts.append(part)

        raw_metrics = regression_metrics(actual, raw)
        scenic_metrics = regression_metrics(actual, part["predicted_visitors"].to_numpy())
        lag1_metrics = regression_metrics(actual, validation["visitors_lag_1"].to_numpy())
        lag7_metrics = regression_metrics(actual, validation["visitors_lag_7"].to_numpy())
        for model_name, values in [
            ("catboost_raw", raw_metrics),
            ("scenicboost", scenic_metrics),
            ("naive_lag1", lag1_metrics),
            ("seasonal_lag7", lag7_metrics),
        ]:
            fold_metrics.append({"fold": fold, "model": model_name, **values})
        prior_rows.append(validation)
        prior_raw.append(raw)

    if not oof_parts:
        raise ValueError("没有生成任何回测结果")
    oof = pd.concat(oof_parts, ignore_index=True)
    calibration_rows = pd.concat(prior_rows, ignore_index=True)
    calibration_raw = np.concatenate(prior_raw)

    final_parameters = dict(config.model_parameters)
    if best_iterations:
        final_parameters["iterations"] = max(100, int(np.median(best_iterations)))
    final_config = replace(config, model_parameters=final_parameters)
    final_model = ScenicBoostModel(final_config)
    final_model.feature_names = feature_names
    final_model.categorical_features = categorical
    final_model.fit(data, sample_weight=build_sample_weights(data, final_config))
    final_model.fit_calibrator(calibration_rows, calibration_raw)
    final_model.metadata["backtest_folds"] = int(oof["fold"].nunique())
    final_model.metadata["backtest_start"] = str(oof["date"].min())
    final_model.metadata["backtest_end"] = str(oof["date"].max())

    overall = []
    actual = oof["actual_visitors"].to_numpy(dtype=float)
    for model_name, prediction_column in [
        ("catboost_raw", "raw_model_prediction"),
        ("scenicboost", "predicted_visitors"),
    ]:
        overall.append({"scope": "all", "model": model_name, **regression_metrics(actual, oof[prediction_column])})
    holiday_mask = data.set_index(config.date_column).reindex(pd.to_datetime(oof["date"]))["is_official_holiday"].fillna(0).to_numpy() > 0
    if holiday_mask.any():
        overall.append(
            {
                "scope": "official_holiday",
                "model": "scenicboost",
                **regression_metrics(actual[holiday_mask], oof.loc[holiday_mask, "predicted_visitors"]),
            }
        )
    metrics = {
        "overall": overall,
        "folds": fold_metrics,
        "selected_final_iterations": final_parameters.get("iterations"),
    }

    destination = Path(artifact_directory)
    destination.mkdir(parents=True, exist_ok=True)
    final_model.save(destination / "model")
    oof.to_csv(destination / "backtest_predictions.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(fold_metrics).to_csv(destination / "backtest_metrics.csv", index=False, encoding="utf-8-sig")
    (destination / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return final_model, oof, metrics

