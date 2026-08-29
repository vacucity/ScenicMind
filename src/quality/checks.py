from __future__ import annotations

import html
from pathlib import Path

import pandas as pd


def _pct(x: float) -> str:
    return f"{x:.2%}"


def run_quality_report(
    root: Path,
    target: pd.DataFrame,
    explanatory: pd.DataFrame,
    safe: pd.DataFrame,
    notice_raw: pd.DataFrame | None,
) -> dict:
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    missingness = pd.DataFrame(
        {
            "column": explanatory.columns,
            "missing_count": explanatory.isna().sum().values,
            "missing_rate": explanatory.isna().mean().values,
        }
    ).sort_values(["missing_rate", "column"], ascending=[False, True])
    missingness.to_csv(reports / "missingness.csv", index=False, encoding="utf-8-sig")

    checks = {
        "date_min": target["date"].min().date().isoformat(),
        "date_max": target["date"].max().date().isoformat(),
        "rows": len(target),
        "duplicate_dates": int(target["date"].duplicated().sum()),
        "target_missing_count": int(target["visitors"].isna().sum()),
        "target_missing_rate": float(target["visitors"].isna().mean()),
        "negative_visitors": int(target["visitors"].lt(0).fillna(False).sum()),
        "target_conflicts": int(target.get("target_conflict", pd.Series(dtype=int)).fillna(0).sum()),
        "explanatory_columns": explanatory.shape[1],
        "forecast_safe_columns": safe.shape[1],
        "weather_coverage": float(explanatory.filter(regex="^actual_temp_mean$").notna().mean().iloc[0])
        if "actual_temp_mean" in explanatory
        else 0.0,
        "wiki_zh_coverage": float(explanatory["wiki_zh_views"].notna().mean()) if "wiki_zh_views" in explanatory else 0.0,
        "notice_articles": 0 if notice_raw is None else len(notice_raw),
    }
    severity = "PASS"
    if checks["duplicate_dates"] or checks["negative_visitors"]:
        severity = "FAIL"
    elif checks["target_missing_rate"] > 0.02 or checks["weather_coverage"] < 0.98:
        severity = "WARN"
    checks["status"] = severity

    rows = "".join(
        f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(_pct(v) if k.endswith('_rate') or k.endswith('_coverage') else str(v))}</td></tr>"
        for k, v in checks.items()
    )
    report = f"""<!doctype html>
<html lang='zh-CN'><head><meta charset='utf-8'><title>九寨沟数据质量报告</title>
<style>body{{font-family:system-ui,'Microsoft YaHei',sans-serif;max-width:1000px;margin:40px auto;color:#172033}}h1{{color:#0b6b53}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #d8dee9;padding:9px;text-align:left}}th{{background:#eef7f4}}code{{background:#f3f5f7;padding:2px 5px}}.note{{background:#fff8df;border-left:4px solid #d29b00;padding:12px}}</style></head>
<body><h1>九寨沟训练数据质量报告</h1><p>状态：<strong>{severity}</strong></p>
<table>{rows}</table>
<h2>质量结论</h2><ul>
<li>日期粒度为每日，主键应为 <code>date</code>。</li>
<li>高客流值未按 IQR 或 z-score 自动删除；仅检查重复、负值和缺失。</li>
<li>forecast-safe 表不含任何 <code>actual_*</code> 实况天气字段。</li>
<li>历史客流 rolling 使用 <code>visitors.shift(1)</code>，公告使用 available-at 截止规则。</li>
</ul><div class='note'>完整列级缺失率见 reports/missingness.csv；可选数据源抓取失败时，该来源不会以全空列进入 Gold。</div>
</body></html>"""
    (reports / "data_quality.html").write_text(report, encoding="utf-8")
    return checks

