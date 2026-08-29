"""FlowStack 命令行入口。

训练：
  python -m src.flowstack.cli train --data path/to/training_data.xlsx --artifact-dir artifacts/flowstack/current
预测：
  python -m src.flowstack.cli predict --model-dir artifacts/flowstack/current/model \
      --features future_features.csv --output outputs/flowstack/predictions.csv
特征重要性（Agent 接口）：
  python -m src.flowstack.cli importance --model-dir artifacts/flowstack/current/model \
      --output-dir outputs/flowstack/importance
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.flowstack.config import FlowStackConfig
from src.flowstack.model import FlowStackModel
from src.flowstack.service import ImportanceService, PredictionService


def _read_table(path: str) -> pd.DataFrame:
    if path.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path, sheet_name="Sheet1")
    return pd.read_csv(path)


def cmd_train(args: argparse.Namespace) -> None:
    frame = _read_table(args.data)
    config = FlowStackConfig()
    if args.config:
        overrides = json.loads(Path(args.config).read_text(encoding="utf-8"))
        for key, value in overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
    model = FlowStackModel(config).fit(frame)
    artifact_dir = Path(args.artifact_dir)
    model.save(artifact_dir / "model")
    model.feature_importance().to_csv(
        artifact_dir / "feature_importance.csv", index=False, encoding="utf-8-sig")
    ImportanceService(model).export_agent_payload(artifact_dir / "agent_importance.json")
    model.oof_frame_.to_csv(
        artifact_dir / "oof_predictions.csv", index=False, encoding="utf-8-sig")
    print(f"训练完成，产物目录: {artifact_dir}")


def cmd_predict(args: argparse.Namespace) -> None:
    service = PredictionService.from_directory(args.model_dir)
    result = service.predict(_read_table(args.features))
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(destination, index=False, encoding="utf-8-sig")
    print(f"预测完成: {destination}（{len(result)} 行）")


def cmd_importance(args: argparse.Namespace) -> None:
    service = ImportanceService.from_directory(args.model_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    service.global_importance().to_csv(
        out_dir / "feature_importance_global.csv", index=False, encoding="utf-8-sig")
    service.group_importance().to_csv(
        out_dir / "feature_importance_groups.csv", index=False, encoding="utf-8-sig")
    service.redundancy_report().to_csv(
        out_dir / "redundancy_clusters.csv", index=False, encoding="utf-8-sig")
    service.export_agent_payload(out_dir / "agent_importance.json", top_k=args.top_k)
    print(f"重要性输出完成: {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="flowstack")
    sub = parser.add_subparsers(dest="command", required=True)

    p_train = sub.add_parser("train")
    p_train.add_argument("--data", required=True)
    p_train.add_argument("--artifact-dir", required=True)
    p_train.add_argument("--config", default=None)
    p_train.set_defaults(func=cmd_train)

    p_predict = sub.add_parser("predict")
    p_predict.add_argument("--model-dir", required=True)
    p_predict.add_argument("--features", required=True)
    p_predict.add_argument("--output", required=True)
    p_predict.set_defaults(func=cmd_predict)

    p_imp = sub.add_parser("importance")
    p_imp.add_argument("--model-dir", required=True)
    p_imp.add_argument("--output-dir", required=True)
    p_imp.add_argument("--top-k", type=int, default=None)
    p_imp.set_defaults(func=cmd_importance)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
