from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.scenicboost.config import BacktestConfig, CalibrationConfig, ScenicBoostConfig
from src.scenicboost.schema import feature_group, prepare_features, scene_keys, select_model_features


def _catboost():
    try:
        from catboost import CatBoostRegressor, Pool
    except ImportError as exc:  # pragma: no cover - exercised only in incomplete environments
        raise RuntimeError("缺少 CatBoost。请执行 pip install -e \".[model]\"") from exc
    return CatBoostRegressor, Pool


@dataclass
class SceneAdjustment:
    residual_median: float
    sample_count: int
    shrunk_adjustment: float


@dataclass
class SceneResidualCalibrator:
    config: CalibrationConfig = field(default_factory=CalibrationConfig)
    adjustments: dict[str, SceneAdjustment] = field(default_factory=dict)

    def fit(self, rows: pd.DataFrame, residuals: np.ndarray) -> "SceneResidualCalibrator":
        if len(rows) != len(residuals):
            raise ValueError("校准数据和残差长度不一致")
        buckets: dict[str, list[float]] = {}
        for (_, row), residual in zip(rows.iterrows(), residuals, strict=True):
            if not np.isfinite(residual):
                continue
            for key in scene_keys(row):
                buckets.setdefault(key, []).append(float(residual))
        self.adjustments = {}
        for key, values in buckets.items():
            count = len(values)
            median = float(np.median(values))
            weight = count / (count + self.config.shrinkage)
            adjustment = float(np.clip(median * weight, -self.config.max_absolute_adjustment, self.config.max_absolute_adjustment))
            self.adjustments[key] = SceneAdjustment(median, count, adjustment)
        return self

    def adjustment_for(self, row: pd.Series) -> tuple[float, str]:
        if not self.config.enabled:
            return 0.0, "disabled"
        for key in scene_keys(row):
            item = self.adjustments.get(key)
            if item and item.sample_count >= self.config.minimum_samples:
                return item.shrunk_adjustment, key
        return 0.0, "none"

    def transform(self, rows: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
        pairs = [self.adjustment_for(row) for _, row in rows.iterrows()]
        return np.asarray([p[0] for p in pairs], dtype=float), [p[1] for p in pairs]

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": asdict(self.config),
            "adjustments": {key: asdict(value) for key, value in self.adjustments.items()},
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SceneResidualCalibrator":
        result = cls(CalibrationConfig(**payload.get("config", {})))
        result.adjustments = {
            key: SceneAdjustment(**value) for key, value in payload.get("adjustments", {}).items()
        }
        return result


class ScenicBoostModel:
    """Point-forecast model. Explanations intentionally live in a separate service."""

    def __init__(self, config: ScenicBoostConfig):
        self.config = config
        self.estimator = None
        self.feature_names: list[str] = []
        self.categorical_features: list[str] = []
        self.calibrator = SceneResidualCalibrator(config.calibration)
        self.metadata: dict[str, Any] = {}

    def fit(
        self,
        frame: pd.DataFrame,
        *,
        eval_frame: pd.DataFrame | None = None,
        sample_weight: np.ndarray | None = None,
    ) -> "ScenicBoostModel":
        CatBoostRegressor, _ = _catboost()
        if not self.feature_names:
            self.feature_names, self.categorical_features = select_model_features(
                frame,
                date_column=self.config.date_column,
                target_column=self.config.target_column,
            )
        x_train = prepare_features(frame, self.feature_names, self.categorical_features)
        y_train = frame[self.config.target_column].to_numpy(dtype=float)
        parameters = dict(self.config.model_parameters)
        self.estimator = CatBoostRegressor(**parameters)
        kwargs: dict[str, Any] = {
            "X": x_train,
            "y": y_train,
            "cat_features": self.categorical_features,
            "sample_weight": sample_weight,
        }
        if eval_frame is not None and not eval_frame.empty:
            kwargs["eval_set"] = (
                prepare_features(eval_frame, self.feature_names, self.categorical_features),
                eval_frame[self.config.target_column].to_numpy(dtype=float),
            )
            kwargs["early_stopping_rounds"] = 100
            kwargs["use_best_model"] = True
        self.estimator.fit(**kwargs)
        dates = pd.to_datetime(frame[self.config.date_column])
        best_iteration = self.estimator.get_best_iteration()
        self.metadata.update(
            {
                "model_version": self.metadata.get(
                    "model_version", datetime.now(timezone.utc).strftime("scenicboost-%Y%m%dT%H%M%SZ")
                ),
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "training_start": dates.min().strftime("%Y-%m-%d"),
                "training_end": dates.max().strftime("%Y-%m-%d"),
                "training_rows": int(len(frame)),
                "feature_count": len(self.feature_names),
                "best_iteration": -1 if best_iteration is None else int(best_iteration),
            }
        )
        return self

    def fit_calibrator(self, rows: pd.DataFrame, raw_predictions: np.ndarray) -> None:
        residuals = rows[self.config.target_column].to_numpy(dtype=float) - np.asarray(raw_predictions, dtype=float)
        self.calibrator.fit(rows, residuals)

    def raw_predict(self, frame: pd.DataFrame) -> np.ndarray:
        if self.estimator is None:
            raise RuntimeError("模型尚未训练或加载")
        x = prepare_features(frame, self.feature_names, self.categorical_features)
        return np.asarray(self.estimator.predict(x), dtype=float)

    def predict_components(self, frame: pd.DataFrame) -> pd.DataFrame:
        raw = self.raw_predict(frame)
        scene_adjustment, scene_key = self.calibrator.transform(frame)
        corrected = raw + scene_adjustment
        constrained = np.maximum(corrected, 0.0)
        if self.config.capacity_cap_enabled and "daily_capacity" in frame:
            capacity = pd.to_numeric(frame["daily_capacity"], errors="coerce").to_numpy(dtype=float)
            known = (
                pd.to_numeric(frame.get("daily_capacity_known", pd.Series(1, index=frame.index)), errors="coerce")
                .fillna(0)
                .to_numpy(dtype=float)
                > 0
            )
            constrained = np.where(known & (capacity > 0), np.minimum(constrained, capacity), constrained)
        constraint_adjustment = constrained - corrected
        dates = pd.to_datetime(frame[self.config.date_column]).dt.strftime("%Y-%m-%d")
        return pd.DataFrame(
            {
                "date": dates.to_numpy(),
                "predicted_visitors": np.rint(constrained).astype("int64"),
                "raw_model_prediction": raw,
                "scene_adjustment": scene_adjustment,
                "scene_key": scene_key,
                "constraint_adjustment": constraint_adjustment,
                "model_version": self.metadata.get("model_version", "unknown"),
            },
            index=frame.index,
        )

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Stable hot-path contract: date plus one visitor point forecast."""
        result = self.predict_components(frame)
        return result[["date", "predicted_visitors", "model_version"]].reset_index(drop=True)

    def save(self, directory: str | Path) -> Path:
        if self.estimator is None:
            raise RuntimeError("不能保存未训练模型")
        destination = Path(directory)
        destination.mkdir(parents=True, exist_ok=True)
        self.estimator.save_model(str(destination / "model.cbm"))
        payload = {
            "metadata": self.metadata,
            "feature_names": self.feature_names,
            "categorical_features": self.categorical_features,
            "feature_groups": {name: feature_group(name) for name in self.feature_names},
            "config": {
                "target_column": self.config.target_column,
                "date_column": self.config.date_column,
                "model_parameters": self.config.model_parameters,
                "backtest": asdict(self.config.backtest),
                "calibration": asdict(self.config.calibration),
                "sample_weights": self.config.sample_weights,
                "capacity_cap_enabled": self.config.capacity_cap_enabled,
                "explanation_sample_days": self.config.explanation_sample_days,
            },
            "calibrator": self.calibrator.to_dict(),
        }
        (destination / "metadata.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return destination

    @classmethod
    def load(cls, directory: str | Path) -> "ScenicBoostModel":
        CatBoostRegressor, _ = _catboost()
        source = Path(directory)
        payload = json.loads((source / "metadata.json").read_text(encoding="utf-8"))
        config_payload = payload["config"]
        config = ScenicBoostConfig(
            target_column=config_payload["target_column"],
            date_column=config_payload["date_column"],
            model_parameters=config_payload["model_parameters"],
            backtest=BacktestConfig(**config_payload["backtest"]),
            calibration=CalibrationConfig(**config_payload["calibration"]),
            sample_weights=config_payload.get("sample_weights", {}),
            capacity_cap_enabled=bool(config_payload.get("capacity_cap_enabled", False)),
            explanation_sample_days=int(config_payload.get("explanation_sample_days", 365)),
        )
        result = cls(config)
        result.estimator = CatBoostRegressor()
        result.estimator.load_model(str(source / "model.cbm"))
        result.feature_names = payload["feature_names"]
        result.categorical_features = payload["categorical_features"]
        result.calibrator = SceneResidualCalibrator.from_dict(payload.get("calibrator", {}))
        result.metadata = payload["metadata"]
        return result
