# 旧基线实验附录

本目录保存 FlowStack 建模前的基线实验，仅用于结果追溯和模型对照，不参与当前系统运行。

- `baseline_models.py`：RandomForest、LightGBM、XGBoost 与 LSTM 的旧评估脚本。
- `baseline_results.md`：旧实验设置、指标和结论记录。
- `flowstack_vs_baseline.md`：FlowStack 与旧基线的历史对比结果。

注意：脚本保留了原实验环境中的绝对数据路径，不能在当前 Windows 工作区直接运行。当前生产候选算法位于 `src/flowstack/`，模型产物位于 `artifacts/flowstack/current/`。
