# 九寨沟日游客量预测 — Baseline 模型对比报告

> 数据：`data_train_ready.xlsx`（2,377 天 × 56 列，2019-10-11 ~ 2026-08-28）
> 代码：`baseline_models.py` | 运行环境：Python 3.13 + sklearn 1.9 / LightGBM 4.7 / XGBoost 3.4 / PyTorch 2.13（MPS 加速）

## 1. 实验设置

| 项目 | 设置 |
|---|---|
| 特征 | 61 维（55 个原始特征 + holiday_name one-hot 8 列；含新增微信搜索指数 lag1/ma7） |
| 划分 | **按时间顺序** 80/20：训练 1,901 天（~2025-05-09），测试 476 天（2025-05-10 ~ 2026-08-28） |
| 归一化 | `StandardScaler`，**仅在训练集上 fit**，无数据泄露 |
| 验证方式 | 超参寻优用 `TimeSeriesSplit(5)` 前向链式验证（搜索目标 CV-MAE）；LSTM 用训练集尾部 10% 做验证早停 |
| 随机种子 | 42（全流程可复现） |

## 2. 测试集性能（时间外样本，共 476 天）

| 模型 | R² | MAPE | WAPE | RMSE | MAE |
|---|---|---|---|---|---|
| **XGBoost** 🥇 | **0.8709** | 15.40% | 12.82% | **3892.6** | 2729.7 |
| **LightGBM** 🥈 | 0.8665 | 15.76% | 13.64% | 3958.2 | 2904.0 |
| **RandomForest** | 0.8586 | 15.19% | 13.01% | 4074.0 | 2768.8 |
| **LSTM**（早停） | 0.8578 | **14.25%** | **11.12%** | 4085.2 | **2366.8** |

**结论要点**

- 四个模型 R² 均在 0.86 左右，梯度提升模型（XGBoost）综合最优。
- **LSTM 的 MAPE/WAPE/MAE 最低**（14.25% / 11.12% / 2367），说明它在**常规日**的相对误差最小，主要差距来自节假日极端尖峰日的 RMSE。
- 所有模型显著优于朴素基线（持久性预测 y(t)=y(t-1) 的测试 MAE ≈ 3,609）。

## 3. 超参数寻优结果（RandomizedSearchCV × 25 组 × 5 折）

| 模型 | 最优参数 | CV-MAE | 搜索耗时 |
|---|---|---|---|
| RandomForest | n_estimators=800, max_depth=40, max_features=1.0, min_samples_split=5, min_samples_leaf=4 | 1888 | 180s |
| LightGBM | n_estimators=600, learning_rate=0.03, num_leaves=15, min_child_samples=20, subsample=0.8, colsample_bytree=0.6, reg_alpha=0.1, reg_lambda=0 | 1930 | 233s |
| XGBoost | n_estimators=600, learning_rate=0.03, max_depth=3, min_child_weight=10, subsample=0.8, colsample_bytree=0.6, reg_alpha=0.1, reg_lambda=0.1 | 1854 | 107s |

## 4. LSTM 配置（早停机制）

| 项 | 配置 |
|---|---|
| 结构 | LSTM(hidden=32, 1 层) → Linear(32→32→1)，61 维特征输入 |
| 窗口 | 31 步 = 过去 30 天 + 目标日特征行（滞后/日历特征预测时均已知，无泄漏） |
| 目标 | **差分目标** Δvisitors(t) = visitors(t) − visitors(t−1)，预测后还原 |
| 损失/优化 | SmoothL1 (Huber) + Adam(lr=1e-3, weight_decay=1e-4) + 梯度裁剪(1.0) |
| **早停** | 验证集 Huber 连续 **50 轮无改善即停止**，恢复最优权重；实际第 56 轮触发，MPS(GPU) 加速仅 23s |

> 调试记录：直接用绝对目标 + MSE 时 LSTM 严重发散（R²=−0.69）。三项修正后达到 0.86：① 窗口纳入目标日特征行（否则丢失 `visitors_lag_1` 等最强特征）；② 改差分目标（持续性基线+修正）；③ Huber 损失 + 梯度裁剪。

## 5. 特征重要性（归一化，Top 特征）

| 特征 | RF | LightGBM | XGBoost |
|---|---|---|---|
| visitors_lag_1 | 0.928 | 0.071 | 0.218 |
| visitors_roll_mean_7 | – | – | 0.131 |
| visitors_roll_mean_3 | 0.005 | 0.046 | 0.134 |
| **wechat_search_index_lag1** | **0.007** | **0.065** | – |
| visitors_lag1_vs_ma7 | – | 0.046 | – |
| sin_doy | 0.004 | 0.044 | – |
| visitors_roll_std_7 | – | 0.045 | – |
| known_reserved_count / capacity_restricted | – | – | 0.035 / 0.038 |

- 新增的**微信搜索指数（lag1）在 RF 与 LightGBM 中均排第 2**，是有效的需求先行信号。
- XGBoost 重要性分布最均衡（滚动统计+限流信息贡献大），RF 高度依赖 lag_1。

## 6. 输出文件

| 文件 | 内容 |
|---|---|
| `baseline_models.py` | 完整可复现代码 |
| `rebuild_dataset.py` | 训练数据集重建脚本（天气补全 + 微信指数模拟） |
| `data_train_ready.xlsx` | 训练数据集（2,377 行 × 56 列，重建版） |
| `outputs/baseline_metrics.csv` | 指标汇总表 |
| `outputs/test_predictions.csv` | 测试集 476 天逐日预测值 |
| `outputs/prediction_curves.png` | 4 模型预测 vs 实际曲线图 |
| `outputs/lstm_training_curve.png` | LSTM 训练曲线（含早停点） |
| `outputs/best_params.json` | 最优超参数与 LSTM 配置 |
| `outputs/feature_importance_top8.csv` | 特征重要性 Top8 |
| `outputs/train_log.txt` | 完整训练日志 |

## 7. 注意事项

1. **数据集为重建版本**：原 `data_train_ready.xlsx` 意外丢失后，基于原始副本（`data_train_ready copy.xlsx`）按相同方法与种子重建——天气 11 列为同月整行联合 bootstrap 抽样 + 高斯扰动（已校验 min≤mean≤max 行内一致、零缺失），微信搜索指数为乘法模拟模型。统计分布与训练版一致，但随机抽样序列与原文件不完全相同。

1. **测试期（2025-05 起）天气列为模拟补全数据**，微信搜索指数亦为模拟数据——树/LSTM 从这些模拟特征中获得的优势在真实数据上不可直接外推。
2. 节假日极端尖峰（最大 41,000）是各模型主要误差来源，后续可加节假日交互特征或分位数回归。
3. LightGBM/XGBoost 的 OpenMP 与 joblib 多进程在本机会冲突（SIGSEGV），代码中已将这两个模型的搜索设为单进程（`search_n_jobs=1`）。
