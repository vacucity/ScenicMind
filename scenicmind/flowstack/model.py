"""FlowStack 核心模型：冗余选择 + 差分目标 + 多样化基学习器 + OOF 堆叠 + 场景校正。

训练流程（全部仅在训练集上 fit，测试/预测阶段纯 transform）：
  1. 编码：数值化 + 类别 one-hot（holiday_name），与 baseline 特征口径一致；
  2. 冗余感知特征选择（RedundancyReducer）；
  3. 差分目标 Δvisitors = visitors - visitors_lag_1，按训练集均值/方差标准化；
  4. 四路基学习器（LGB-Huber / XGB-Huber / LGB-L1 / CatBoost-Huber），
     节假日/周末/暑期/限流样本加权；
  5. TimeSeriesSplit 前向链式 OOF 预测 → 正约束 Ridge 元学习器融合；
  6. OOF 残差 → 场景收缩中位数校正器；
  7. 共识特征重要性（元学习器权重加权的归一化 gain）。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scenicmind.flowstack.config import FlowStackConfig
from scenicmind.flowstack.redundancy import RedundancyReducer

# 描述数据质量/标签来源而非预测时点状态的字段，永不进入估计器（与 ScenicBoost 口径一致）
EXCLUDED_FEATURES = {
    "target_source", "target_quality", "target_conflict", "target_missing",
    "feature_missing_count", "quality_score", "historical_target_imputed_count",
}

GROUP_RULES = [
    ("历史客流", lambda f: f.startswith(("visitors_lag_", "visitors_roll_"))
     or f in {"visitors_trend_strength", "visitors_lag1_vs_ma7", "visitors_lag7_vs_ma28"}),
    ("天气", lambda f: f.startswith("weather_")),
    ("网络关注度", lambda f: f.startswith(("wiki_", "wechat_"))),
    ("交通可达性", lambda f: "hsr" in f or "expressway" in f),
    ("景区运营", lambda f: f in {
        "official_notice_count", "sold_out_flag", "is_closed", "is_reopen",
        "is_partial_open", "discount_flag", "free_ticket_flag", "capacity_restricted",
        "sold_out_notice_lead_days", "known_reserved_count", "daily_capacity",
        "booking_pressure_ratio",
    }),
    ("日历节假日", lambda f: f in {"year", "month", "day", "quarter", "week_of_year",
        "day_of_year", "weekday", "is_weekend", "is_rest_day", "is_makeup_workday",
        "is_month_start", "is_month_end", "is_summer_vacation", "is_winter_vacation",
        "is_peak_season", "is_offseason", "sin_doy", "cos_doy", "sin_weekday",
        "cos_weekday", "holiday_day_index", "holiday_length", "days_until_holiday_end",
        "days_to_next_holiday", "days_since_prev_holiday", "is_pre_holiday_1",
        "is_pre_holiday_3", "is_post_holiday_1", "is_post_holiday_3",
        "is_official_holiday"} or f.startswith("holiday_")),
]


def feature_group(feature: str) -> str:
    for group, rule in GROUP_RULES:
        if rule(feature):
            return group
    return "其他"


def scene_keys(row: pd.Series) -> list[str]:
    """与 ScenicBoost 一致的场景划分，用于残差校正与误差归因。"""
    keys: list[str] = []
    holiday_name = str(row.get("holiday_name", "非节假日"))
    holiday_flag = int(float(row.get("is_official_holiday", 0) or 0))
    holiday_day = int(float(row.get("holiday_day_index", 0) or 0))
    if holiday_flag or holiday_name not in {"非节假日", "None", "nan", ""}:
        if holiday_day > 0:
            keys.append(f"holiday:{holiday_name}:day:{holiday_day}")
        keys.extend([f"holiday:{holiday_name}", "holiday:any"])
    if int(float(row.get("is_summer_vacation", 0) or 0)):
        keys.append("season:summer_vacation")
    if int(float(row.get("is_peak_season", 0) or 0)):
        keys.append("season:peak")
    if int(float(row.get("is_offseason", 0) or 0)):
        keys.append("season:offseason")
    keys.append("calendar:weekend" if int(float(row.get("is_weekend", 0) or 0)) else "calendar:weekday")
    keys.append("global")
    return keys


def build_sample_weights(frame: pd.DataFrame, config: FlowStackConfig) -> np.ndarray:
    settings = {"normal": 1.0, "weekend": 1.15, "summer_vacation": 1.25,
                "official_holiday": 1.5, "capacity_restricted": 1.25, **config.sample_weights}
    weights = np.full(len(frame), float(settings["normal"]))
    for column, key in [("is_weekend", "weekend"), ("is_summer_vacation", "summer_vacation"),
                        ("is_official_holiday", "official_holiday"),
                        ("capacity_restricted", "capacity_restricted")]:
        if column in frame:
            mask = pd.to_numeric(frame[column], errors="coerce").fillna(0).to_numpy(float) > 0
            weights[mask] = np.maximum(weights[mask], float(settings[key]))
    return weights


class SceneResidualCalibrator:
    """场景残差收缩校正：只对样本充足场景的系统性中位数偏差做温和修正。"""

    def __init__(self, config):
        self.config = config
        self.adjustments: dict[str, dict[str, float]] = {}

    def fit(self, rows: pd.DataFrame, residuals: np.ndarray) -> "SceneResidualCalibrator":
        buckets: dict[str, list[float]] = {}
        for (_, row), residual in zip(rows.iterrows(), residuals):
            if not np.isfinite(residual):
                continue
            for key in scene_keys(row):
                buckets.setdefault(key, []).append(float(residual))
        self.adjustments = {}
        for key, values in buckets.items():
            count = len(values)
            median = float(np.median(values))
            shrunk = float(np.clip(median * count / (count + self.config.shrinkage),
                                   -self.config.max_absolute_adjustment,
                                   self.config.max_absolute_adjustment))
            self.adjustments[key] = {"median": median, "count": count, "adjustment": shrunk}
        return self

    def adjustment_for(self, row: pd.Series) -> tuple[float, str]:
        if not self.config.enabled:
            return 0.0, "disabled"
        for key in scene_keys(row):
            item = self.adjustments.get(key)
            if item and item["count"] >= self.config.minimum_samples:
                return item["adjustment"], key
        return 0.0, "none"

    def transform(self, rows: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
        pairs = [self.adjustment_for(row) for _, row in rows.iterrows()]
        return np.asarray([p[0] for p in pairs]), [p[1] for p in pairs]


def _build_base_learners(config: FlowStackConfig) -> dict[str, Any]:
    """四路多样化基学习器：不同算法 × 不同稳健损失，降低融合后方差。"""
    import lightgbm as lgb
    import xgboost as xgb
    from catboost import CatBoostRegressor

    rs = config.random_state
    return {
        "lgb_huber": lgb.LGBMRegressor(
            objective="huber", random_state=rs, n_jobs=4, verbose=-1, **config.lgb_params),
        "xgb_huber": xgb.XGBRegressor(
            objective="reg:pseudohubererror", random_state=rs, n_jobs=4,
            tree_method="hist", **config.xgb_params),
        "lgb_l1": lgb.LGBMRegressor(
            objective="mae", random_state=rs, n_jobs=4, verbose=-1, **config.lgb_params),
        "cat_huber": CatBoostRegressor(
            loss_function="Huber:delta=1.0", random_seed=rs, verbose=0,
            allow_writing_files=False, thread_count=4, **config.catboost_params),
    }


class FlowStackModel:
    """点预测模型。解释（特征重要性）通过独立接口输出，与预测解耦。"""

    def __init__(self, config: FlowStackConfig | None = None):
        self.config = config or FlowStackConfig()
        self.reducer = RedundancyReducer(self.config.redundancy)
        self.base_learners: dict[str, Any] = {}
        self.meta_learner = None
        self.calibrator = SceneResidualCalibrator(self.config.calibration)
        self.feature_names_raw: list[str] = []      # 编码后、去冗余前
        self.selected_features_: list[str] = []     # 去冗余后
        self.category_columns_: list[str] = []
        self.fill_values_: dict[str, float] = {}
        self.delta_mean_: float = 0.0
        self.delta_std_: float = 1.0
        self.meta_weights_: dict[str, float] = {}
        self.oof_frame_: pd.DataFrame | None = None
        self.metadata: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # 特征编码
    # ------------------------------------------------------------------
    def _raw_feature_frame(self, frame: pd.DataFrame, *, fitting: bool) -> pd.DataFrame:
        excluded = EXCLUDED_FEATURES | {self.config.date_column, self.config.target_column}
        categorical = [c for c in self.config.categorical_columns if c in frame.columns]
        numeric_cols = [
            c for c in frame.columns
            if c not in excluded and c not in categorical and not c.startswith("actual_")
        ]
        x = frame.loc[:, numeric_cols].copy()
        for col in numeric_cols:
            x[col] = pd.to_numeric(x[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        if fitting:
            self.fill_values_ = {c: float(x[c].median()) if x[c].notna().any() else 0.0
                                 for c in numeric_cols}
        for col in numeric_cols:
            x[col] = x[col].fillna(self.fill_values_.get(col, 0.0))
        if categorical:
            dummies = pd.get_dummies(
                frame[categorical].astype(str).fillna("__MISSING__"),
                prefix=[c.rstrip("_name") for c in categorical],
            ).astype(float)
            if fitting:
                self.category_columns_ = list(dummies.columns)
            dummies = dummies.reindex(columns=self.category_columns_, fill_value=0.0)
            x = pd.concat([x, dummies], axis=1)
        return x

    # ------------------------------------------------------------------
    # 训练
    # ------------------------------------------------------------------
    def fit(self, frame: pd.DataFrame) -> "FlowStackModel":
        from sklearn.linear_model import Ridge
        from sklearn.model_selection import TimeSeriesSplit

        data = frame.copy()
        data[self.config.date_column] = pd.to_datetime(data[self.config.date_column])
        data = data.sort_values(self.config.date_column).reset_index(drop=True)
        y = pd.to_numeric(data[self.config.target_column], errors="raise").to_numpy(float)
        lag1 = pd.to_numeric(data[self.config.lag1_column], errors="raise").to_numpy(float)

        x_raw = self._raw_feature_frame(data, fitting=True)
        self.feature_names_raw = list(x_raw.columns)

        # 1) 冗余感知特征选择（仅用训练数据）
        x_sel = self.reducer.fit_transform(x_raw, pd.Series(y))
        self.selected_features_ = list(x_sel.columns)

        # 2) 差分目标 + 标准化（持续性基线 + 修正量，baseline LSTM 的关键经验）
        delta = y - lag1
        self.delta_mean_, self.delta_std_ = float(delta.mean()), float(delta.std() or 1.0)
        delta_s = (delta - self.delta_mean_) / self.delta_std_

        weights = build_sample_weights(data, self.config)

        # 3) OOF 堆叠：前向链式验证产生元特征，杜绝泄漏
        n = len(data)
        names = list(_build_base_learners(self.config).keys())
        oof = np.full((n, len(names)), np.nan)
        tscv = TimeSeriesSplit(n_splits=self.config.stack.n_splits)
        for tr_idx, va_idx in tscv.split(x_sel):
            learners = _build_base_learners(self.config)
            for j, name in enumerate(names):
                learners[name].fit(
                    x_sel.iloc[tr_idx], delta_s[tr_idx], sample_weight=weights[tr_idx])
                oof[va_idx, j] = learners[name].predict(x_sel.iloc[va_idx])
        valid = ~np.isnan(oof).any(axis=1)

        # 4) 正约束 Ridge 元学习器：权重非负 → 可解释为融合比例
        self.meta_learner = Ridge(alpha=self.config.stack.meta_alpha, positive=True)
        self.meta_learner.fit(oof[valid], delta_s[valid])
        coefs = np.asarray(self.meta_learner.coef_, dtype=float)
        total = float(coefs.sum()) or 1.0
        self.meta_weights_ = {name: float(c / total) for name, c in zip(names, coefs)}

        # 5) 全量训练集拟合最终基学习器
        self.base_learners = _build_base_learners(self.config)
        for name, learner in self.base_learners.items():
            learner.fit(x_sel, delta_s, sample_weight=weights)

        # 6) OOF 残差 → 场景校正器（在还原后的客流尺度上）
        oof_pred_visitors = self.meta_learner.predict(oof[valid]) * self.delta_std_ \
            + self.delta_mean_ + lag1[valid]
        calib_rows = data.loc[valid].reset_index(drop=True)
        self.calibrator.fit(calib_rows, y[valid] - oof_pred_visitors)
        self.oof_frame_ = pd.DataFrame({
            "date": data.loc[valid, self.config.date_column].dt.strftime("%Y-%m-%d").to_numpy(),
            "actual": y[valid], "stack_prediction": oof_pred_visitors,
        })

        dates = data[self.config.date_column]
        self.metadata.update({
            "model_name": "FlowStack",
            "model_version": datetime.now(timezone.utc).strftime("flowstack-%Y%m%dT%H%M%SZ"),
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "training_start": dates.min().strftime("%Y-%m-%d"),
            "training_end": dates.max().strftime("%Y-%m-%d"),
            "training_rows": int(n),
            "raw_feature_count": len(self.feature_names_raw),
            "selected_feature_count": len(self.selected_features_),
            "dropped_redundant": self.reducer.dropped_features_,
            "meta_weights": self.meta_weights_,
        })
        return self

    # ------------------------------------------------------------------
    # 预测
    # ------------------------------------------------------------------
    def _stack_predict_visitors(self, frame: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
        if self.meta_learner is None:
            raise RuntimeError("模型尚未训练或加载")
        x_raw = self._raw_feature_frame(frame, fitting=False)
        x_raw = x_raw.reindex(columns=self.feature_names_raw, fill_value=0.0)
        x_sel = self.reducer.transform(x_raw)
        base_preds = np.column_stack([
            learner.predict(x_sel) for learner in self.base_learners.values()])
        delta_s = self.meta_learner.predict(base_preds)
        lag1 = pd.to_numeric(frame[self.config.lag1_column], errors="coerce") \
            .fillna(self.delta_mean_).to_numpy(float)
        visitors = delta_s * self.delta_std_ + self.delta_mean_ + lag1
        detail = pd.DataFrame(
            base_preds * self.delta_std_ + self.delta_mean_ + lag1[:, None],
            columns=[f"base_{k}" for k in self.base_learners], index=frame.index)
        return visitors, detail

    def predict_components(self, frame: pd.DataFrame) -> pd.DataFrame:
        raw, detail = self._stack_predict_visitors(frame)
        scene_adjustment, scene_key = self.calibrator.transform(frame)
        corrected = raw + scene_adjustment
        constrained = np.maximum(corrected, 0.0)
        if self.config.capacity_cap_enabled and self.config.capacity_column in frame:
            capacity = pd.to_numeric(
                frame[self.config.capacity_column], errors="coerce").to_numpy(float)
            constrained = np.where(capacity > 0, np.minimum(constrained, capacity), constrained)
        dates = pd.to_datetime(frame[self.config.date_column]).dt.strftime("%Y-%m-%d")
        result = pd.DataFrame({
            "date": dates.to_numpy(),
            "predicted_visitors": np.rint(constrained).astype("int64"),
            "stack_prediction": raw,
            "scene_adjustment": scene_adjustment,
            "scene_key": scene_key,
            "constraint_adjustment": constrained - corrected,
            "model_version": self.metadata.get("model_version", "unknown"),
        }, index=frame.index)
        return pd.concat([result, detail], axis=1)

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        """看板热路径稳定契约：date + 整数客流点预测 + 模型版本。"""
        result = self.predict_components(frame)
        return result[["date", "predicted_visitors", "model_version"]].reset_index(drop=True)

    # ------------------------------------------------------------------
    # 特征重要性（下游 Agent 接口）
    # ------------------------------------------------------------------
    def _learner_importance(self) -> dict[str, np.ndarray]:
        importances: dict[str, np.ndarray] = {}
        n = len(self.selected_features_)
        for name, learner in self.base_learners.items():
            if name.startswith("lgb"):
                values = learner.booster_.feature_importance(importance_type="gain")
            elif name.startswith("xgb"):
                score = learner.get_booster().get_score(importance_type="gain")
                values = np.array([score.get(f, 0.0) for f in self.selected_features_])
            else:  # catboost
                values = np.asarray(learner.get_feature_importance(), dtype=float)
            values = np.asarray(values, dtype=float)[:n]
            total = values.sum()
            importances[name] = values / total if total > 0 else np.full(n, 1.0 / n)
        return importances

    def feature_importance(self) -> pd.DataFrame:
        """共识重要性 = Σ 元学习器融合权重 × 各基学习器归一化 gain 重要性。

        同时输出：业务分组、冗余簇规模与簇成员（被合并的同维度特征），
        下游 Agent 可直接据此生成"哪个维度在驱动客流"的经营建议。
        """
        per_learner = self._learner_importance()
        consensus = np.zeros(len(self.selected_features_))
        for name, values in per_learner.items():
            consensus += self.meta_weights_.get(name, 0.0) * values
        rows = []
        for feature, value in zip(self.selected_features_, consensus):
            cluster = self.reducer.cluster_of(feature)
            rows.append({
                "feature": feature,
                "importance": float(value),
                "group": feature_group(feature),
                "cluster_size": len(cluster.members) if cluster else 1,
                "cluster_members": "|".join(cluster.members) if cluster else feature,
                **{f"importance_{k}": float(per_learner[k][self.selected_features_.index(feature)])
                   for k in per_learner},
            })
        out = pd.DataFrame(rows).sort_values("importance", ascending=False).reset_index(drop=True)
        out["rank"] = np.arange(1, len(out) + 1)
        return out

    def group_importance(self) -> pd.DataFrame:
        imp = self.feature_importance()
        grouped = imp.groupby("group", as_index=False)["importance"].sum()
        return grouped.sort_values("importance", ascending=False).reset_index(drop=True)

    def importance_payload(self, top_k: int | None = None) -> dict[str, Any]:
        """Agent 消费用 JSON 结构：字段级 + 分组级 + 冗余簇映射。"""
        imp = self.feature_importance()
        if top_k:
            imp = imp.head(top_k)
        return {
            "model_version": self.metadata.get("model_version", "unknown"),
            "meta_weights": self.meta_weights_,
            "feature_importance": imp.to_dict(orient="records"),
            "group_importance": self.group_importance().to_dict(orient="records"),
            "redundancy_clusters": self.reducer.report().to_dict(orient="records"),
        }

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------
    def save(self, directory: str | Path) -> Path:
        import joblib

        destination = Path(directory)
        destination.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, destination / "model.joblib")
        payload = {"metadata": self.metadata,
                   "selected_features": self.selected_features_,
                   "meta_weights": self.meta_weights_}
        (destination / "metadata.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return destination

    @classmethod
    def load(cls, directory: str | Path) -> "FlowStackModel":
        import joblib

        return joblib.load(Path(directory) / "model.joblib")
