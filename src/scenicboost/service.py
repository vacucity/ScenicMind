from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.scenicboost.explain import global_shap, local_shap
from src.scenicboost.model import ScenicBoostModel


class PredictionService:
    """Small synchronous interface suitable for a batch job or future API wrapper."""

    def __init__(self, model: ScenicBoostModel):
        self.model = model

    @classmethod
    def from_directory(cls, directory: str | Path) -> "PredictionService":
        return cls(ScenicBoostModel.load(directory))

    def predict(self, features: pd.DataFrame) -> pd.DataFrame:
        return self.model.predict(features)


class ExplanationService:
    """Separate SHAP interface so explanation latency cannot block prediction."""

    def __init__(self, model: ScenicBoostModel):
        self.model = model

    @classmethod
    def from_directory(cls, directory: str | Path) -> "ExplanationService":
        return cls(ScenicBoostModel.load(directory))

    def explain_rows(self, features: pd.DataFrame, *, top_k: int | None = 10) -> pd.DataFrame:
        return local_shap(self.model, features, top_k=top_k)

    def global_importance(self, features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        return global_shap(self.model, features)

