from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ModuleOutput(BaseModel):
    generated_at: datetime = Field(alias="generatedAt")
    data: dict[str, Any]
    text: str | None = None

    model_config = {"populate_by_name": True}
