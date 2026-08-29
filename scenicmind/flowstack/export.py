"""看板 / Agent 中立数据契约整理（只整理数据，不实现看板与 Agent）。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def export_dashboard(
    predictions: pd.DataFrame,
    actuals: pd.DataFrame | None,
    output: str | Path,
) -> Path:
    """预测 vs 实际事实表：适合看板折线图与误差卡片。

    predictions: PredictionService.predict 的输出（date/predicted_visitors/model_version）
    actuals: 含 date 与 visitors 的真实客流表，可为 None（仅预测期导出）。
    """
    out = predictions.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    if actuals is not None and "visitors" in actuals:
        act = actuals[["date", "visitors"]].copy()
        act["date"] = pd.to_datetime(act["date"]).dt.strftime("%Y-%m-%d")
        out = out.merge(act, on="date", how="left").rename(columns={"visitors": "actual_visitors"})
        out["error"] = out["actual_visitors"] - out["predicted_visitors"]
        out["abs_error"] = out["error"].abs()
        out["ape(%)"] = np.where(
            out["actual_visitors"] > 0,
            out["abs_error"] / out["actual_visitors"] * 100, np.nan)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(destination, index=False, encoding="utf-8-sig")
    return destination


def export_agent_daily_facts(
    predictions: pd.DataFrame,
    importance_payload: dict,
    output: str | Path,
) -> Path:
    """日度事实 JSONL：预测值 + 全局特征重要性快照，供 Agent 生成经营建议。

    只包含可验证的指标与特征归因，不包含经营建议本身。
    """
    import json

    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    top_features = importance_payload.get("feature_importance", [])[:10]
    with destination.open("w", encoding="utf-8") as fh:
        for _, row in predictions.iterrows():
            fact = {
                "date": row["date"],
                "predicted_visitors": int(row["predicted_visitors"]),
                "model_version": row.get("model_version", "unknown"),
                "top_drivers": [
                    {"feature": f["feature"], "group": f["group"],
                     "importance": round(f["importance"], 4)}
                    for f in top_features
                ],
            }
            if "actual_visitors" in row and pd.notna(row.get("actual_visitors")):
                fact["actual_visitors"] = float(row["actual_visitors"])
                fact["abs_error"] = float(abs(row["actual_visitors"] - row["predicted_visitors"]))
            fh.write(json.dumps(fact, ensure_ascii=False) + "\n")
    return destination
