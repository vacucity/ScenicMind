from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path

import pandas as pd

from scenicmind.collectors import jiuzhai_notices, jiuzhai_visitors, openmeteo_weather, wikimedia
from scenicmind.features import calendar as calendar_features
from scenicmind.features.builder import build_gold
from scenicmind.importers import github_target
from scenicmind.io import read_yaml
from scenicmind.quality.checks import run_quality_report
from scenicmind.quality.leakage import run_leakage_audit


def _record_exclusion(root: Path, source: str, reason: str) -> None:
    path = root / "reports/source_exclusions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    current = [x for x in current if x.get("source") != source]
    current.append({"source": source, "reason": reason})
    path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")


def build(root: Path, refresh: bool = False) -> dict:
    sources = read_yaml(root / "configs/sources.yaml")
    scenic = read_yaml(root / "configs/scenic.yaml")["scenic"]
    feature_config = read_yaml(root / "configs/features.yaml")
    for path in [
        "data/bronze/visitors",
        "data/bronze/notices/articles",
        "data/bronze/weather",
        "data/bronze/wikipedia",
        "data/manual/baidu_index",
        "data/silver",
        "data/gold",
        "reports",
    ]:
        (root / path).mkdir(parents=True, exist_ok=True)

    default_exclusions = [
        {
            "source": "historical_d1_weather_forecast",
            "reason": "No reproducible issue-time D-1 archive was available for the full target range; excluded from forecast-safe instead of substituting realized weather.",
        },
        {
            "source": "baidu_index",
            "reason": "Baidu provides no official open API and no user-authorized manual export was supplied.",
        },
        {
            "source": "historical_air_quality",
            "reason": "A stable complete daily archive covering the target period was not available.",
        },
        {
            "source": "airport_monthly_statistics",
            "reason": "No complete, consistently published, point-in-time monthly series was found.",
        },
        {
            "source": "hotel_ota_history",
            "reason": "Historical backfill is not reproducible without restricted platform access; no anti-bot bypass was attempted.",
        },
        {
            "source": "gdelt",
            "reason": "Official API connectivity timed out during this build, so no GDELT columns were created.",
        },
    ]
    (root / "reports/source_exclusions.json").write_text(
        json.dumps(default_exclusions, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    github = github_target.collect(sources["github_target"], root, refresh=refresh)
    try:
        official = jiuzhai_visitors.collect(
            sources["official_visitors"], root, scenic["target_start"], refresh=refresh
        )
    except Exception as exc:
        _record_exclusion(root, "jiuzhai_official_target", f"{type(exc).__name__}: {exc}")
        official = pd.DataFrame(columns=["date", "visitors", "source_url", "published_at", "target_quality"])
    target = jiuzhai_visitors.merge_targets(github, official, root)

    start, end = target["date"].min(), target["date"].max()
    calendar = calendar_features.build(start, end, root)
    weather = openmeteo_weather.collect(
        sources["open_meteo_archive"],
        root,
        scenic["latitude"],
        scenic["longitude"],
        scenic["timezone"],
        start,
        end,
        refresh=refresh,
    )
    try:
        wiki = wikimedia.collect(sources["wikimedia_pageviews"], root, start, end, refresh=refresh)
    except Exception as exc:
        _record_exclusion(root, "wikimedia", f"{type(exc).__name__}: {exc}")
        wiki = pd.DataFrame({"date": pd.date_range(start, end, freq="D")})

    notice_raw = notice_events = None
    try:
        notice_raw, notice_events = jiuzhai_notices.collect(sources["official_notices"], root, refresh=refresh)
    except Exception as exc:
        _record_exclusion(root, "jiuzhai_official_notices", f"{type(exc).__name__}: {exc}")
        (root / "reports/notice_error.txt").write_text(traceback.format_exc(), encoding="utf-8")

    explanatory, safe = build_gold(
        root,
        target,
        calendar,
        weather,
        wiki,
        notice_events,
        feature_config["weather_thresholds"],
    )
    leakage_failures = run_leakage_audit(root, safe)
    quality = run_quality_report(root, target, explanatory, safe, notice_raw)
    summary = {
        **quality,
        "leakage_failures": leakage_failures,
        "official_rows": len(official),
        "github_rows": len(github),
        "notice_events": 0 if notice_events is None else len(notice_events),
    }
    (root / "reports/build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build the Jiuzhaigou multi-source daily training dataset")
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)
    root = Path.cwd()
    if args.command == "build":
        summary = build(root, refresh=args.refresh)
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
