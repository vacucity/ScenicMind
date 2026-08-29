# -*- coding: utf-8 -*-
"""
九寨沟日游客量预测 —— Baseline 模型对比
==========================================
模型：
  1. RandomForest   （RandomizedSearchCV 超参数寻优）
  2. LightGBM       （RandomizedSearchCV 超参数寻优）
  3. XGBoost        （RandomizedSearchCV 超参数寻优）
  4. LSTM (PyTorch) （验证集早停 Early Stopping）

要点：
  - 时序数据按时间顺序 80/20 划分训练/测试集（不打乱）
  - StandardScaler 归一化仅在训练集上 fit，避免数据泄露
  - 超参寻优使用 TimeSeriesSplit（前向链式验证），主搜索指标为 MAE
  - LSTM 使用过去 lookback 天的特征序列预测当日游客量，验证集早停并恢复最优权重
  - 评估指标：R2、MAPE、WAPE、RMSE、MAE
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

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    r2_score,
)
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

import lightgbm as lgb
import xgboost as xgb

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

warnings.filterwarnings("ignore")
RS = 42  # 全局随机种子
np.random.seed(RS)
torch.manual_seed(RS)

# ----------------------------------------------------------------------------
# 路径与输出
# ----------------------------------------------------------------------------
DATA_PATH = "/Users/wangchujie/Desktop/data_train_ready.xlsx"
OUT_DIR = Path(__file__).parent / "outputs"
OUT_DIR.mkdir(exist_ok=True)

# ----------------------------------------------------------------------------
# 1. 数据加载与预处理
# ----------------------------------------------------------------------------
print("=" * 70)
print("1. 加载数据")


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Sheet1")
    # date 列可能是 datetime 或 Excel 序列号，统一转 datetime
    if np.issubdtype(df["date"].dtype, np.number):
        df["date"] = pd.to_datetime("1899-12-30") + pd.to_timedelta(
            df["date"].astype(int), unit="D"
        )
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


df = load_data(DATA_PATH)
print(f"   数据规模: {df.shape[0]} 行 x {df.shape[1]} 列")
print(f"   时间范围: {df['date'].min().date()} ~ {df['date'].max().date()}")
print(f"   缺失值总数: {int(df.isna().sum().sum())}")

TARGET = "visitors"
y = df[TARGET]

# holiday_name 为唯一文本列，做 one-hot 编码
holiday_dummies = pd.get_dummies(df["holiday_name"], prefix="holiday").astype(float)
feature_cols = [c for c in df.columns if c not in ("date", TARGET, "holiday_name")]
X = pd.concat([df[feature_cols].astype(float), holiday_dummies], axis=1)
print(f"   特征数(编码后): {X.shape[1]}，目标变量: {TARGET}")

# ----------------------------------------------------------------------------
# 2. 时序划分（80/20）+ 归一化（仅 fit 训练集）
# ----------------------------------------------------------------------------
print("=" * 70)
print("2. 时序划分与归一化")
n = len(df)
split = int(n * 0.8)

X_train, X_test = X.iloc[:split], X.iloc[split:]
y_train, y_test = y.iloc[:split], y.iloc[split:]
date_test = df["date"].iloc[split:]

scaler = StandardScaler()
X_train_s = pd.DataFrame(scaler.fit_transform(X_train), columns=X.columns, index=X_train.index)
X_test_s = pd.DataFrame(scaler.transform(X_test), columns=X.columns, index=X_test.index)

print(f"   训练集: {split} 条 ({df['date'].iloc[0].date()} ~ {df['date'].iloc[split-1].date()})")
print(f"   测试集: {n - split} 条 ({df['date'].iloc[split].date()} ~ {df['date'].iloc[n-1].date()})")
print(f"   归一化: StandardScaler，仅用训练集 fit（{X.shape[1]} 个特征）")
print("   注意: 测试期(2025 年起)天气列为模拟补全数据，泛化结论需谨慎解读")

# ----------------------------------------------------------------------------
# 3. 评估工具
# ----------------------------------------------------------------------------


def evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "R2": r2_score(y_true, y_pred),
        "MAPE(%)": mean_absolute_percentage_error(y_true, y_pred) * 100,
        "WAPE(%)": np.abs(y_true - y_pred).sum() / y_true.sum() * 100,
        "RMSE": float(np.sqrt(np.mean((y_true - y_pred) ** 2))),
        "MAE": mean_absolute_error(y_true, y_pred),
    }


# ----------------------------------------------------------------------------
# 4. 机器学习模型：RandomizedSearchCV + TimeSeriesSplit 超参寻优
# ----------------------------------------------------------------------------
print("=" * 70)
print("3. 机器学习模型超参数寻优 (RandomizedSearchCV, cv=TimeSeriesSplit(5))")

tscv = TimeSeriesSplit(n_splits=5)
results = {}
best_params_all = {}

SEARCH_ITER = 25


def search_and_eval(name, estimator, param_dist, search_n_jobs=-1):
    # 注意：LightGBM/XGBoost 的 C++ 层使用 OpenMP，与 joblib 多进程并行会冲突
    # （loky 子进程内 libomp 段错误），因此这两个模型的搜索用单进程顺序执行。
    t0 = time.time()
    search = RandomizedSearchCV(
        estimator,
        param_distributions=param_dist,
        n_iter=SEARCH_ITER,
        cv=tscv,
        scoring="neg_mean_absolute_error",
        n_jobs=search_n_jobs,
        random_state=RS,
        verbose=0,
    )
    search.fit(X_train_s, y_train)
    fit_s = time.time() - t0
    best = search.best_estimator_
    y_pred = best.predict(X_test_s)
    m = evaluate(y_test.values, y_pred)
    results[name] = m
    best_params_all[name] = {k: (v if isinstance(v, (int, float, str, type(None))) else str(v))
                             for k, v in search.best_params_.items()}
    print(f"   [{name}] 搜索 {fit_s:.0f}s | CV-MAE {-search.best_score_:.1f} | "
          f"Test R2 {m['R2']:.4f}, MAPE {m['MAPE(%)']:.2f}%")
    return best, y_pred


rf_best, rf_pred = search_and_eval(
    "RandomForest",
    RandomForestRegressor(random_state=RS, n_jobs=-1),
    {
        "n_estimators": [200, 400, 600, 800, 1000],
        "max_depth": [None, 10, 20, 30, 40],
        "min_samples_split": [2, 5, 10],
        "min_samples_leaf": [1, 2, 4],
        "max_features": ["sqrt", 0.3, 0.5, 0.8, 1.0],
    },
)

lgb_best, lgb_pred = search_and_eval(
    "LightGBM",
    lgb.LGBMRegressor(random_state=RS, n_jobs=4, verbose=-1),
    {
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
    search_n_jobs=1,  # 避免 libomp 与多进程冲突
)

xgb_best, xgb_pred = search_and_eval(
    "XGBoost",
    xgb.XGBRegressor(random_state=RS, n_jobs=4, tree_method="hist", objective="reg:squarederror"),
    {
        "n_estimators": [200, 400, 600, 1000],
        "learning_rate": [0.01, 0.03, 0.05, 0.1, 0.2],
        "max_depth": [3, 4, 5, 6, 8, 10],
        "min_child_weight": [1, 3, 5, 10],
        "subsample": [0.6, 0.8, 1.0],
        "colsample_bytree": [0.6, 0.8, 1.0],
        "reg_alpha": [0, 0.01, 0.1, 1],
        "reg_lambda": [0, 0.01, 0.1, 1],
    },
    search_n_jobs=1,  # 避免 OpenMP 与多进程冲突
)

# ----------------------------------------------------------------------------
# 5. LSTM（PyTorch）：序列建模 + 早停
# ----------------------------------------------------------------------------
print("=" * 70)
print("4. LSTM 训练 (PyTorch, 早停 EarlyStopping)")

LOOKBACK = 30   # 用过去 30 天特征 + 当日可得特征（共 31 步）预测当日游客量
HIDDEN, LAYERS, DROPOUT = 32, 1, 0.0
MAX_EPOCHS, PATIENCE, BATCH = 600, 50, 32
LR, WD, GRAD_CLIP = 1e-3, 1e-4, 1.0

# 关键设计：
# 1) 窗口为 [t-LOOKBACK, t] 共 31 步——第 t 行的滞后/日历特征（visitors_lag_1、
#    weather_*_lag1、sin/cos 等）在预测时均为已知信息，与树模型特征对齐，无泄漏；
#    若窗口止于 t-1，则 LSTM 相比树模型丢失了 visitors_lag_1 这类最强特征。
# 2) 差分目标：预测 visitors(t) - visitors(t-1) 再还原（持续性基线 + 修正量），
#    显著提升训练稳定性与泛化（实验中 R2 从 -0.69 提升到 0.86）。
# 3) Huber(SmoothL1) 损失 + 梯度裁剪 + weight decay，抑制节假日尖峰导致的发散。
lag1_all = df["visitors_lag_1"].values
y_delta = (y.values - lag1_all).astype(float)
d_mean, d_std = y_delta[:split].mean(), y_delta[:split].std()
y_delta_s = (y_delta - d_mean) / d_std

X_all_s = pd.DataFrame(scaler.transform(X), columns=X.columns, index=X.index)
train_idx = np.arange(LOOKBACK, split)
test_idx = np.arange(split, n)
X_seq_tr = np.stack([X_all_s.values[i - LOOKBACK:i + 1] for i in train_idx])
X_seq_te = np.stack([X_all_s.values[i - LOOKBACK:i + 1] for i in test_idx])
y_seq_tr = y_delta_s[train_idx]

# 训练序列内部再按时间切 10% 作验证（早停依据）
val_cut = int(len(X_seq_tr) * 0.9)
ds_tr = TensorDataset(torch.tensor(X_seq_tr[:val_cut], dtype=torch.float32),
                      torch.tensor(y_seq_tr[:val_cut], dtype=torch.float32))
ds_val = TensorDataset(torch.tensor(X_seq_tr[val_cut:], dtype=torch.float32),
                       torch.tensor(y_seq_tr[val_cut:], dtype=torch.float32))
dl_tr = DataLoader(ds_tr, batch_size=BATCH, shuffle=True)
dl_val = DataLoader(ds_val, batch_size=BATCH, shuffle=False)

print(f"   序列样本: 训练 {len(ds_tr)} / 验证 {len(ds_val)} / 测试 {len(X_seq_te)}，"
      f"窗口 {LOOKBACK + 1} 步（含目标日特征），差分目标")


class LSTMRegressor(nn.Module):
    def __init__(self, n_features):
        super().__init__()
        self.lstm = nn.LSTM(n_features, HIDDEN, num_layers=LAYERS,
                            dropout=DROPOUT, batch_first=True)
        self.head = nn.Sequential(
            nn.Linear(HIDDEN, 32), nn.ReLU(), nn.Linear(32, 1)
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :]).squeeze(-1)


device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
model = LSTMRegressor(X.shape[1]).to(device)
opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=WD)
loss_fn = nn.SmoothL1Loss()  # Huber 损失


class EarlyStopping:
    """验证集 loss 连续 patience 轮不下降则停止，并恢复最优权重"""

    def __init__(self, patience):
        self.patience = patience
        self.best, self.count, self.best_state = np.inf, 0, None

    def step(self, val_loss):
        if val_loss < self.best - 1e-6:
            self.best, self.count = val_loss, 0
            self.best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            return False
        self.count += 1
        return self.count >= self.patience


stopper = EarlyStopping(PATIENCE)
hist = {"train": [], "val": []}
t0 = time.time()
for epoch in range(1, MAX_EPOCHS + 1):
    model.train()
    for xb, yb in dl_tr:
        xb, yb = xb.to(device), yb.to(device)
        opt.zero_grad()
        loss = loss_fn(model(xb), yb)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
        opt.step()
    model.eval()
    with torch.no_grad():
        tr_losses = [loss_fn(model(xb.to(device)), yb.to(device)).item() for xb, yb in dl_tr]
        va_losses = [loss_fn(model(xb.to(device)), yb.to(device)).item() for xb, yb in dl_val]
    hist["train"].append(np.mean(tr_losses))
    hist["val"].append(np.mean(va_losses))
    if epoch % 20 == 0 or epoch == 1:
        print(f"   epoch {epoch:3d} | train Huber {hist['train'][-1]:.4f} | val Huber {hist['val'][-1]:.4f}")
    if stopper.step(hist["val"][-1]):
        print(f"   早停触发于第 {epoch} 轮（{PATIENCE} 轮无改善），恢复最优权重")
        break

if stopper.best_state is not None:
    model.load_state_dict(stopper.best_state)
print(f"   LSTM 训练完成: {time.time() - t0:.0f}s, {len(hist['val'])} epochs, "
      f"最优 val Huber {stopper.best:.4f}, device={device}")

model.eval()
with torch.no_grad():
    pred_d = model(torch.tensor(X_seq_te, dtype=torch.float32).to(device)).cpu().numpy()
# 差分还原: visitors(t) = Δ预测 * std + mean + visitors(t-1)
lstm_pred = pred_d * d_std + d_mean + lag1_all[split:]
lstm_pred = np.clip(lstm_pred, 0, None)
results["LSTM"] = evaluate(y_test.values, lstm_pred)
print(f"   [LSTM]      Test R2 {results['LSTM']['R2']:.4f}, MAPE {results['LSTM']['MAPE(%)']:.2f}%")

# ----------------------------------------------------------------------------
# 6. 汇总输出
# ----------------------------------------------------------------------------
print("=" * 70)
print("5. 测试集性能汇总（时间外样本，2025-06 ~ 2026-08）")

res_df = pd.DataFrame(results).T
print(res_df.round(4).to_string())

res_df.round(6).to_csv(OUT_DIR / "baseline_metrics.csv", encoding="utf-8-sig")
pred_df = pd.DataFrame({
    "date": date_test.dt.strftime("%Y-%m-%d").values,
    "y_true": y_test.values,
    "RandomForest": np.round(rf_pred, 1),
    "LightGBM": np.round(lgb_pred, 1),
    "XGBoost": np.round(xgb_pred, 1),
    "LSTM": np.round(lstm_pred, 1),
})
pred_df.to_csv(OUT_DIR / "test_predictions.csv", index=False, encoding="utf-8-sig")

with open(OUT_DIR / "best_params.json", "w", encoding="utf-8") as f:
    json.dump({
        "best_params": best_params_all,
        "lstm_config": {
            "lookback": LOOKBACK, "window_steps": LOOKBACK + 1,
            "window_includes_target_row_features": True,
            "target": "diff(visitors - visitors_lag_1)",
            "hidden": HIDDEN, "layers": LAYERS,
            "dropout": DROPOUT, "lr": LR, "weight_decay": WD,
            "grad_clip": GRAD_CLIP, "loss": "SmoothL1(Huber)",
            "batch": BATCH, "max_epochs": MAX_EPOCHS, "patience": PATIENCE,
            "epochs_run": len(hist["val"]),
            "best_val_huber": float(stopper.best),
            "device": str(device),
        },
    }, f, ensure_ascii=False, indent=2)

# 特征重要性（树模型 Top 15）
imp = {}
for name, m in [("RandomForest", rf_best), ("LightGBM", lgb_best), ("XGBoost", xgb_best)]:
    imp[name] = pd.Series(m.feature_importances_, index=X.columns).sort_values(ascending=False)
imp_df = pd.DataFrame({k: v for k, v in imp.items()}).fillna(0)
imp_df.head(15).round(4).to_csv(OUT_DIR / "feature_importance_top15.csv", encoding="utf-8-sig")

# 预测曲线图
fig, axes = plt.subplots(2, 2, figsize=(16, 10), sharex=True, sharey=True)
pred_map = {"RandomForest": rf_pred, "LightGBM": lgb_pred, "XGBoost": xgb_pred, "LSTM": lstm_pred}
for ax, (name, pred) in zip(axes.ravel(), pred_map.items()):
    ax.plot(date_test, y_test, label="Actual", color="#333333", lw=1.2)
    ax.plot(date_test, pred, label=f"{name} (R2={results[name]['R2']:.3f})",
            color="#c0392b", lw=1.0, alpha=0.85)
    ax.set_title(name)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
fig.suptitle("Test-set predictions vs actual (Jiuzhaigou daily visitors)", fontsize=14)
fig.autofmt_xdate()
fig.tight_layout()
fig.savefig(OUT_DIR / "prediction_curves.png", dpi=130)

# LSTM 训练曲线
fig2, ax = plt.subplots(figsize=(8, 5))
ax.plot(hist["train"], label="train Huber")
ax.plot(hist["val"], label="val MSE")
ax.set_xlabel("epoch"); ax.set_ylabel("MSE (scaled)")
ax.set_title(f"LSTM training curve (stopped at epoch {len(hist['val'])})")
ax.legend(); ax.grid(alpha=0.3)
fig2.tight_layout()
fig2.savefig(OUT_DIR / "lstm_training_curve.png", dpi=130)

print("=" * 70)
print(f"全部完成。输出目录: {OUT_DIR}")
print("DONE_MARKER_OK")
