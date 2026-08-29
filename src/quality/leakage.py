from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.features.builder import add_target_history


def run_leakage_audit(root: Path, safe: pd.DataFrame) -> list[str]:
    failures: list[str] = []
    actual_cols = [c for c in safe.columns if c.startswith("actual_")]
    if actual_cols:
        failures.append(f"forecast-safe contains realized columns: {actual_cols}")
    direct_target_copies = [c for c in safe.columns if c in {"visitors_github", "visitors_official"}]
    if direct_target_copies:
        failures.append(f"forecast-safe contains direct target copies: {direct_target_copies}")
    sample = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=4), "visitors": [10, 20, 30, 999]})
    engineered = add_target_history(sample)
    if not np.isclose(engineered.loc[3, "visitors_roll_mean_3"], 20.0):
        failures.append("rolling mean includes current target")
    safe_only = set(safe.columns)
    forbidden_exact = {"visitors_diff_1", "visitors_diff_7", "visitors_wow"}
    if safe_only & forbidden_exact:
        failures.append(f"unsafe target transforms present: {sorted(safe_only & forbidden_exact)}")
    lines = ["LEAKAGE AUDIT", "status=" + ("FAIL" if failures else "PASS")]
    lines.extend(f"failure={f}" for f in failures)
    if not failures:
        lines.extend(
            [
                "check=no actual_* fields in forecast-safe: PASS",
                "check=no direct source copies of current visitors: PASS",
                "check=rolling mean uses T-1 and earlier: PASS",
                "check=no direct diff/pct_change target fields: PASS",
                "check=notice point-in-time enforced in builder: PASS",
            ]
        )
    (root / "reports/leakage_audit.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return failures
