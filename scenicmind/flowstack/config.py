from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RedundancyConfig:
    """冗余特征处理配置。

    corr_threshold: Spearman 相关系数绝对值阈值，超过即视为同一冗余簇。
    max_per_cluster: 每个冗余簇最多保留的代表特征数（按互信息排序）。
    """

    enabled: bool = True
    corr_threshold: float = 0.90
    max_per_cluster: int = 1


@dataclass
class StackConfig:
    """堆叠融合配置。"""

    n_splits: int = 5            # OOF 前向链式折数（与 baseline 的 TimeSeriesSplit(5) 一致）
    meta_alpha: float = 1.0      # 元学习器 Ridge 正则强度（正约束，权重可解释为融合比例）
    valid_tail_ratio: float = 0.1  # CatBoost 早停用训练集尾部比例


@dataclass
class CalibrationConfig:
    """场景残差校正配置（沿用 ScenicBoost 思路，只对可解释的系统性偏差做收缩校正）。"""

    enabled: bool = True
    shrinkage: float = 30.0
    minimum_samples: int = 8
    max_absolute_adjustment: float = 6000.0


@dataclass
class FlowStackConfig:
    date_column: str = "date"
    target_column: str = "visitors"
    lag1_column: str = "visitors_lag_1"
    capacity_column: str = "daily_capacity"
    categorical_columns: tuple[str, ...] = ("holiday_name",)
    # 与 ScenicBoost 一致的场景加权，强化节假日/高峰学习
    sample_weights: dict[str, float] = field(
        default_factory=lambda: {
            "normal": 1.0,
            "weekend": 1.15,
            "summer_vacation": 1.25,
            "official_holiday": 1.5,
            "capacity_restricted": 1.25,
        }
    )
    capacity_cap_enabled: bool = True
    redundancy: RedundancyConfig = field(default_factory=RedundancyConfig)
    stack: StackConfig = field(default_factory=StackConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    # 基学习器超参数（由评估脚本按 baseline 协议 RandomizedSearchCV 寻优后注入；
    # 下列默认值可直接训练，保证包独立可用）
    lgb_params: dict[str, Any] = field(
        default_factory=lambda: {
            "n_estimators": 600, "learning_rate": 0.03, "num_leaves": 15,
            "min_child_samples": 20, "subsample": 0.8, "subsample_freq": 1,
            "colsample_bytree": 0.6, "reg_alpha": 0.1, "reg_lambda": 0.0,
        }
    )
    xgb_params: dict[str, Any] = field(
        default_factory=lambda: {
            "n_estimators": 600, "learning_rate": 0.03, "max_depth": 3,
            "min_child_weight": 10, "subsample": 0.8, "colsample_bytree": 0.6,
            "reg_alpha": 0.1, "reg_lambda": 0.1,
        }
    )
    catboost_params: dict[str, Any] = field(
        default_factory=lambda: {
            "iterations": 1500, "learning_rate": 0.03, "depth": 6,
            "l2_leaf_reg": 3.0, "random_strength": 1.0, "bagging_temperature": 1.0,
        }
    )
    random_state: int = 42
