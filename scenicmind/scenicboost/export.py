from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def build_forecast_actual(
    predictions: pd.DataFrame,
    actuals: pd.DataFrame | None = None,
    *,
    date_column: str = "date",
    actual_column: str = "visitors",
) -> pd.DataFrame:
    required = {date_column, "predicted_visitors", "model_version"}
    missing = sorted(required - set(predictions.columns))
    if missing:
        raise ValueError(f"预测结果缺少字段: {missing}")
    output = predictions[[date_column, "predicted_visitors", "model_version"]].copy()
    output[date_column] = pd.to_datetime(output[date_column], errors="raise")
    if actuals is not None:
        truth = actuals[[date_column, actual_column]].copy()
        truth[date_column] = pd.to_datetime(truth[date_column], errors="raise")
        truth = truth.rename(columns={actual_column: "actual_visitors"})
        output = output.merge(truth, on=date_column, how="left", validate="one_to_one")
    else:
        output["actual_visitors"] = np.nan
    output["error"] = output["predicted_visitors"] - output["actual_visitors"]
    output["absolute_error"] = output["error"].abs()
    denominator = output["actual_visitors"].abs().replace(0, np.nan)
    output["absolute_percentage_error"] = output["absolute_error"] / denominator * 100
    output["actual_status"] = np.where(output["actual_visitors"].notna(), "available", "pending")
    output[date_column] = output[date_column].dt.strftime("%Y-%m-%d")
    return output.sort_values(date_column).reset_index(drop=True)


def _top_groups(explanations: pd.DataFrame, dates: set[str], top_k: int = 5) -> list[dict]:
    if explanations.empty:
        return []
    subset = explanations[explanations["date"].astype(str).isin(dates)]
    if subset.empty:
        return []
    grouped = (
        subset.groupby("feature_group", as_index=False)["absolute_shap"]
        .mean()
        .sort_values("absolute_shap", ascending=False)
        .head(top_k)
    )
    total = max(float(grouped["absolute_shap"].sum()), 1e-12)
    return [
        {
            "feature_group": row.feature_group,
            "mean_absolute_shap": round(float(row.absolute_shap), 3),
            "importance_share_within_top": round(float(row.absolute_shap) / total, 6),
        }
        for row in grouped.itertuples(index=False)
    ]


def build_agent_contexts(
    forecast_actual: pd.DataFrame,
    local_explanations: pd.DataFrame | None = None,
) -> dict[str, list[dict]]:
    """Create neutral facts for a future Agent; no recommendation is generated here."""
    frame = forecast_actual.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    explanations = local_explanations if local_explanations is not None else pd.DataFrame()
    daily: list[dict] = []
    for row in frame.itertuples(index=False):
        date = row.date.strftime("%Y-%m-%d")
        actual = None if pd.isna(row.actual_visitors) else int(round(row.actual_visitors))
        daily.append(
            {
                "grain": "day",
                "period_start": date,
                "period_end": date,
                "model_version": row.model_version,
                "metrics": {
                    "predicted_visitors": int(row.predicted_visitors),
                    "actual_visitors": actual,
                    "error": None if pd.isna(row.error) else round(float(row.error), 3),
                    "absolute_percentage_error": None
                    if pd.isna(row.absolute_percentage_error)
                    else round(float(row.absolute_percentage_error), 4),
                },
                "top_feature_groups": _top_groups(explanations, {date}),
            }
        )

    outputs: dict[str, list[dict]] = {"daily": daily, "weekly": [], "monthly": []}
    for label, period in [("weekly", "W-SUN"), ("monthly", "M")]:
        for _, group in frame.groupby(frame["date"].dt.to_period(period)):
            dates = set(group["date"].dt.strftime("%Y-%m-%d"))
            actual_available = group["actual_visitors"].notna()
            actual_total = float(group.loc[actual_available, "actual_visitors"].sum()) if actual_available.any() else None
            predicted_for_actual = float(group.loc[actual_available, "predicted_visitors"].sum()) if actual_available.any() else None
            absolute_error = float(group.loc[actual_available, "absolute_error"].sum()) if actual_available.any() else None
            wape = (
                absolute_error / max(abs(actual_total), 1.0) * 100
                if actual_total is not None and absolute_error is not None
                else None
            )
            outputs[label].append(
                {
                    "grain": "week" if label == "weekly" else "month",
                    "period_start": group["date"].min().strftime("%Y-%m-%d"),
                    "period_end": group["date"].max().strftime("%Y-%m-%d"),
                    "model_version": str(group["model_version"].iloc[-1]),
                    "metrics": {
                        "predicted_visitors_total": int(group["predicted_visitors"].sum()),
                        "actual_visitors_total": None if actual_total is None else int(round(actual_total)),
                        "predicted_total_on_observed_days": None
                        if predicted_for_actual is None
                        else int(round(predicted_for_actual)),
                        "wape": None if wape is None else round(float(wape), 4),
                        "observed_days": int(actual_available.sum()),
                        "period_days": int(len(group)),
                    },
                    "top_feature_groups": _top_groups(explanations, dates),
                }
            )
    return outputs


def write_integration_outputs(
    predictions: pd.DataFrame,
    output_directory: str | Path,
    *,
    actuals: pd.DataFrame | None = None,
    local_explanations: pd.DataFrame | None = None,
) -> dict[str, Path]:
    destination = Path(output_directory)
    destination.mkdir(parents=True, exist_ok=True)
    comparison = build_forecast_actual(predictions, actuals)
    comparison_path = destination / "forecast_actual.csv"
    comparison.to_csv(comparison_path, index=False, encoding="utf-8-sig")
    contexts = build_agent_contexts(comparison, local_explanations)
    paths = {"forecast_actual": comparison_path}
    for name, records in contexts.items():
        path = destination / f"agent_context_{name}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        paths[f"agent_context_{name}"] = path
    return paths
