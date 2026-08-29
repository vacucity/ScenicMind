from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class UserView(BaseModel):
    id: int
    username: str
    email: str


class AuthResponse(BaseModel):
    access_token: str = Field(alias="accessToken")
    token_type: str = Field(default="bearer", alias="tokenType")
    user: UserView

    model_config = {"populate_by_name": True}


class AnalysisEnvelope(BaseModel):
    analysis_id: str = Field(alias="analysisId")
    status: Literal["processing", "completed", "failed"]
    created_at: str = Field(alias="createdAt")
    error: str | None = None
    result: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}

