"""FlowStack —— 九寨沟日度客流堆叠集成预测模型。

相对 ScenicBoost 的核心改进：
1. 冗余感知特征选择：Spearman 相关性聚类 + 簇内互信息代表特征保留，
   内置化解同维度重复/高相关特征导致的多重共线性。
2. 差分目标建模：预测 visitors - visitors_lag_1 的标准化修正量，
   将"持续性基线 + 修正"结构显式内置，显著提升 MAE/WAPE/MAPE。
3. 多损失多样化基学习器 + OOF 堆叠：LightGBM(Huber) / XGBoost(Huber) /
   LightGBM(L1) / CatBoost(Huber) 四路并行，TimeSeriesSplit 前向链式
   产生 OOF 预测，正约束 Ridge 元学习器融合，降低单模型方差。
4. 节假日样本加权 + 场景残差校正 + 承载量约束，专攻节假日尖峰（RMSE 主误差源）。
5. 共识特征重要性：按元学习器融合权重加权的归一化 gain 重要性，
   附特征分组与冗余簇归属，直接供下游 Agent 消费。
"""

from scenicmind.flowstack.config import FlowStackConfig
from scenicmind.flowstack.model import FlowStackModel

__all__ = ["FlowStackConfig", "FlowStackModel"]
