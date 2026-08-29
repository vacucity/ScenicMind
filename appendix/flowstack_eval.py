# -*- coding: utf-8 -*-
"""
FlowStack vs Baseline —— 严格按 baseline 协议的训练与评估
==========================================================
与 baseline_models.py 完全一致的协议：
  - 数据：data.xlsx（Sheet1），同一套 61 维特征口径（数值 + holiday one-hot）
  - 划分：按时间顺序 80/20，训练 1,901 天 / 测试 476 天
  - 超参寻优：RandomizedSearchCV × 25 组 × TimeSeriesSplit(5)，目标 CV-MAE，种子 42
  - 指标：R2 / MAPE / WAPE / RMSE / MAE（同一实现口径）
差异（FlowStack 的模型层改进，非协议差异）：
  - 冗余感知特征选择（仅训练集 fit）
  - 差分目标 + 标准化（树模型对单调缩放不变，StandardScaler 对树分裂等价，故不再重复缩放）
  - 四路基学习器 + OOF 堆叠 + 节假日样本加权 + 场景残差校正 + 承载量约束
"""

import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit

import lightgbm as lgb
import xgboost as xgb

from scenicmind.flowstack.config import FlowStackConfig
from scenicmind.flowstack.metrics import regression_metrics
from scenicmind.flowstack.model import FlowStackModel
from scenicmind.flowstack.redundancy import RedundancyReducer

warnings.filterwarnings("ignore")
RS = 42
np.random.seed(RS)

DATA_PATH = Path(__file__).parent / "data.xlsx"
OUT_DIR = Path(__file__).parent / "outputs"
ART_DIR = Path(__file__).parent / "artifacts" / "flowstack" / "current"
OUT_DIR.mkdir(exist_ok=True)
ART_DIR.mkdir(parents=True, exist_ok=True)

# baseline_results.md 中的参考成绩（测试集 476 天）
BASELINE = {
    "XGBoost":     {"R2": 0.8709, "MAPE(%)": 15.40, "WAPE(%)": 12.82, "RMSE": 3892.6, "MAE": 2729.7},
    "LightGBM":    {"R2": 0.8665, "MAPE(%)": 15.76, "WAPE(%)": 13.64, "RMSE": 3958.2, "MAE": 2904.0},
    "RandomForest": {"R2": 0.8586, "MAPE(%)": 15.19, "WAPE(%)": 13.01, "RMSE": 4074.0, "MAE": 2768.8},
    "LSTM":        {"R2": 0.8578, "MAPE(%)": 14.25, "WAPE(%)": 11.12, "RMSE": 4085.2, "MAE": 2366.8},
}
METRIC_KEYS = ["R2", "MAPE(%)", "WAPE(%)", "RMSE", "MAE"]
BASELINE_BEST = {  # 各指标的最强基线值（全面超越的及格线）
    "R2": max(m["R2"] for m in BASELINE.values()),
    "MAPE(%)": min(m["MAPE(%)"] for m in BASELINE.values()),
    "WAPE(%)": min(m["WAPE(%)"] for m in BASELINE.values()),
    "RMSE": min(m["RMSE"] for m in BASELINE.values()),
    "MAE": min(m["MAE"] for m in BASELINE.values()),
}

# ----------------------------------------------------------------------------
# 1. 数据加载（与 baseline 相同）
# ----------------------------------------------------------------------------
print("=" * 70)
print("1. 加载数据（与 baseline 相同口径）")
df = pd.read_excel(DATA_PATH, sheet_name="Sheet1")
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date").reset_index(drop=True)
TARGET = "visitors"
n = len(df)
split = int(n * 0.8)
print(f"   {n} 行 x {df.shape[1]} 列 | 训练 {split} / 测试 {n - split}")
print(f"   测试区间: {df['date'].iloc[split].date()} ~ {df['date'].iloc[-1].date()}")

train_frame = df.iloc[:split].reset_index(drop=True)
test_frame = df.iloc[split:].reset_index(drop=True)
y_test = test_frame[TARGET].to_numpy(float)

# ----------------------------------------------------------------------------
# 2. 编码 + 冗余感知特征选择（仅训练集 fit，供超参搜索使用；与模型内部口径一致）
# ----------------------------------------------------------------------------
print("=" * 70)
print("2. 冗余感知特征选择（Spearman 聚类 + 簇内互信息代表）")
holiday_dummies = pd.get_dummies(train_frame["holiday_name"], prefix="holiday").astype(float)
feature_cols = [c for c in train_frame.columns if c not in ("date", TARGET, "holiday_name")]
X_train_raw = pd.concat([train_frame[feature_cols].astype(float), holiday_dummies], axis=1)
y_train = train_frame[TARGET].to_numpy(float)

reducer = RedundancyReducer(FlowStackConfig().redundancy)
X_train_sel = reducer.fit_transform(X_train_raw, pd.Series(y_train))
print(f"   原始特征 {X_train_raw.shape[1]} 维 → 去冗余后 {X_train_sel.shape[1]} 维 "
      f"（合并 {len(reducer.dropped_features_)} 个冗余特征，{len(reducer.clusters)} 个簇）")
cluster_report = reducer.report()
big = cluster_report[cluster_report["cluster_size"] > 1]
for _, r in big.head(10).iterrows():
    print(f"   簇[{r['cluster_size']}] 代表={r['representative']} ← {r['members']}")

# 差分目标（与模型内部一致；MAE(delta) == MAE(visitors)，因 lag1 相互抵消）
lag1_train = train_frame["visitors_lag_1"].to_numpy(float)
delta = y_train - lag1_train
d_mean, d_std = float(delta.mean()), float(delta.std())
delta_s = (delta - d_mean) / d_std

# ----------------------------------------------------------------------------
# 3. 超参寻优（与 baseline 相同：RandomizedSearchCV×25×TSCV5，MAE，种子 42）
# ----------------------------------------------------------------------------
print("=" * 70)
print("3. 基学习器超参寻优（协议与 baseline 相同；目标为差分 Huber/L1 学习器）")
tscv = TimeSeriesSplit(n_splits=5)
t0 = time.time()

lgb_search = RandomizedSearchCV(
    lgb.LGBMRegressor(objective="huber", random_state=RS, n_jobs=4, verbose=-1),
    param_distributions={
        "n_estimators": [200, 400, 600, 1000],
        "learning_rate": [0.01, 0.03, 0.05, 0.1, 0.2],
        "num_leaves": [15, 31, 63, 127, 255],
        "min_child_samples": [5, 10, 20, 50],
        "subsample": [0.6, 0.8, 1.0],
        "subsample_freq": [1],
        "colsample_bytree": [0.6, 0.8, 1.0],
        "reg_alpha": [0, 0.01, 0.1, 1],
        "reg_lambda": [0, 0.01, 0.1, 1],
    },
    n_iter=25, cv=tscv, scoring="neg_mean_absolute_error",
    n_jobs=1, random_state=RS, verbose=0,
)
lgb_search.fit(X_train_sel, delta_s)
print(f"   [LGB-Huber] CV-MAE(Δ) {-lgb_search.best_score_:.4f} | {lgb_search.best_params_}")

xgb_search = RandomizedSearchCV(
    xgb.XGBRegressor(objective="reg:pseudohubererror", random_state=RS, n_jobs=4,
                     tree_method="hist"),
    param_distributions={
        "n_estimators": [200, 400, 600, 1000],
        "learning_rate": [0.01, 0.03, 0.05, 0.1, 0.2],
        "max_depth": [3, 4, 5, 6, 8, 10],
        "min_child_weight": [1, 3, 5, 10],
        "subsample": [0.6, 0.8, 1.0],
        "colsample_bytree": [0.6, 0.8, 1.0],
        "reg_alpha": [0, 0.01, 0.1, 1],
        "reg_lambda": [0, 0.01, 0.1, 1],
    },
    n_iter=25, cv=tscv, scoring="neg_mean_absolute_error",
    n_jobs=1, random_state=RS, verbose=0,
)
xgb_search.fit(X_train_sel, delta_s)
print(f"   [XGB-Huber] CV-MAE(Δ) {-xgb_search.best_score_:.4f} | {xgb_search.best_params_}")
print(f"   搜索耗时 {time.time() - t0:.0f}s（与 baseline 相同预算：25 组 x 5 折）")

# ----------------------------------------------------------------------------
# 4. 训练 FlowStack（注入寻优参数，完整流水线：选择→差分→堆叠→校正）
# ----------------------------------------------------------------------------
print("=" * 70)
print("4. 训练 FlowStack 完整流水线")
config = FlowStackConfig()
config.lgb_params = {k: v for k, v in lgb_search.best_params_.items()}
config.xgb_params = {k: v for k, v in xgb_search.best_params_.items()}
config.catboost_params = {**config.catboost_params, "iterations": 1000}

t0 = time.time()
model = FlowStackModel(config).fit(train_frame)
print(f"   训练耗时 {time.time() - t0:.0f}s | 元学习器融合权重: "
      + ", ".join(f"{k}={v:.3f}" for k, v in model.meta_weights_.items()))

# ----------------------------------------------------------------------------
# 5. 测试集评估与基线对比
# ----------------------------------------------------------------------------
print("=" * 70)
print("5. 测试集性能（476 天，时间外样本）")
components = model.predict_components(test_frame)
pred = components["predicted_visitors"].to_numpy(float)
raw_stack = components["stack_prediction"].to_numpy(float)

metrics_final = regression_metrics(y_test, pred)
metrics_stack = regression_metrics(y_test, raw_stack)
results = {"FlowStack": metrics_final, "FlowStack(无场景校正)": metrics_stack, **BASELINE}
res_df = pd.DataFrame(results).T[METRIC_KEYS]
print(res_df.round(4).to_string())

print("\n   逐项 vs 最强基线（全面超越判定）:")
win_all = True
for key in METRIC_KEYS:
    mine = metrics_final[key]
    best = BASELINE_BEST[key]
    win = mine > best if key == "R2" else mine < best
    win_all &= win
    delta_show = (mine - best) if key == "R2" else (best - mine)
    print(f"   {key:9s}: FlowStack {mine:10.4f} vs 最强基线 {best:10.4f} "
          f"→ {'超越' if win else '未超越'} (+{delta_show:.4f})" if win else
          f"   {key:9s}: FlowStack {mine:10.4f} vs 最强基线 {best:10.4f} → 未超越")
print(f"\n   五项全面超越最强基线: {'是' if win_all else '否'}")

# ----------------------------------------------------------------------------
# 6. 产物输出
# ----------------------------------------------------------------------------
print("=" * 70)
print("6. 输出产物")
res_df.round(6).to_csv(OUT_DIR / "flowstack_metrics.csv", encoding="utf-8-sig")

vs_rows = []
for key in METRIC_KEYS:
    mine = metrics_final[key]
    best = BASELINE_BEST[key]
    best_model = max(BASELINE, key=lambda m: BASELINE[m][key]) if key == "R2" \
        else min(BASELINE, key=lambda m: BASELINE[m][key])
    win = mine > best if key == "R2" else mine < best
    vs_rows.append({
        "metric": key, "flowstack": round(mine, 4),
        "baseline_best": round(best, 4), "baseline_best_model": best_model,
        "improvement": round((mine - best) if key == "R2" else (best - mine), 4),
        "improvement_pct": round(abs(mine - best) / abs(best) * 100, 2),
        "beat_baseline": bool(win),
    })
vs_df = pd.DataFrame(vs_rows)
vs_df.to_csv(OUT_DIR / "flowstack_vs_baseline.csv", index=False, encoding="utf-8-sig")

pred_df = pd.DataFrame({
    "date": components["date"].to_numpy(),
    "y_true": y_test,
    "FlowStack": np.round(pred, 1),
    "FlowStack_raw_stack": np.round(raw_stack, 1),
    "scene_adjustment": np.round(components["scene_adjustment"].to_numpy(float), 1),
    "base_lgb_huber": np.round(components["base_lgb_huber"].to_numpy(float), 1),
    "base_xgb_huber": np.round(components["base_xgb_huber"].to_numpy(float), 1),
    "base_lgb_l1": np.round(components["base_lgb_l1"].to_numpy(float), 1),
    "base_cat_huber": np.round(components["base_cat_huber"].to_numpy(float), 1),
})
pred_df.to_csv(OUT_DIR / "flowstack_test_predictions.csv", index=False, encoding="utf-8-sig")

imp = model.feature_importance()
imp.to_csv(OUT_DIR / "flowstack_feature_importance.csv", index=False, encoding="utf-8-sig")
model.group_importance().to_csv(
    OUT_DIR / "flowstack_group_importance.csv", index=False, encoding="utf-8-sig")
cluster_report.to_csv(OUT_DIR / "flowstack_redundancy_clusters.csv",
                      index=False, encoding="utf-8-sig")
with open(OUT_DIR / "flowstack_agent_importance.json", "w", encoding="utf-8") as f:
    json.dump(model.importance_payload(top_k=20), f, ensure_ascii=False, indent=2)

model.save(ART_DIR / "model")
with open(ART_DIR / "metrics.json", "w", encoding="utf-8") as f:
    json.dump({"test_metrics": metrics_final, "stack_only_metrics": metrics_stack,
               "baseline_best": BASELINE_BEST, "beat_all": bool(win_all),
               "meta_weights": model.meta_weights_,
               "lgb_params": config.lgb_params, "xgb_params": config.xgb_params},
              f, ensure_ascii=False, indent=2)

print("\n   特征重要性 Top10（共识 = 融合权重 x 归一化 gain）:")
print(imp.head(10)[["rank", "feature", "importance", "group", "cluster_size"]]
      .to_string(index=False))

fig, axes = plt.subplots(2, 1, figsize=(15, 9), sharex=True,
                         gridspec_kw={"height_ratios": [3, 1]})
date_test = test_frame["date"]
axes[0].plot(date_test, y_test, label="Actual", color="#333333", lw=1.2)
axes[0].plot(date_test, pred,
             label=f"FlowStack (R2={metrics_final['R2']:.4f}, MAE={metrics_final['MAE']:.0f})",
             color="#c0392b", lw=1.0, alpha=0.9)
axes[0].axhline(0, color="#999999", lw=0.5)
axes[0].set_title("FlowStack vs Actual - test set (476 days)")
axes[0].legend(); axes[0].grid(alpha=0.3)
axes[1].bar(date_test, y_test - pred, color="#7f8c8d", width=1.0)
axes[1].set_title("Residual (actual - predicted)")
axes[1].grid(alpha=0.3)
fig.autofmt_xdate(); fig.tight_layout()
fig.savefig(OUT_DIR / "flowstack_prediction_curve.png", dpi=130)

print(f"\n   产物目录: {OUT_DIR} / {ART_DIR}")
print("DONE_MARKER_OK")
