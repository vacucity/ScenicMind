from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PredictionResult(BaseModel):
    """Stable envelope shared with the frontend; keep algorithm data inside `data`."""

    generated_at: datetime = Field(alias="generatedAt")
    data: dict[str, Any]
    text: str | None = None

    model_config = {"populate_by_name": True}


def get_latest_prediction() -> PredictionResult:
    """Replace this function body with the real prediction algorithm call."""

    raise NotImplementedError("Prediction algorithm is not connected")
