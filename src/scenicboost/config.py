from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BacktestConfig:
    folds: int = 5
    validation_days: int = 90
    minimum_training_days: int = 730


@dataclass(frozen=True)
class CalibrationConfig:
    enabled: bool = True
    minimum_samples: int = 5
    shrinkage: float = 10.0
    max_absolute_adjustment: float = 6000.0


@dataclass(frozen=True)
class ScenicBoostConfig:
    target_column: str = "visitors"
    date_column: str = "date"
    model_parameters: dict[str, Any] = field(default_factory=dict)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    sample_weights: dict[str, float] = field(default_factory=dict)
    capacity_cap_enabled: bool = False
    explanation_sample_days: int = 365


DEFAULT_MODEL_PARAMETERS: dict[str, Any] = {
    "loss_function": "RMSE",
    "eval_metric": "MAE",
    "iterations": 1000,
    "learning_rate": 0.03,
    "depth": 7,
    "l2_leaf_reg": 6.0,
    "random_strength": 0.5,
    "bagging_temperature": 0.5,
    "random_seed": 42,
    "allow_writing_files": False,
    "verbose": False,
    "thread_count": -1,
}


def load_config(path: str | Path) -> ScenicBoostConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    model_parameters = {**DEFAULT_MODEL_PARAMETERS, **raw.get("model_parameters", {})}
    return ScenicBoostConfig(
        target_column=raw.get("target_column", "visitors"),
        date_column=raw.get("date_column", "date"),
        model_parameters=model_parameters,
        backtest=BacktestConfig(**raw.get("backtest", {})),
        calibration=CalibrationConfig(**raw.get("calibration", {})),
        sample_weights=raw.get("sample_weights", {}),
        capacity_cap_enabled=bool(raw.get("capacity_cap_enabled", False)),
        explanation_sample_days=int(raw.get("explanation_sample_days", 365)),
    )

