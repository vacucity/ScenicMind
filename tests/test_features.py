import numpy as np
import pandas as pd

from scenicmind.features.builder import _aggregate_notice_events, add_target_history


def test_rolling_feature_does_not_include_current_target():
    frame = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=4), "visitors": [10, 20, 30, 999]})
    result = add_target_history(frame)
    assert np.isclose(result.loc[3, "visitors_roll_mean_3"], 20.0)


def test_notice_after_forecast_origin_is_excluded():
    events = pd.DataFrame(
        {
            "event_date": [pd.Timestamp("2025-10-03")],
            "available_at": [pd.Timestamp("2025-10-04", tz="Asia/Shanghai")],
            "sold_out_flag": [1],
        }
    )
    result = _aggregate_notice_events(events, pd.Series([pd.Timestamp("2025-10-03")]), forecast_safe=True)
    assert result.loc[0, "sold_out_flag"] == 0


def test_date_unique_and_nonnegative_example():
    frame = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=3), "visitors": [0, 5000, 41000]})
    assert frame["date"].is_unique
    assert frame["visitors"].ge(0).all()

