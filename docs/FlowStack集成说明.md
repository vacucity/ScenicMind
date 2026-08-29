# FlowStack 代码与数据接口说明

## 交付边界

本目录只提供算法代码和稳定的数据输出格式，不包含数据看板、Web API、Agent 或经营建议生成逻辑。与 ScenicBoost 一样，预测与解释完全分离：

- `PredictionService`：只计算客流预测，适合实时或批量预测链路（推看板）。
- `ImportanceService`：单独输出共识特征重要性，适合离线任务，供下游 Agent 生成经营建议，不阻塞预测。
- `export.py`：把结果整理为通用 CSV/JSONL，供看板或 Agent 读取。

相对 ScenicBoost 的模型层改进：冗余感知特征选择、差分目标、四路基学习器 OOF 堆叠、Huber/L1 稳健损失、节假日样本加权。历史评估协议与五项指标对比见 `appendix/baseline/flowstack_vs_baseline.md`。

## 目录

```text
scenicmind/flowstack/
├── config.py       # 配置对象（冗余阈值/堆叠折数/样本权重/基学习器参数）
├── redundancy.py   # 冗余感知特征选择（Spearman 聚类 + 簇内互信息代表）
├── model.py        # 差分目标 + 四路基学习器 + OOF 堆叠 + 场景校正
├── metrics.py      # R2/MAPE/WAPE/RMSE/MAE（与 baseline 同口径）
├── service.py      # 预测、重要性两个独立调用接口
├── export.py       # 看板/Agent 中立数据契约
└── cli.py          # 命令行入口
```

## 依赖

项目 `.deps` 目录已包含全部依赖（pandas / numpy / scikit-learn / lightgbm / xgboost / catboost / joblib）。运行时设置 `PYTHONPATH=.deps;.`。

## 训练

```powershell
python -m scenicmind.flowstack.cli train `
  --data path/to/training_data.xlsx `
  --artifact-dir artifacts/flowstack/current
```

训练产物：

```text
artifacts/flowstack/current/
├── model/
│   ├── model.joblib      # 完整模型（含冗余选择器/基学习器/元学习器/校正器）
│   └── metadata.json     # 版本、特征清单、融合权重、训练区间
├── feature_importance.csv
├── agent_importance.json
└── oof_predictions.csv
```

带超参寻优的完整复现（baseline 同协议 RandomizedSearchCV）请运行根目录 `flowstack_eval.py`，它会自动把寻优参数注入配置再训练。

## 只生成预测（推看板）

输入文件必须包含模型 `metadata.json` 中列出的原始特征列（去冗余前的全量列，模型内部自动完成选择与编码），可含也可不含目标 `visitors`。

```powershell
python -m scenicmind.flowstack.cli predict `
  --model-dir artifacts/flowstack/current/model `
  --features future_features.csv `
  --output outputs/flowstack/predictions.csv
```

稳定输出字段（看板热路径契约）：

| 字段 | 含义 |
|---|---|
| `date` | 预测日期 |
| `predicted_visitors` | 预测客流人数，整数，非负且不超过已知承载量 |
| `model_version` | 模型版本，用于追溯 |

Python 内置方式：

```python
import pandas as pd
from scenicmind.flowstack.service import PredictionService

service = PredictionService.from_directory("artifacts/flowstack/current/model")
result = service.predict(pd.read_csv("future_features.csv"))
# result[["date", "predicted_visitors", "model_version"]] -> 写入 forecast_fact 表
```

需要误差归因时可用 `service.predict_components()`，额外返回四路基学习器各自预测、场景修正量、约束修正量。

## 单独生成特征重要性（接 Agent）

```powershell
python -m scenicmind.flowstack.cli importance `
  --model-dir artifacts/flowstack/current/model `
  --output-dir outputs/flowstack/importance `
  --top-k 20
```

输出：

- `feature_importance_global.csv`：字段级共识重要性（含业务分组、冗余簇大小、各基学习器分项）。
- `feature_importance_groups.csv`：历史客流/日历节假日/天气/网络关注度/景区运营/交通可达性分组重要性。
- `redundancy_clusters.csv`：冗余簇映射——每个代表特征合并了哪些同维度特征。
- `agent_importance.json`：Agent 直接可读的 JSON（字段级 + 分组级 + 簇映射 + 元学习器融合权重）。

共识重要性 = Σ 元学习器融合权重 × 各基学习器归一化 gain 重要性。`cluster_size > 1` 表示该特征是冗余簇代表，其重要性应理解为"这一整个同维度特征族"的贡献。不要把重要性描述为因果影响。

## 推荐的后续接入方式

1. 每日特征任务生成预测日期的 forecast-safe 特征行，字段须与模型 `metadata.json` 中记录的原始特征一致。
2. 调用 `PredictionService`，立即持久化预测结果和模型版本。
3. 使用独立离线任务调用 `ImportanceService`，写入解释结果。
4. 真实客流到达后按 `date + model_version` 关联，而不是覆盖历史预测。
5. 看板读取预测事实表；Agent 读取 `agent_importance.json` 或 `export.py` 生成的日度 JSONL。

生产数据库建议保留两张事实表：

```text
forecast_fact(date, predicted_visitors, model_version, generated_at)
importance_fact(feature, feature_group, importance, rank, cluster_size, model_version)
```

真实客流来自独立的 `actual_visitors_fact`，三者通过日期与模型版本组合。
