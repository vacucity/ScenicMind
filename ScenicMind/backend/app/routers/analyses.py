from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from ..database import (
    analyses_by_user,
    analysis_by_id,
    complete_analysis_with_indicators,
    create_analysis,
    fail_analysis,
    latest_analysis,
)
from ..dependencies import current_user
from ..schemas import AnalysisEnvelope
from ..settings import UPLOAD_DIR
from ..services.dataset import DatasetError, normalize_dataset, read_uploaded_dataset
from ..services.forecast import analyze_visitors
from ..services.indicators import compute_indicators


router = APIRouter(prefix="/api/v1/analyses", tags=["analyses"])
ALLOWED_SUFFIXES = {".csv", ".xlsx", ".xls", ".json", ".parquet"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _safe_filename(name: str) -> str:
    clean = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", Path(name).name, flags=re.UNICODE)
    return clean[:150] or "dataset.csv"


def _envelope(row) -> AnalysisEnvelope:
    result = json.loads(row["result_json"]) if row["result_json"] else None
    return AnalysisEnvelope(
        analysisId=row["id"], status=row["status"], createdAt=row["created_at"],
        error=row["error"], result=result,
    )


@router.post("", response_model=AnalysisEnvelope, response_model_by_alias=True, status_code=201)
async def create_analysis_from_upload(file: UploadFile = File(...), user=Depends(current_user)) -> AnalysisEnvelope:
    filename = _safe_filename(file.filename or "dataset.csv")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="文件类型不受支持")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件超过 50 MB")
    if not content:
        raise HTTPException(status_code=422, detail="上传文件为空")

    analysis_id = uuid.uuid4().hex
    user_dir = UPLOAD_DIR / str(user["id"])
    user_dir.mkdir(parents=True, exist_ok=True)
    stored_path = user_dir / f"{analysis_id}{suffix}"
    stored_path.write_bytes(content)
    create_analysis(analysis_id, user["id"], filename, str(stored_path))
    try:
        raw = read_uploaded_dataset(stored_path)
        normalized, warnings = normalize_dataset(raw)
        result, importance = analyze_visitors(normalized, filename, warnings)
        indicators = compute_indicators(normalized)
        complete_analysis_with_indicators(analysis_id, result, importance, indicators)
    except DatasetError as error:
        fail_analysis(analysis_id, str(error))
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        fail_analysis(analysis_id, str(error))
        raise HTTPException(status_code=500, detail=f"算法分析失败：{error}") from error

    row = analysis_by_id(analysis_id, user["id"])
    if row is None:
        raise HTTPException(status_code=500, detail="分析结果保存失败")
    return _envelope(row)


@router.get("/latest", response_model=AnalysisEnvelope, response_model_by_alias=True)
def get_latest_analysis(user=Depends(current_user)) -> AnalysisEnvelope:
    row = latest_analysis(user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="尚未上传分析数据")
    return _envelope(row)


@router.get("")
def list_analyses(user=Depends(current_user)) -> list[dict]:
    rows = analyses_by_user(user["id"])
    return [
        {
            "analysisId": row["id"],
            "fileName": row["file_name"],
            "status": row["status"],
            "error": row["error"],
            "createdAt": row["created_at"],
            "completedAt": row["completed_at"],
        }
        for row in rows
    ]


@router.get("/{analysis_id}", response_model=AnalysisEnvelope, response_model_by_alias=True)
def get_analysis(analysis_id: str, user=Depends(current_user)) -> AnalysisEnvelope:
    row = analysis_by_id(analysis_id, user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="分析任务不存在")
    return _envelope(row)


@router.get("/{analysis_id}/importance")
def get_analysis_importance(analysis_id: str, user=Depends(current_user)) -> dict:
    row = analysis_by_id(analysis_id, user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="分析任务不存在")
    if row["status"] != "completed" or not row["importance_json"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="特征贡献尚未生成")
    return json.loads(row["importance_json"])


@router.get("/{analysis_id}/indicators")
def get_analysis_indicators(analysis_id: str, user=Depends(current_user)) -> dict:
    row = analysis_by_id(analysis_id, user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="分析任务不存在")
    if row["status"] != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="分析尚未完成")
    if row["indicators_json"]:
        return json.loads(row["indicators_json"])
    # 历史数据无 indicators_json 时按需重新计算
    try:
        raw = read_uploaded_dataset(Path(row["stored_path"]))
        normalized, _ = normalize_dataset(raw)
        indicators = compute_indicators(normalized)
        return indicators
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"指标计算失败：{error}") from error

