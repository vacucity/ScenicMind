from __future__ import annotations

import numpy as np
import pandas as pd

from scenicmind.scenicboost.model import ScenicBoostModel, _catboost
from scenicmind.scenicboost.schema import feature_group, prepare_features


def local_shap(model: ScenicBoostModel, frame: pd.DataFrame, *, top_k: int | None = None) -> pd.DataFrame:
    """Return long-form local contributions; never runs on the prediction hot path."""
    if model.estimator is None:
        raise RuntimeError("模型尚未训练或加载")
    _, Pool = _catboost()
    x = prepare_features(frame, model.feature_names, model.categorical_features)
    pool = Pool(x, cat_features=model.categorical_features)
    values = np.asarray(model.estimator.get_feature_importance(pool, type="ShapValues"), dtype=float)
    shap_values, base_values = values[:, :-1], values[:, -1]
    components = model.predict_components(frame)
    records: list[dict] = []
    for position, (_, row) in enumerate(frame.iterrows()):
        date = pd.Timestamp(row[model.config.date_column]).strftime("%Y-%m-%d")
        feature_rows = []
        for index, name in enumerate(model.feature_names):
            value = row.get(name)
            if pd.isna(value):
                value = None
            elif isinstance(value, np.generic):
                value = value.item()
            contribution = float(shap_values[position, index])
            feature_rows.append(
                {
                    "date": date,
                    "feature_name": name,
                    "feature_group": feature_group(name),
                    "feature_value": value,
                    "shap_value": contribution,
                    "absolute_shap": abs(contribution),
                    "direction": "increase" if contribution >= 0 else "decrease",
                    "base_value": float(base_values[position]),
                    "raw_model_prediction": float(components.iloc[position]["raw_model_prediction"]),
                    "predicted_visitors": int(components.iloc[position]["predicted_visitors"]),
                    "model_version": model.metadata.get("model_version", "unknown"),
                }
            )
        feature_rows.sort(key=lambda item: item["absolute_shap"], reverse=True)
        if top_k is not None:
            feature_rows = feature_rows[:top_k]
        for rank, item in enumerate(feature_rows, start=1):
            item["rank"] = rank
            records.append(item)
    return pd.DataFrame.from_records(records)


def global_shap(model: ScenicBoostModel, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    local = local_shap(model, frame)
    feature_table = (
        local.groupby(["feature_name", "feature_group"], as_index=False)["absolute_shap"]
        .mean()
        .rename(columns={"absolute_shap": "mean_absolute_shap"})
        .sort_values("mean_absolute_shap", ascending=False)
        .reset_index(drop=True)
    )
    total = max(float(feature_table["mean_absolute_shap"].sum()), 1e-12)
    feature_table["importance_share"] = feature_table["mean_absolute_shap"] / total
    feature_table["rank"] = np.arange(1, len(feature_table) + 1)
    feature_table["model_version"] = model.metadata.get("model_version", "unknown")
    group_table = (
        feature_table.groupby("feature_group", as_index=False)["mean_absolute_shap"]
        .sum()
        .sort_values("mean_absolute_shap", ascending=False)
        .reset_index(drop=True)
    )
    group_total = max(float(group_table["mean_absolute_shap"].sum()), 1e-12)
    group_table["importance_share"] = group_table["mean_absolute_shap"] / group_total
    group_table["rank"] = np.arange(1, len(group_table) + 1)
    group_table["model_version"] = model.metadata.get("model_version", "unknown")
    return feature_table, group_table

