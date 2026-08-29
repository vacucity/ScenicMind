"""Agent 工具层 —— 三个确定性 Tool，数据来自 SQLite 已存 JSON，零重算。"""

from __future__ import annotations

import json
from typing import Any

from ..database import analysis_by_id


def _load_json_column(analysis_id: str, user_id: int, column: str) -> Any:
    row = analysis_by_id(analysis_id, user_id)
    if row is None:
        raise ValueError(f"分析任务不存在：{analysis_id}")
    if row["status"] != "completed":
        raise ValueError("分析尚未完成，无法生成报告")
    raw = row[column]
    return json.loads(raw) if raw else None


def tool_forecast(analysis_id: str, user_id: int) -> dict[str, Any]:
    """预测客流量：未来点位 + 周期摘要 + 模型指标。"""
    result = _load_json_column(analysis_id, user_id, "result_json")
    if not result:
        raise ValueError("预测结果为空")
    return {
        "latestActual": result["latestActual"],
        "nextForecast": result["forecastPoints"][0] if result["forecastPoints"] else None,
        "forecastPoints": [
            {"date": p["date"], "predictedVisitors": p["predictedVisitors"]}
            for p in result["forecastPoints"][:14]
        ],
        "horizons": result.get("horizons", {}),
        "metrics": result.get("metrics", {}),
        "model": result.get("model", {}),
        "source": {
            "fileName": result["source"]["fileName"],
            "rowCount": result["source"]["rowCount"],
            "endDate": result["source"]["endDate"],
        },
    }


def tool_indicators(analysis_id: str, user_id: int) -> dict[str, Any]:
    """指标蓝图：8 大模块经营指标。"""
    indicators = _load_json_column(analysis_id, user_id, "indicators_json")
    if indicators:
        return indicators
    # 历史数据无 indicators_json 时按需补算
    from ..services.indicators import compute_indicators
    from ..services.dataset import normalize_dataset, read_uploaded_dataset
    from pathlib import Path
    row = analysis_by_id(analysis_id, user_id)
    raw = read_uploaded_dataset(Path(row["stored_path"]))
    normalized, _ = normalize_dataset(raw)
    return compute_indicators(normalized)


def tool_importance(analysis_id: str, user_id: int) -> dict[str, Any]:
    """特征贡献度：业务主题占比。"""
    importance = _load_json_column(analysis_id, user_id, "importance_json")
    if not importance:
        return {"semantic_groups": []}
    return {
        "semantic_groups": importance.get("semantic_groups", []),
        "top_features": [
            {"feature": item["feature"], "importance": item["importance"]}
            for item in (importance.get("feature_importance") or [])[:10]
        ],
    }


def collect_all(analysis_id: str, user_id: int) -> dict[str, Any]:
    """DataCollector 主入口：一次性采集三维度数据包。"""
    gaps: list[str] = []
    forecast: Any
    indicators: Any
    importance: Any
    try:
        forecast = tool_forecast(analysis_id, user_id)
    except Exception as error:
        forecast = None
        gaps.append(f"预测数据缺失：{error}")
    try:
        indicators = tool_indicators(analysis_id, user_id)
    except Exception as error:
        indicators = None
        gaps.append(f"指标数据缺失：{error}")
    try:
        importance = tool_importance(analysis_id, user_id)
    except Exception as error:
        importance = None
        gaps.append(f"贡献度数据缺失：{error}")
    return {"forecast": forecast, "indicators": indicators, "importance": importance, "gaps": gaps}
