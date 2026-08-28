import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .prediction import PredictionResult, get_latest_prediction

app = FastAPI(
    title="PineFlow API",
    version="0.1.0",
    description="人流量预测系统的后端接口骨架。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/api/v1/predictions/latest",
    response_model=PredictionResult,
    response_model_by_alias=True,
    tags=["predictions"],
)
def latest_prediction() -> PredictionResult:
    try:
        return get_latest_prediction()
    except NotImplementedError as error:
        raise HTTPException(status_code=501, detail=str(error)) from error
