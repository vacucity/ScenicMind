from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


EXACT = {
    "date": ("日期", "YYYY-MM-DD", "日度记录主键。"),
    "visitors": ("游客接待量", "人次", "当天九寨沟景区接待游客数量；模型预测目标，不作为输入特征。"),
    "target_source": ("客流来源", "类别", "当天游客量的最终采用来源，例如九寨沟官网或 GitHub 种子数据。"),
    "target_quality": ("客流质量等级", "类别", "游客量记录的来源质量说明。"),
    "target_conflict": ("客流来源冲突", "0/1", "官网与 GitHub 同日数值是否冲突；1 表示冲突。"),
    "target_missing": ("客流是否缺失", "0/1", "原始日期骨架中当天游客量是否缺失；清洗版已删除目标缺失行。"),
    "year": ("年份", "年", "公历年份。"),
    "month": ("月份", "1-12", "公历月份。"),
    "day": ("月内日期", "1-31", "当月第几日。"),
    "weekday": ("星期序号", "0-6", "星期一为 0，星期日为 6。"),
    "day_of_year": ("年内日序", "1-366", "当年第几天。"),
    "week_of_year": ("年内周序", "ISO 周", "ISO-8601 年内周数。"),
    "quarter": ("季度", "1-4", "公历季度。"),
    "is_weekend": ("是否周末", "0/1", "星期六或星期日为 1；不代表一定休息。"),
    "is_official_holiday": ("是否法定节假日", "0/1", "国务院节假日安排中的正式放假日。"),
    "is_makeup_workday": ("是否调休上班日", "0/1", "原本是周末但按国务院安排调休上班的日期。"),
    "is_rest_day": ("是否实际休息日", "0/1", "结合法定节假日、周末和调休判断的实际休息日。"),
    "holiday_name": ("节假日名称", "类别", "春节、国庆节等；普通日期在清洗版中为“非节假日”。"),
    "holiday_day_index": ("假期第几天", "天", "连续假期中的日序；非节假日为 0。"),
    "holiday_length": ("假期长度", "天", "当前连续假期的总天数；非节假日为 0。"),
    "days_until_holiday_end": ("距假期结束天数", "天", "当前假期距最后一天还有多少天；非节假日为 0。"),
    "days_to_next_holiday": ("距下一法定假日", "天", "从当天到下一法定假日的自然日数。"),
    "days_since_prev_holiday": ("距上一法定假日", "天", "从上一法定假日到当天的自然日数。"),
    "is_pre_holiday_1": ("节前 1 天", "0/1", "距离下一法定假日恰好 1 天。"),
    "is_pre_holiday_3": ("节前 3 天窗口", "0/1", "距离下一法定假日 1 至 3 天。"),
    "is_post_holiday_1": ("节后 1 天", "0/1", "距离上一法定假日恰好 1 天。"),
    "is_post_holiday_3": ("节后 3 天窗口", "0/1", "距离上一法定假日 1 至 3 天。"),
    "is_summer_vacation": ("是否暑期", "0/1", "7 月或 8 月为 1。"),
    "is_winter_vacation": ("是否寒假期", "0/1", "1 月或 2 月为 1。"),
    "is_peak_season": ("是否景区旺季", "0/1", "4 月 1 日至 11 月 15 日为 1。"),
    "is_offseason": ("是否景区淡季", "0/1", "旺季以外日期为 1。"),
    "is_month_start": ("是否月初", "0/1", "当月第一天。"),
    "is_month_end": ("是否月末", "0/1", "当月最后一天。"),
    "sin_doy": ("年周期正弦编码", "-1~1", "年内日序的正弦周期编码。"),
    "cos_doy": ("年周期余弦编码", "-1~1", "年内日序的余弦周期编码。"),
    "sin_weekday": ("周周期正弦编码", "-1~1", "星期序号的正弦周期编码。"),
    "cos_weekday": ("周周期余弦编码", "-1~1", "星期序号的余弦周期编码。"),
    "sold_out_flag": ("是否售罄", "0/1", "官方公告是否表明当天门票售罄或达到最大承载量。"),
    "official_notice_count": ("相关公告数量", "篇", "解析后指向当天的九寨沟官方公告数量。"),
    "known_reserved_count": ("已知预约量", "人次", "预测时点前公告披露的当天预约人数；无已知公告时清洗版填 0。"),
    "daily_capacity": ("已知日承载量", "人次/日", "公告中披露的当天最大承载量；无已知公告时清洗版填 0。"),
    "sold_out_notice_lead_days": ("售罄公告提前天数", "天", "售罄公告发布时间相对游览日期提前的天数。"),
    "booking_pressure_ratio": ("预约压力比", "比例", "已知预约量除以已知日承载量；无有效公告时为 0。"),
    "is_closed": ("是否闭园", "0/1", "官方公告是否明确当天闭园或暂停开放。"),
    "is_reopen": ("是否恢复开放", "0/1", "官方公告是否明确当天恢复开放。"),
    "is_partial_open": ("是否部分开放", "0/1", "官方公告是否明确部分区域开放或游览调整。"),
    "discount_flag": ("是否门票优惠", "0/1", "官方公告是否包含面向当天的门票优惠政策。"),
    "free_ticket_flag": ("是否免门票", "0/1", "官方公告是否包含面向当天的免门票政策。"),
    "capacity_restricted": ("是否限流", "0/1", "官方公告是否包含最大承载量或限流要求。"),
    "huanglong_jiuzhai_hsr_open": ("黄龙九寨站是否开通", "0/1", "2024-08-30 起为 1。"),
    "days_since_hsr_open": ("高铁站开通后天数", "天", "黄龙九寨站开通后的累计自然日数，开通前为 0。"),
    "jiuzhai_mianyang_expressway_open": ("九绵高速是否开通", "0/1", "2025-09-28 起为 1。"),
    "days_since_expressway_open": ("高速开通后天数", "天", "九绵高速全线开通后的累计自然日数，开通前为 0。"),
    "feature_missing_count": ("原始特征缺失数", "个", "清洗前该行缺失的特征数量。"),
    "quality_score": ("原始行质量分", "0~1", "按原始特征完整率计算的行级质量分；越接近 1 越完整。"),
    "historical_target_imputed_count": ("历史客流填补数", "个", "清洗过程中该行有多少个 lag/rolling 历史客流字段被过去数据回填。"),
}

ACTUAL_WEATHER = {
    "temp_mean": ("日平均气温", "°C"), "temp_max": ("日最高气温", "°C"), "temp_min": ("日最低气温", "°C"),
    "apparent_temp_mean": ("日平均体感温度", "°C"), "apparent_temp_max": ("日最高体感温度", "°C"),
    "precipitation_sum": ("日总降水量", "mm"), "rain_sum": ("日降雨量", "mm"), "snowfall_sum": ("日降雪量", "cm"),
    "precipitation_hours": ("降水小时数", "小时"), "weather_code": ("天气代码", "WMO 代码"),
    "wind_speed_max": ("最大风速", "km/h"), "wind_gust_max": ("最大阵风", "km/h"), "sunshine_duration": ("日照时长", "秒"),
    "humidity_mean": ("平均相对湿度", "%"), "humidity_max": ("最大相对湿度", "%"), "dew_point_mean": ("平均露点温度", "°C"),
    "cloud_cover_mean": ("平均云量", "%"), "cloud_cover_max": ("最大云量", "%"), "pressure_mean": ("平均地表气压", "hPa"),
    "wind_speed_mean": ("平均风速", "km/h"), "temp_range": ("日温差", "°C"), "is_rain": ("是否降雨", "0/1"),
    "is_heavy_rain": ("是否大雨", "0/1"), "is_snow": ("是否降雪", "0/1"), "is_extreme_cold": ("是否极端低温", "0/1"),
    "is_extreme_heat": ("是否极端高温", "0/1"), "rain_3d_sum": ("近 3 日累计降雨", "mm"), "rain_7d_sum": ("近 7 日累计降雨", "mm"),
    "bad_weather_flag": ("恶劣天气标记", "0/1"),
}


def explain(column: str) -> tuple[str, str, str]:
    if column in EXACT:
        return EXACT[column]
    if column.startswith("actual_"):
        key = column.removeprefix("actual_")
        label, unit = ACTUAL_WEATHER.get(key, (key.replace("_", " "), "数值"))
        return label, unit, "Open-Meteo 当天实况天气；仅用于解释性数据，不用于严格 T+1 预测。"
    if m := re.fullmatch(r"visitors_lag_(\d+)", column):
        n = m.group(1)
        return f"客流滞后 {n} 天", "人次", f"日期 T 之前第 {n} 个自然日的游客量；缺失时清洗版仅用 T 之前数据回填。"
    if m := re.fullmatch(r"visitors_roll_(mean|median|std|min|max|q25|q75)_(\d+)", column):
        labels = {"mean": "均值", "median": "中位数", "std": "标准差", "min": "最小值", "max": "最大值", "q25": "25%分位数", "q75": "75%分位数"}
        stat, n = m.groups()
        return f"过去 {n} 日客流{labels[stat]}", "人次", f"基于 visitors.shift(1) 计算的过去 {n} 日统计，不包含当天目标。"
    if column == "visitors_trend_strength":
        return "客流趋势强度", "比值", "过去 7 日均值除以过去 28 日均值。"
    if column == "visitors_lag1_vs_ma7":
        return "昨日客流相对短期均值", "比值", "前 1 日游客量除以过去 7 日均值。"
    if column == "visitors_lag7_vs_ma28":
        return "上周同日客流相对长期均值", "比值", "前 7 日游客量除以过去 28 日均值。"
    if column.endswith("_known"):
        base = column.removesuffix("_known")
        return f"{explain(base)[0]}是否已知", "0/1", f"1 表示原始数据中确有 {base}，0 表示清洗时因无已知公告而填 0。"
    if column.endswith("_was_missing"):
        base = column.removesuffix("_was_missing")
        return f"{base}原始是否缺失", "0/1", "1 表示该值由清洗规则填补，0 表示原始数据已有值。"
    if column.startswith("wiki_"):
        lang = "中文" if "wiki_zh" in column else "英文"
        if column.endswith("_views"):
            return f"{lang}维基页面浏览量", "次", f"九寨沟{lang}维基百科页面当天浏览次数。"
        if m := re.search(r"_(lag1|lag7|ma7|ma14|growth7)$", column):
            suffix = m.group(1)
            labels = {"lag1": "前 1 日浏览量", "lag7": "前 7 日浏览量", "ma7": "过去 7 日平均浏览量", "ma14": "过去 14 日平均浏览量", "growth7": "7 日增长率"}
            unit = "比例" if suffix == "growth7" else "次"
            return f"{lang}维基{labels[suffix]}", unit, "基于预测日之前已经产生的 Wikimedia 浏览量计算。"
    return column.replace("_", " "), "数值/类别", "派生或质量控制字段，字段名对应其计算含义。"


def build(root: Path) -> Path:
    explanatory = pd.read_csv(root / "jiuzhaigou_daily_explanatory_clean.csv", nrows=5)
    safe = pd.read_csv(root / "jiuzhaigou_daily_forecast_safe_h1_clean.csv", nrows=5)
    exp_cols, safe_cols = list(explanatory.columns), list(safe.columns)
    union = list(dict.fromkeys(exp_cols + safe_cols))
    lines = [
        "# 九寨沟训练数据集变量说明",
        "",
        "本文件与 `README.md` 同级，覆盖两份清洗数据的全部变量。严格训练预测建议使用 `jiuzhaigou_daily_forecast_safe_h1_clean.csv`；实况天气字段仅用于解释性分析。",
        "",
        f"- 解释性清洗数据：{len(exp_cols)} 列",
        f"- T+1 安全清洗数据：{len(safe_cols)} 列",
        f"- 两份数据合计唯一字段：{len(union)} 个",
        "",
        "| 字段名 | 中文含义 | 单位/取值 | 所在数据集 | T+1 可用性 | 详细解释 |",
        "|---|---|---|---|---|---|",
    ]
    for col in union:
        label, unit, description = explain(col)
        membership = "两份都有" if col in exp_cols and col in safe_cols else ("仅解释性" if col in exp_cols else "仅 T+1 安全版")
        if col == "visitors":
            safety = "预测目标"
        elif col in safe_cols:
            safety = "可用"
        else:
            safety = "不可用于严格 T+1"
        values = [col, label, unit, membership, safety, description]
        lines.append("| " + " | ".join(str(v).replace("|", "\\|").replace("\n", " ") for v in values) + " |")
    lines.extend(
        [
            "",
            "## 清洗标记说明",
            "",
            "- `*_known`：用于区分“公告中真实给出数值”和“因无已知公告而填 0”。",
            "- `*_was_missing`：用于标记 Wikimedia 字段是否经过清洗填补。",
            "- `historical_target_imputed_count`：记录一行中有多少个历史客流特征经过仅使用过去数据的回填。",
            "- `feature_missing_count` 与 `quality_score` 描述清洗前的数据质量，清洗后仍保留供建模筛选或加权使用。",
        ]
    )
    output = root / "变量说明.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    print(build(Path.cwd()))

