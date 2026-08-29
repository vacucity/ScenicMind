"""预测与解释两个独立服务接口（与 ScenicBoost 的服务边界一致）。

- PredictionService：只算客流预测，供每日批量/实时链路调用，结果推送看板。
- ImportanceService：单独输出特征重要性，供下游 Agent 生成经营建议，
  解释延迟永远不会阻塞预测链路。
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scenicmind.flowstack.model import FlowStackModel


class PredictionService:
    """适合批处理任务或未来 API 包装的同步预测接口。"""

    def __init__(self, model: FlowStackModel):
        self.model = model

    @classmethod
    def from_directory(cls, directory: str | Path) -> "PredictionService":
        return cls(FlowStackModel.load(directory))

    def predict(self, features: pd.DataFrame) -> pd.DataFrame:
        """稳定输出契约：date / predicted_visitors / model_version。"""
        return self.model.predict(features)

    def predict_components(self, features: pd.DataFrame) -> pd.DataFrame:
        """完整分解：堆叠预测、各基学习器预测、场景修正、约束修正。"""
        return self.model.predict_components(features)


class ImportanceService:
    """特征重要性独立接口，面向下游经营建议 Agent。"""

    def __init__(self, model: FlowStackModel):
        self.model = model

    @classmethod
    def from_directory(cls, directory: str | Path) -> "ImportanceService":
        return cls(FlowStackModel.load(directory))

    def global_importance(self) -> pd.DataFrame:
        return self.model.feature_importance()

    def group_importance(self) -> pd.DataFrame:
        return self.model.group_importance()

    def redundancy_report(self) -> pd.DataFrame:
        return self.model.reducer.report()

    def export_agent_payload(self, output: str | Path, top_k: int | None = None) -> Path:
        """导出 Agent 直接可读的 JSON：字段级/分组级重要性 + 冗余簇映射。"""
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.model.importance_payload(top_k=top_k),
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return destination
