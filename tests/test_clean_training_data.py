import pandas as pd

from scenicmind.quality.clean_training_data import clean_frame


def test_cleaner_drops_missing_target_and_removes_nulls():
    dates = pd.date_range("2025-01-01", periods=20)
    frame = pd.DataFrame(
        {
            "date": dates,
            "visitors": [10, None] + list(range(12, 30)),
            "target_source": ["official", None] + ["official"] * 18,
            "target_quality": ["high", None] + ["high"] * 18,
            "target_conflict": [0, None] + [0] * 18,
            "holiday_name": [None] * 20,
            "holiday_day_index": [None] * 20,
            "holiday_length": [None] * 20,
            "days_until_holiday_end": [None] * 20,
            "days_to_next_holiday": [None] * 20,
            "days_since_prev_holiday": [None] * 20,
            "known_reserved_count": [None] * 20,
            "daily_capacity": [None] * 20,
            "sold_out_notice_lead_days": [None] * 20,
            "booking_pressure_ratio": [None] * 20,
            "visitors_lag_1": [None] + list(range(10, 29)),
            "visitors_lag_7": [None] * 7 + list(range(10, 23)),
            "visitors_roll_mean_7": [None] * 7 + list(range(10, 23)),
            "visitors_roll_mean_28": [None] * 20,
            "visitors_trend_strength": [None] * 20,
            "visitors_lag1_vs_ma7": [None] * 20,
            "visitors_lag7_vs_ma28": [None] * 20,
            "wiki_zh_views_lag1": [None] + list(range(100, 119)),
        }
    )
    cleaned, report = clean_frame(frame, forecast_safe=True)
    assert report["target_missing_rows_dropped"] == 1
    assert not cleaned.isna().any().any()
    assert cleaned["date"].is_unique

