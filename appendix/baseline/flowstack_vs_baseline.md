# FlowStack vs Baseline —— 九寨沟日游客量预测模型对比报告

> 数据：`data.xlsx`（2,377 天 × 56 列，2019-10-11 ~ 2026-08-28）
> 代码：`flowstack_eval.py` + `scenicmind/flowstack/` | 环境：Python 3.12 + sklearn 1.9 / LightGBM 4.7 / XGBoost 3.4 / CatBoost 1.2
> 评估协议与 `baseline_models.py` **完全一致**：时间序 80/20（训练 1,901 / 测试 476）、TimeSeriesSplit(5) 前向链式验证、RandomizedSearchCV×25 组按 CV-MAE 寻优、随机种子 42、同一套五项指标实现。

## 1. 测试集性能对比（时间外样本，476 天，2025-05-10 ~ 2026-08-28）

| 模型 | R² | MAPE | WAPE | RMSE | MAE |
|---|---|---|---|---|---|
| **FlowStack** 🥇 | **0.8858** | **13.26%** | **10.66%** | **3661.2** | **2270.1** |
| FlowStack（无场景校正） | 0.8831 | 13.60% | 11.20% | 3704.5 | 2384.6 |
| XGBoost（最强基线） | 0.8709 | 15.40% | 12.82% | 3892.6 | 2729.7 |
| LightGBM | 0.8665 | 15.76% | 13.64% | 3958.2 | 2904.0 |
| RandomForest | 0.8586 | 15.19% | 13.01% | 4074.0 | 2768.8 |
| LSTM | 0.8578 | 14.25% | 11.12% | 4085.2 | 2366.8 |

## 2. 逐项 vs 各指标最强基线（全面超越判定）

| 指标 | FlowStack | 最强基线值（模型） | 差值 | 相对提升 | 判定 |
|---|---|---|---|---|---|
| R² ↑ | 0.8858 | 0.8709（XGBoost） | +0.0149 | +1.71% | ✅ 超越 |
| MAPE ↓ | 13.26% | 14.25%（LSTM） | −0.99pp | −6.97% | ✅ 超越 |
| WAPE ↓ | 10.66% | 11.12%（LSTM） | −0.46pp | −4.10% | ✅ 超越 |
| RMSE ↓ | 3661.2 | 3892.6（XGBoost） | −231.4 | −5.94% | ✅ 超越 |
| MAE ↓ | 2270.1 | 2366.8（LSTM） | −96.7 | −4.09% | ✅ 超越 |

**结论：FlowStack 在五项指标上全面超越全部四个基线模型**，且不是"打平最强单项"——它同时击败了 XGBoost 的 R²/RMSE 和 LSTM 的 MAPE/WAPE/MAE。注意基线的最优值分散在两个模型上（XGBoost 擅长绝对误差/方差，LSTM 擅长相对误差），此前没有任何单一模型能同时占住两条线。

## 3. 核心改进点（相对 ScenicBoost / 基线）

| # | 改进 | 解决的问题 | 对应指标收益 |
|---|---|---|---|
| 1 | **差分目标建模**：预测 Δvisitors = visitors − visitors_lag_1 的标准化修正量，再还原 | ScenicBoost/树基线用绝对目标，节假日尖峰下梯度被极端值主导；差分把"持续性基线+修正"结构显式内置（baseline LSTM 的关键经验移植到树模型） | MAE / WAPE / MAPE |
| 2 | **四路多样化基学习器 + OOF 堆叠**：LGB-Huber / XGB-Huber / LGB-L1 / CatBoost-Huber，TimeSeriesSplit 前向链式 OOF → 正约束 Ridge 元学习器融合（本次融合权重 CatBoost 0.71 / XGBoost 0.29） | 单模型方差大、各有所长无法兼得；堆叠让"擅长绝对误差的"和"擅长相对误差的"模型互补 | 全部五项 |
| 3 | **稳健损失（Huber/L1）替代 L2** | 节假日 41,000 人次尖峰在 L2 下产生过大梯度，拖累常规日拟合 | MAPE / WAPE / MAE |
| 4 | **冗余感知特征选择**：Spearman 相关聚类（\|ρ\|≥0.9）+ 簇内互信息代表保留，61 维 → 46 维 | 同维度重复特征（如 lag_1/roll_mean_3/roll_mean_7 五胞胎、温度四胞胎）导致的多重共线性与重要性稀释 | 可解释性 + 泛化 |
| 5 | **节假日样本加权 + 场景残差收缩校正**（沿用 ScenicBoost 思想，作用于 OOF 残差） | 法定节假日极端尖峰是 RMSE 主误差源 | RMSE（校正贡献约 −43） |
| 6 | **承载量约束后处理**：预测值截断到 [0, daily_capacity] | 物理不可达的预测（超承载/负值） | 工程可信度 |

## 4. 冗余处理明细（61 → 46 维）

代表性冗余簇（完整清单见 `outputs/flowstack/importance/redundancy_clusters.csv`）：

| 簇大小 | 保留代表 | 被合并的同维度特征 |
|---|---|---|
| 5 | visitors_lag_1 | visitors_roll_mean_3 / roll_min_7 / roll_max_7 / roll_mean_7 |
| 4 | weather_temp_mean_ma7 | weather_temp_mean_ma3 / temp_min_lag1 / temp_mean_lag1 |
| 4 | holiday_length | holiday_非节假日 / is_official_holiday / holiday_day_index |
| 2 | visitors_lag_7 | visitors_roll_mean_28 |
| 2 | daily_capacity | known_reserved_count |
| 2 | days_since_hsr_open | huanglong_jiuzhai_hsr_open |

选择仅在训练集上 fit（互信息 + 相关矩阵均不含测试数据），无泄漏。

## 5. 特征重要性（共识重要性 Top10，供 Agent 消费）

共识重要性 = Σ 元学习器融合权重 × 各基学习器归一化 gain 重要性；`cluster_size` 表明该代表特征背后合并了多少个同维度冗余特征。

| 排名 | 特征 | 共识重要性 | 业务分组 | 簇大小 |
|---|---|---|---|---|
| 1 | visitors_lag_1 | 0.094 | 历史客流 | 5 |
| 2 | visitors_lag1_vs_ma7 | 0.086 | 历史客流 | 1 |
| 3 | holiday_length | 0.072 | 日历节假日 | 4 |
| 4 | visitors_trend_strength | 0.056 | 历史客流 | 1 |
| 5 | visitors_roll_std_7 | 0.049 | 历史客流 | 1 |
| 6 | visitors_lag_365 | 0.047 | 历史客流 | 1 |
| 7 | wechat_search_index_ma7 | 0.042 | 网络关注度 | 1 |
| 8 | days_to_next_holiday | 0.033 | 日历节假日 | 1 |
| 9 | sin_doy | 0.032 | 日历节假日 | 1 |
| 10 | visitors_roll_std_14 | 0.032 | 历史客流 | 1 |

分组占比：历史客流 42.9% / 日历节假日 25.8% / 天气 11.9% / 网络关注度 10.6% / 景区运营 8.0% / 交通可达性 0.9%。

## 6. 输出文件

| 文件 | 内容 |
|---|---|
| `scenicmind/flowstack/` | 模型包（config / redundancy / model / metrics / service / export / cli） |
| `flowstack_eval.py` | 可复现评估脚本（baseline 同协议） |
| `artifacts/flowstack/current/model/` | 模型产物（model.joblib + metadata.json） |
| `outputs/flowstack_metrics.csv` | 全模型指标汇总 |
| `outputs/flowstack_vs_baseline.csv` | 逐项对比与超越判定 |
| `outputs/flowstack_test_predictions.csv` | 476 天逐日预测（含各基学习器分解） |
| `outputs/flowstack/importance/feature_importance_global.csv` | 字段级共识重要性 |
| `outputs/flowstack/importance/feature_importance_groups.csv` | 业务分组重要性 |
| `outputs/flowstack/importance/redundancy_clusters.csv` | 冗余簇映射（代表 ↔ 被合并特征） |
| `outputs/flowstack/importance/agent_importance.json` | Agent 消费用 JSON（字段+分组+簇+融合权重） |
| `docs/FlowStack集成说明.md` | 集成调用说明（看板 / Agent 接口） |

## 7. 注意事项

1. 测试期天气列与微信搜索指数为模拟补全数据（继承自 baseline 数据集），树模型从中获得的收益在真实数据上需重新验证。
2. 元学习器本次将两路 LightGBM 权重压为 0（CatBoost 0.71 + XGBoost 0.29 已足够），属正常现象——正约束 Ridge 自动做了模型选择；四路结构保留了对未来数据分布漂移的冗余。
3. 场景残差校正仅在"同场景历史样本 ≥ 8"时生效且有收缩与上限（±6,000），不会对未见场景产生激进外推。
4. 与 baseline 的协议等价说明：baseline 对树模型也施加 StandardScaler——线性缩放不改变树的分裂结构，对树预测结果无影响，FlowStack 因此省略该步，结论可比性不受影响。
