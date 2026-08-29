from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from scenicmind.scenicboost.config import load_config
from scenicmind.scenicboost.explain import global_shap
from scenicmind.scenicboost.export import write_integration_outputs
from scenicmind.scenicboost.service import ExplanationService, PredictionService
from scenicmind.scenicboost.training import train_with_backtest


def _read_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def train_command(args: argparse.Namespace) -> None:
    frame = _read_csv(args.data)
    config = load_config(args.config)
    _, _, metrics = train_with_backtest(frame, config, args.artifact_dir)
    print(json.dumps(metrics["overall"], ensure_ascii=False, indent=2))


def predict_command(args: argparse.Namespace) -> None:
    service = PredictionService.from_directory(args.model_dir)
    predictions = service.predict(_read_csv(args.features))
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(destination, index=False, encoding="utf-8-sig")
    print(str(destination))


def explain_command(args: argparse.Namespace) -> None:
    frame = _read_csv(args.features)
    service = ExplanationService.from_directory(args.model_dir)
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    local = service.explain_rows(frame, top_k=args.top_k)
    local.to_csv(destination / "feature_contributions_local.csv", index=False, encoding="utf-8-sig")
    feature_table, group_table = global_shap(service.model, frame)
    feature_table.to_csv(destination / "feature_importance_global.csv", index=False, encoding="utf-8-sig")
    group_table.to_csv(destination / "feature_importance_groups.csv", index=False, encoding="utf-8-sig")
    print(str(destination))


def export_command(args: argparse.Namespace) -> None:
    predictions = _read_csv(args.predictions)
    actuals = _read_csv(args.actuals) if args.actuals else None
    explanations = _read_csv(args.explanations) if args.explanations else None
    paths = write_integration_outputs(
        predictions,
        args.output_dir,
        actuals=actuals,
        local_explanations=explanations,
    )
    print(json.dumps({key: str(value) for key, value in paths.items()}, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ScenicBoost 日度客流预测")
    commands = parser.add_subparsers(dest="command", required=True)
    train = commands.add_parser("train", help="滚动回测并训练模型")
    train.add_argument("--data", default="jiuzhaigou_daily_forecast_safe_h1_clean.csv")
    train.add_argument("--config", default="configs/scenicboost.json")
    train.add_argument("--artifact-dir", default="artifacts/scenicboost/current")
    train.set_defaults(func=train_command)
    predict = commands.add_parser("predict", help="只生成客流预测")
    predict.add_argument("--model-dir", default="artifacts/scenicboost/current/model")
    predict.add_argument("--features", required=True)
    predict.add_argument("--output", default="outputs/scenicboost/predictions.csv")
    predict.set_defaults(func=predict_command)
    explain = commands.add_parser("explain", help="独立生成 TreeSHAP 解释")
    explain.add_argument("--model-dir", default="artifacts/scenicboost/current/model")
    explain.add_argument("--features", required=True)
    explain.add_argument("--output-dir", default="outputs/scenicboost/explanations")
    explain.add_argument("--top-k", type=int, default=10)
    explain.set_defaults(func=explain_command)
    export = commands.add_parser("export", help="整理看板和 Agent 可消费的数据文件")
    export.add_argument("--predictions", required=True)
    export.add_argument("--actuals")
    export.add_argument("--explanations")
    export.add_argument("--output-dir", default="outputs/scenicboost/integration")
    export.set_defaults(func=export_command)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

