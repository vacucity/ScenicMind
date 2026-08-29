import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ApiError } from "../../../api/client";
import {
  agentChat,
  createAgentReport,
  getAgentReport,
  getAgentReports,
  getAnalysis,
  getImportance,
  getIndicators,
  getLatestAnalysis,
  type AnalysisEnvelope,
  type AnalysisResult,
  type ChartPoint,
  type FeatureImportanceItem,
  type ImportancePayload,
  type SemanticImportanceGroup,
} from "../../../api/analyses";
import { navigate } from "../../../app/navigation";
import { clearSession, getSession, signOut } from "../../auth/services/session";

type Horizon = 7 | 14 | 30;
type IconName = "dashboard" | "upload" | "drivers" | "report";

const GROUP_META: Record<string, Omit<SemanticImportanceGroup, "importance">> = {
  history: { key: "history", label: "历史客流走势", description: "近期变化、周期规律与客流波动" },
  calendar: { key: "calendar", label: "节假日与季节", description: "节假日、休息日及季节性变化" },
  weather: { key: "weather", label: "天气条件", description: "温度、降水、风力与恶劣天气" },
  attention: { key: "attention", label: "网络关注度", description: "搜索热度与百科关注趋势" },
  operation: { key: "operation", label: "预约与运营", description: "预约量、承载限制与官方公告" },
  transport: { key: "transport", label: "交通可达性", description: "高铁、高速等交通条件变化" },
};

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    dashboard: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
    upload: <><path d="M12 16V3m0 0L7 8m5-5 5 5"/><path d="M5 14v6h14v-6"/></>,
    drivers: <><path d="M4 19V9m8 10V5m8 14v-7"/><path d="M2 19h20"/></>,
    report: <><path d="M6 3h9l4 4v14H6z"/><path d="M15 3v4h4"/><path d="M9 12h6M9 16h6"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

/** 把带 null 的点序列生成为分段 path：连续段用 L，断裂处用 M 起新段 */
function segmentedPath(coords: Array<[number, number] | null>): string {
  let d = "";
  let inSegment = false;
  for (const point of coords) {
    if (point === null) {
      inSegment = false;
      continue;
    }
    d += `${inSegment ? "L" : "M"} ${point[0]} ${point[1]} `;
    inSegment = true;
  }
  return d.trim();
}

function TrendChart({ result, horizon }: { result: AnalysisResult; horizon: Horizon }) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [drawProgress, setDrawProgress] = useState(0);
  const [pathLengths, setPathLengths] = useState<{ actual: number; forecast: number }>({ actual: 0, forecast: 0 });
  const actualRef = useRef<SVGPathElement>(null);
  const forecastRef = useRef<SVGPathElement>(null);
  const points = useMemo(
    () => [...result.historyPoints.slice(-30), ...result.forecastPoints.slice(0, horizon)],
    [result, horizon],
  );

  // 曲线动态逐步绘制动画
  useEffect(() => {
    setDrawProgress(0);
    let raf: number;
    const start = performance.now();
    const duration = 1400;
    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setDrawProgress(eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [horizon, result]);

  // 挂载后测量路径长度（解决首帧 getTotalLength 返回 0 的问题）
  useLayoutEffect(() => {
    const measure = () => {
      const actualLen = actualRef.current?.getTotalLength() ?? 0;
      const forecastLen = forecastRef.current?.getTotalLength() ?? 0;
      if (actualLen > 0 || forecastLen > 0) {
        setPathLengths({ actual: actualLen, forecast: forecastLen });
      }
    };
    measure();
    // SVG path 长度有时需要一帧后才准确
    const raf = requestAnimationFrame(measure);
    return () => cancelAnimationFrame(raf);
  }, [horizon, result]);

  useEffect(() => setActiveIndex(null), [horizon]);

  const width = 880;
  const height = 280;
  const pad = { top: 20, right: 20, bottom: 36, left: 52 };
  const values = points.flatMap(point => [point.actualVisitors, point.predictedVisitors]).filter((value): value is number => value !== null);
  const max = Math.ceil(Math.max(...values, 1) * 1.1 / 1000) * 1000;
  const x = (index: number) => pad.left + index * ((width - pad.left - pad.right) / Math.max(points.length - 1, 1));
  const y = (value: number) => height - pad.bottom - value / max * (height - pad.top - pad.bottom);
  // 保留 null 的坐标序列，用 segmentedPath 分段绘制
  const actualCoords = points.map((point, index) => point.actualVisitors === null ? null : [x(index), y(point.actualVisitors)] as [number, number]);
  const predictedCoords = points.map((point, index) => point.predictedVisitors === null ? null : [x(index), y(point.predictedVisitors)] as [number, number]);
  const forecastStart = result.historyPoints.slice(-30).length;
  const labelEvery = Math.max(1, Math.ceil(points.length / 8));
  const activePoint = activeIndex === null ? null : points[activeIndex];
  const tooltipX = activeIndex === null ? 0 : Math.min(Math.max(x(activeIndex) - 72, pad.left), width - pad.right - 144);
  const tooltipY = activePoint
    ? Math.max(8, Math.min(y(activePoint.predictedVisitors ?? activePoint.actualVisitors ?? 0) - 72, height - 104))
    : 0;

  // 动态绘制：真实线先绘制（0~55%），预测线后绘制（55%~100%）
  const actualVisible = drawProgress <= 0.55 ? drawProgress / 0.55 : 1;
  const forecastVisible = drawProgress <= 0.55 ? 0 : (drawProgress - 0.55) / 0.45;
  const actualLen = pathLengths.actual;
  const forecastLen = pathLengths.forecast;

  return (
    <div className="chart-wrap">
      <svg className="trend-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`真实客流、历史回测与未来${horizon}天预测趋势`} onMouseLeave={() => setActiveIndex(null)}>
        <rect x={x(forecastStart) - 8} y={pad.top} width={width - pad.right - x(forecastStart) + 8} height={height - pad.top - pad.bottom} className="forecast-zone"/>
        {[0, .25, .5, .75, 1].map(rate => <g key={rate}><line x1={pad.left} x2={width - pad.right} y1={y(max * rate)} y2={y(max * rate)} className="chart-grid"/><text x={pad.left - 12} y={y(max * rate) + 4} textAnchor="end" className="chart-axis-label">{Math.round(max * rate / 1000)}k</text></g>)}
        <line x1={x(forecastStart)} x2={x(forecastStart)} y1={pad.top} y2={height - pad.bottom} className="forecast-boundary"/>
        <text x={x(forecastStart) + 8} y={pad.top + 12} className="forecast-boundary-label">预测开始</text>
        <path
          ref={actualRef}
          d={segmentedPath(actualCoords)}
          className="actual-line chart-series"
          style={actualLen ? { strokeDasharray: `${actualLen} ${actualLen}`, strokeDashoffset: actualLen * (1 - actualVisible) } : undefined}
        />
        <path
          ref={forecastRef}
          d={segmentedPath(predictedCoords)}
          className="forecast-line chart-series"
          style={forecastLen ? { strokeDasharray: `${forecastLen} ${forecastLen}`, strokeDashoffset: forecastLen * (1 - forecastVisible) } : undefined}
        />
        {drawProgress >= 0.99 && points.map((point, index) => <g
          key={`${point.date}-${point.kind}`}
          className="chart-point"
          tabIndex={0}
          role="button"
          aria-label={`${point.date}，真实${point.actualVisitors?.toLocaleString() ?? "无"}人，预测${point.predictedVisitors?.toLocaleString() ?? "无"}人`}
          onMouseEnter={() => setActiveIndex(index)}
          onFocus={() => setActiveIndex(index)}
          onBlur={() => setActiveIndex(null)}
        >
          <line x1={x(index)} x2={x(index)} y1={pad.top} y2={height - pad.bottom} className="chart-hit-line"/>
          {point.actualVisitors !== null && <circle cx={x(index)} cy={y(point.actualVisitors)} r={activeIndex === index ? 4 : 2.8} className="actual-dot"/>}
          {point.predictedVisitors !== null && <circle cx={x(index)} cy={y(point.predictedVisitors)} r={activeIndex === index ? 4 : 2.8} className="forecast-dot"/>}
          {(index % labelEvery === 0 || index === points.length - 1) && <text x={x(index)} y={height - 12} textAnchor="middle" className="chart-label">{point.date.slice(5).replace("-", "/")}</text>}
        </g>)}
        {activePoint && <g className="chart-tooltip" transform={`translate(${tooltipX} ${tooltipY})`}>
          <rect width="144" height={activePoint.actualVisitors !== null && activePoint.predictedVisitors !== null ? 68 : 52} rx="8"/>
          <text x="12" y="18" className="tooltip-date">{activePoint.date}</text>
          {activePoint.actualVisitors !== null && <text x="12" y="38">真实值 <tspan>{activePoint.actualVisitors.toLocaleString()} 人</tspan></text>}
          {activePoint.predictedVisitors !== null && <text x="12" y={activePoint.actualVisitors !== null ? 56 : 38}>预测值 <tspan>{activePoint.predictedVisitors.toLocaleString()} 人</tspan></text>}
        </g>}
      </svg>
    </div>
  );
}

function semanticKey(feature: string) {
  if (feature.startsWith("visitors_")) return "history";
  if (feature.startsWith("weather_")) return "weather";
  if (/^(wiki_|wechat_|search_)/.test(feature)) return "attention";
  if (/^(capacity|daily_capacity|known_reserved|reservation|sold_out|official_notice)/.test(feature)) return "operation";
  if (/hsr|expressway|^transport_/.test(feature)) return "transport";
  if (/^(holiday_|year$|month$|weekday$|day_of_year$|week_of_year$|quarter$|sin_|cos_|is_weekend$|is_rest_day$|is_official_holiday$|is_.*vacation$|is_peak_season$|is_offseason$|days_to_next_holiday$)/.test(feature)) return "calendar";
  return null;
}

function fallbackGroups(items: FeatureImportanceItem[]): SemanticImportanceGroup[] {
  const totals: Record<string, number> = {};
  items.forEach(item => {
    const key = semanticKey(item.feature);
    if (key) totals[key] = (totals[key] ?? 0) + Math.max(0, item.importance);
  });
  const total = Object.values(totals).reduce((sum, value) => sum + value, 0) || 1;
  return Object.entries(totals)
    .map(([key, value]) => ({ ...GROUP_META[key], importance: Math.round(value / total * 1000) / 10 }))
    .sort((a, b) => b.importance - a.importance);
}

function MetricRow({ label, value, suffix, tone }: { label: string; value: string | number | null; suffix?: string; tone?: "up" | "down" | "neutral" }) {
  const toneClass = tone === "up" ? "metric-up" : tone === "down" ? "metric-down" : "";
  return <div className={`metric-row ${toneClass}`}><span className="metric-label">{label}</span><span className="metric-value">{value === null ? "—" : value}{suffix && value !== null ? ` ${suffix}` : ""}</span></div>;
}

function GaugeDial({ rate, label }: { rate: number | null; label: string }) {
  const safeRate = rate ?? 0;
  const clamped = Math.max(0, Math.min(100, safeRate));
  const radius = 42;
  const circumference = Math.PI * radius; // 半圆
  const offset = circumference * (1 - clamped / 100);
  const color = clamped >= 90 ? "#D85A30" : clamped >= 70 ? "#BA7517" : "#0F6E56";
  return (
    <div className="gauge-dial-wrap">
      <svg className="gauge-dial" viewBox="0 0 110 64" role="img" aria-label={`${label}: ${safeRate.toFixed(1)}%`}>
        <path d="M 13 58 A 42 42 0 0 1 97 58" fill="none" stroke="#e8eeea" strokeWidth="8" strokeLinecap="round"/>
        <path d="M 13 58 A 42 42 0 0 1 97 58" fill="none" stroke={color} strokeWidth="8" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset} style={{ transition: "stroke-dashoffset 1s ease-out" }}/>
      </svg>
      <div className="gauge-center">
        <strong style={{ color }}>{safeRate === 0 && rate === null ? "—" : `${safeRate.toFixed(1)}%`}</strong>
        <small>{label}</small>
      </div>
    </div>
  );
}

/** 预测准确率栏目（与承载/天气对齐的独立指标块） */
function CompactAccuracy({ mape, mae }: { mape: number | null; mae: number | null }) {
  const accuracy = mape == null ? null : Math.max(0, Math.min(100, 100 - mape));
  const radius = 46;
  const circumference = 2 * Math.PI * radius;
  const offset = accuracy == null ? circumference : circumference * (1 - accuracy / 100);
  return (
    <div className="indicator-block">
      <div className="block-head"><BlockIcon name="accuracy" /><h3>预测准确率</h3></div>
      <div className="accuracy-block">
        <svg viewBox="0 0 110 110" className="accuracy-block-ring" role="img" aria-label={`预测准确率 ${accuracy == null ? "未知" : accuracy.toFixed(1) + "%"}`}>
          <circle cx="55" cy="55" r={radius} className="ring-track"/>
          <circle cx="55" cy="55" r={radius} className="ring-progress" style={{ strokeDasharray: `${circumference}`, strokeDashoffset: offset }}/>
          <text x="55" y="58" textAnchor="middle" className="accuracy-block-value">{accuracy == null ? "—" : accuracy.toFixed(1)}</text>
          <text x="55" y="73" textAnchor="middle" className="accuracy-block-unit">%</text>
        </svg>
        <div className="accuracy-block-stats">
          <div className="metric-row"><span className="metric-label">平均绝对误差</span><span className="metric-value">{mae?.toLocaleString() ?? "—"} 人</span></div>
          <div className="metric-row"><span className="metric-label">平均百分比误差</span><span className="metric-value">{mape == null ? "—" : `${mape}%`}</span></div>
        </div>
      </div>
    </div>
  );
}

function IndicatorBlueprint({ indicators, mape, mae }: { indicators: Record<string, any> | null; mape: number | null; mae: number | null }) {
  if (!indicators || Object.keys(indicators).length === 0) {
    return <section className="card indicator-card" id="indicators"><div className="section-heading"><div><h2>指标蓝图</h2><p>上传数据后自动计算</p></div></div><div className="indicator-empty">暂无指标数据</div></section>;
  }

  const vt = indicators.visitorTrend;
  const cap = indicators.capacity;
  const hol = indicators.holidayEffect;
  const wx = indicators.weather;
  const tr = indicators.transport;
  const att = indicators.attention;
  const dq = indicators.dataQuality;

  return (
    <section className="card indicator-card" id="indicators">
      <div className="section-heading">
        <div><h2>指标蓝图</h2><p>基于上传数据自动计算，8 大模块独立可视化</p></div>
      </div>

      <div className="indicator-grid">
        {/* 模块 1：客流趋势 - 30日柱状趋势 + KPI 行 */}
        {vt && <div className="indicator-block">
          <div className="block-head"><BlockIcon name="trend" /><h3>客流趋势</h3></div>
          <div className="kpi-row">
            <div className="kpi"><span>最新客流</span><strong>{vt.latest?.toLocaleString()}<small>人</small></strong></div>
            <div className="kpi"><span>同比</span><strong className={vt.yoyChange >= 0 ? "kpi-up" : "kpi-down"}>{vt.yoyChange >= 0 ? "+" : ""}{vt.yoyChange}%</strong></div>
            <div className="kpi"><span>环比</span><strong className={vt.momChange >= 0 ? "kpi-up" : "kpi-down"}>{vt.momChange >= 0 ? "+" : ""}{vt.momChange}%</strong></div>
            <div className="kpi"><span>7日均值</span><strong>{vt.rollMean7?.toLocaleString()}</strong></div>
          </div>
          <MiniBarChart data={vt.recent30 || []} color="#316b51" height={110} label="近30日客流" />
        </div>}

        {/* 模块 2：承载与售罄 - 仪表盘 + 售罄/限流堆叠柱 */}
        {cap && <div className="indicator-block">
          <div className="block-head"><BlockIcon name="capacity" /><h3>承载与售罄</h3></div>
          <div className="gauge-flex">
            <GaugeDial rate={cap.latestLoadRate ?? cap.avgLoadRate} label="载客率" />
            <GaugeDial rate={cap.soldOutRate} label="售罄率" />
          </div>
          <CapacityBars soldOut={cap.soldOutDays || 0} restricted={cap.restrictedDays || 0} nearFull={cap.nearCapacityDays || 0} />
          <MetricRow label="平均载客率" value={cap.avgLoadRate} suffix="%" tone={cap.avgLoadRate >= 90 ? "up" : "neutral"} />
          <MetricRow label="限流天数" value={cap.restrictedDays} suffix="天" />
          <MetricRow label="近满载天数" value={cap.nearCapacityDays} suffix="天" />
        </div>}

        {/* 预测准确率 - 与承载/天气对齐 */}
        <CompactAccuracy mape={mape} mae={mae} />

        {/* 模块 3：节假日效应 - 季节饼图 + sparkline 网格 */}
        {hol && <div className="indicator-block indicator-block-wide">
          <div className="block-head"><BlockIcon name="holiday" /><h3>节假日效应</h3></div>
          <div className="holiday-layout">
            <SeasonPie peakSeasonAvg={hol.peakSeasonAvg} offSeasonAvg={hol.offSeasonAvg} summerAvg={hol.summerAvg} winterAvg={hol.winterAvg} />
            <div className="holiday-right">
              <div className="kpi-row">
                <div className="kpi"><span>节假日均值</span><strong>{hol.holidayAvg?.toLocaleString()}<small>人</small></strong></div>
                <div className="kpi"><span>平日均值</span><strong>{hol.weekdayAvg?.toLocaleString()}</strong></div>
                <div className="kpi"><span>节假日提升</span><strong className="kpi-up">+{hol.holidayLift}%</strong></div>
                <div className="kpi"><span>假期天数</span><strong>{hol.holidayDays}<small>天</small></strong></div>
              </div>
              {hol.holidayCurves && Object.keys(hol.holidayCurves).length > 0 && (
                <div className="holiday-sparklines">
                  {Object.entries(hol.holidayCurves).map(([name, curve]: [string, any]) => {
                    const max = Math.max(...curve);
                    return <div key={name} className="spark-cell">
                      <div className="spark-label">{name}<small>峰值 {max.toLocaleString()}</small></div>
                      <Sparkline data={curve} color="#534AB7" width={140} height={44} />
                    </div>;
                  })}
                </div>
              )}
            </div>
          </div>
        </div>}

        {/* 模块 4：天气影响 - 降水对比柱 + 温度计 */}
        {wx && <div className="indicator-block">
          <div className="block-head"><BlockIcon name="weather" /><h3>天气影响</h3></div>
          <div className="kpi-row">
            <div className="kpi"><span>雨天日均</span><strong>{wx.rainyDayAvgVisitors?.toLocaleString()}</strong></div>
            <div className="kpi"><span>晴天日均</span><strong>{wx.dryDayAvgVisitors?.toLocaleString()}</strong></div>
            <div className="kpi"><span>降水影响</span><strong className={wx.rainImpactRate >= 0 ? "kpi-up" : "kpi-down"}>{wx.rainImpactRate >= 0 ? "+" : ""}{wx.rainImpactRate}%</strong></div>
            <div className="kpi"><span>均温</span><strong>{wx.avgTemp}°C</strong></div>
          </div>
          <RainDryBars rainyAvg={wx.rainyDayAvgVisitors} dryAvg={wx.dryDayAvgVisitors} rainyDays={wx.rainyDays || 0} dryDays={(dq?.totalRows || 2377) - (wx.rainyDays || 0)} />
          <WeatherTempBar avg={wx.avgTemp} min={wx.minTemp} max={wx.maxTemp} />
        </div>}

        {/* 模块 5：交通基建 - 前后对比柱状 + 提升率 */}
        {tr && <div className="indicator-block">
          <div className="block-head"><BlockIcon name="transport" /><h3>交通基建</h3></div>
          <CompareBar label="高铁开通" before={tr.hsrClosedAvgVisitors} after={tr.hsrOpenAvgVisitors} lift={tr.hsrLiftRate} />
          <CompareBar label="高速开通" before={tr.expClosedAvgVisitors} after={tr.expOpenAvgVisitors} lift={tr.expLiftRate} />
          <div className="transport-stats">
            <div className="kpi"><span>高铁累计</span><strong>{tr.hsrOpenDays}<small>天</small></strong></div>
            <div className="kpi"><span>高速累计</span><strong>{tr.expOpenDays}<small>天</small></strong></div>
          </div>
        </div>}

        {/* 模块 6：网络热度 - 相关性仪表 + 面积折线 */}
        {att && <div className="indicator-block">
          <div className="block-head"><BlockIcon name="attention" /><h3>网络热度</h3></div>
          <div className="correlation-dial">
            <svg viewBox="0 0 120 70" className="corr-svg">
              <path d="M 12 58 A 48 48 0 0 1 108 58" fill="none" stroke="#e8eeea" strokeWidth="8" strokeLinecap="round"/>
              <path d="M 12 58 A 48 48 0 0 1 108 58" fill="none" stroke={att.correlationWithVisitors >= 0.3 ? "#0F6E56" : "#888780"} strokeWidth="8" strokeLinecap="round" strokeDasharray={Math.PI * 48} strokeDashoffset={Math.PI * 48 * (1 - Math.abs(att.correlationWithVisitors || 0))}/>
            </svg>
            <div className="corr-center"><strong>{att.correlationWithVisitors?.toFixed(2) ?? "—"}</strong><small>相关系数</small></div>
          </div>
          <div className="kpi-row">
            <div className="kpi"><span>中文维基</span><strong>{att.wikiZhLatest}</strong></div>
            <div className="kpi"><span>英文维基</span><strong>{att.wikiEnLatest}</strong></div>
            <div className="kpi"><span>微信指数</span><strong>{att.wechatLatest?.toLocaleString()}</strong></div>
          </div>
          <AttentionArea wikiZh={att.wikiZhAvg || 0} wikiEn={att.wikiEnAvg || 0} wechat={Math.min(att.wechatLatest || 0, 500000)} />
        </div>}

        {/* 模块 7：数据质量 - 堆叠分布 + 进度条 */}
        {dq && <div className="indicator-block">
          <div className="block-head"><BlockIcon name="quality" /><h3>数据质量</h3></div>
          <QualityStack cappedDays={dq.cappedDays || 0} outliers={dq.spikeOutliers || 0} missingDates={dq.missingDates || 0} total={dq.totalRows || 0} />
          <div className="quality-kpi">
            <div className="kpi"><span>总行数</span><strong>{dq.totalRows?.toLocaleString()}</strong></div>
            <div className="kpi"><span>日期跨度</span><strong style={{ fontSize: "10px" }}>{dq.dateStart?.slice(2, 10)} ~ {dq.dateEnd?.slice(2, 10)}</strong></div>
          </div>
        </div>}
      </div>
    </section>
  );
}

/** 模块图标（12×12 线性 SVG，随主题色） */
function BlockIcon({ name }: { name: "trend" | "capacity" | "holiday" | "weather" | "transport" | "attention" | "quality" | "accuracy" }) {
  const paths: Record<string, ReactNode> = {
    trend: <><path d="M3 17l5-5 4 3 6-8"/><path d="M14 7h4v4"/></>,
    capacity: <><rect x="4" y="10" width="16" height="9" rx="2"/><path d="M8 10V7a4 4 0 018 0v3"/></>,
    holiday: <><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/></>,
    weather: <><circle cx="9" cy="10" r="3.5"/><path d="M9 6.5v-1M9 14.5v-1M5.5 10h-1M13.5 10h-1M6.7 7.2l-.7-.7M12 12.5l-.7-.7M6.7 12.8l-.7.7M12 7.5l-.7.7"/><path d="M15 18h5M17.5 15v6"/></>,
    transport: <><rect x="5" y="3" width="14" height="13" rx="2"/><path d="M5 11h14M9 16v3M15 16v3"/><circle cx="9" cy="14" r="0.5"/><circle cx="15" cy="14" r="0.5"/></>,
    attention: <><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1"/></>,
    quality: <><path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z"/><path d="M9 12l2 2 4-4"/></>,
    accuracy: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3"/></>,
  };
  return <span className="block-icon" aria-hidden="true"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg></span>;
}

/** 季节占比环形饼图 */
function SeasonPie({ peakSeasonAvg, offSeasonAvg, summerAvg, winterAvg }: { peakSeasonAvg: number; offSeasonAvg: number; summerAvg: number; winterAvg: number }) {
  const items = [
    { label: "旺季", value: peakSeasonAvg, color: "#0F6E56" },
    { label: "淡季", value: offSeasonAvg, color: "#91ae9b" },
    { label: "暑假", value: summerAvg, color: "#BA7517" },
    { label: "寒假", value: winterAvg, color: "#378ADD" },
  ].filter(item => item.value > 0);
  const total = items.reduce((sum, item) => sum + item.value, 0) || 1;
  let acc = 0;
  const radius = 40, cx = 50, cy = 50, innerR = 24;
  const arcs = items.map(item => {
    const startAngle = (acc / total) * 2 * Math.PI - Math.PI / 2;
    acc += item.value;
    const endAngle = (acc / total) * 2 * Math.PI - Math.PI / 2;
    const largeArc = endAngle - startAngle > Math.PI ? 1 : 0;
    const x1 = cx + radius * Math.cos(startAngle), y1 = cy + radius * Math.sin(startAngle);
    const x2 = cx + radius * Math.cos(endAngle), y2 = cy + radius * Math.sin(endAngle);
    const x3 = cx + innerR * Math.cos(endAngle), y3 = cy + innerR * Math.sin(endAngle);
    const x4 = cx + innerR * Math.cos(startAngle), y4 = cy + innerR * Math.sin(startAngle);
    const d = `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} L ${x3} ${y3} A ${innerR} ${innerR} 0 ${largeArc} 0 ${x4} ${y4} Z`;
    const pct = (item.value / total) * 100;
    return { ...item, d, pct };
  });
  return <div className="season-pie-wrap">
    <svg viewBox="0 0 100 100" className="season-pie" role="img" aria-label="季节客流占比">
      {arcs.map(arc => <path key={arc.label} d={arc.d} fill={arc.color} opacity="0.88"><title>{arc.label} {arc.pct.toFixed(0)}%（日均 {arc.value.toLocaleString()} 人）</title></path>)}
    </svg>
    <div className="pie-legend">
      {arcs.map(arc => <span key={arc.label}><i style={{ background: arc.color }}/>{arc.label} {arc.pct.toFixed(0)}%</span>)}
    </div>
  </div>;
}

/** 雨天/晴天对比柱（垂直双柱） */
function RainDryBars({ rainyAvg, dryAvg, rainyDays, dryDays }: { rainyAvg: number; dryAvg: number; rainyDays: number; dryDays: number }) {
  const max = Math.max(rainyAvg || 0, dryAvg || 0, 1);
  const barH = 80;
  return <div className="rain-dry-chart">
    <div className="rd-col">
      <div className="rd-bar-wrap" style={{ height: barH }}>
        <span className="rd-bar rd-rain" style={{ height: `${((rainyAvg || 0) / max) * 100}%` }} title={`雨天日均 ${rainyAvg?.toLocaleString()} 人`}/>
      </div>
      <small className="rd-val">{rainyAvg?.toLocaleString()}</small>
      <small className="rd-label">雨天 {rainny_days_label(rainyDays)}</small>
    </div>
    <div className="rd-col">
      <div className="rd-bar-wrap" style={{ height: barH }}>
        <span className="rd-bar rd-dry" style={{ height: `${((dryAvg || 0) / max) * 100}%` }} title={`晴天日均 ${dryAvg?.toLocaleString()} 人`}/>
      </div>
      <small className="rd-val">{dryAvg?.toLocaleString()}</small>
      <small className="rd-label">晴天 {rainny_days_label(dryDays)}</small>
    </div>
  </div>;
}
function rainny_days_label(days: number) { return `${days}天`; }

/** 网络热度面积折线图 */
function AttentionArea({ wikiZh, wikiEn, wechat }: { wikiZh: number; wikiEn: number; wechat: number }) {
  const data = [
    { label: "中文维基", value: wikiZh, color: "#0F6E56" },
    { label: "英文维基", value: wikiEn, color: "#378ADD" },
    { label: "微信指数", value: wechat, color: "#534AB7" },
  ].filter(d => d.value > 0);
  const max = Math.max(...data.map(d => d.value), 1);
  const width = 200, height = 56;
  const stepX = data.length > 1 ? width / (data.length - 1) : width / 2;
  const points = data.map((d, i) => `${i * stepX + 10},${height - (d.value / max) * (height - 10) - 4}`);
  const areaPath = `M ${points[0]?.split(",")[0] ?? 10},${height} L ${points.join(" L ")} L ${width - 10},${height} Z`;
  return <div className="attention-area-wrap">
    <svg viewBox={`0 0 ${width} ${height}`} className="attention-area" preserveAspectRatio="none" role="img" aria-label="网络热度渠道对比">
      <path d={areaPath} fill="#316b51" opacity="0.12"/>
      <polyline points={points.join(" ")} fill="none" stroke="#316b51" strokeWidth="1.5" strokeLinejoin="round"/>
      {data.map((d, i) => <circle key={d.label} cx={i * stepX + 10} cy={height - (d.value / max) * (height - 10) - 4} r="2.5" fill={d.color}><title>{d.label}：{d.value.toLocaleString()}</title></circle>)}
    </svg>
    <div className="area-legend">
      {data.map(d => <span key={d.label}><i style={{ background: d.color }}/>{d.label}</span>)}
    </div>
  </div>;
}

// 通用：柱状条
function Bar({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return <div className="bar-row"><span className="bar-label">{label}</span><div className="bar-track"><span style={{ width: `${pct}%` }}/></div><b>{value.toLocaleString()}</b></div>;
}

// 30日客流迷你柱状图（支持悬停 tooltip）
function MiniBarChart({ data, color, height, label }: { data: number[]; color: string; height: number; label: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(...data, 1);
  const width = 320;
  const barW = data.length > 0 ? (width - 4) / data.length - 2 : 0;
  return <div className="mini-chart-wrap" style={{ height: height + 24 }}>
    <svg viewBox={`0 0 ${width} ${height + 8}`} className="mini-bar-chart" preserveAspectRatio="none" onMouseLeave={() => setHover(null)}>
      {data.map((v, i) => {
        const h = (v / max) * height;
        const x = i * (barW + 2) + 2;
        const y = height - h + 4;
        const isHover = hover === i;
        return <rect key={i} x={x} y={y} width={barW} height={h} rx="1.5" fill={color} opacity={hover === null || isHover ? 0.85 : 0.4} onMouseEnter={() => setHover(i)} style={{ transition: "opacity .15s ease" }}/>;
      })}
      {hover !== null && <line x1={hover * (barW + 2) + barW / 2 + 2} x2={hover * (barW + 2) + barW / 2 + 2} y1={4} y2={height + 4} stroke="#35463c" strokeWidth="0.5" strokeDasharray="2 2"/>}
    </svg>
    {hover !== null && <div className="mini-tooltip">近{data.length - hover}天前 · {data[hover].toLocaleString()} 人</div>}
    <small className="mini-label">{label}</small>
  </div>;
}

// 假期 sparkline 折线
function Sparkline({ data, color, width, height }: { data: number[]; color: string; width: number; height: number }) {
  const max = Math.max(...data, 1);
  const stepX = data.length > 1 ? width / (data.length - 1) : width;
  const points = data.map((v, i) => `${i * stepX},${height - (v / max) * (height - 4) - 2}`).join(" ");
  return <svg viewBox={`0 0 ${width} ${height}`} className="sparkline-svg" preserveAspectRatio="none">
    <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    {data.map((v, i) => <circle key={i} cx={i * stepX} cy={height - (v / max) * (height - 4) - 2} r="1.5" fill={color}/>)}
  </svg>;
}

// 售罄/限流堆叠柱
function CapacityBars({ soldOut, restricted, nearFull }: { soldOut: number; restricted: number; nearFull: number }) {
  const total = soldOut + restricted + nearFull;
  if (total === 0) return null;
  const soldPct = (soldOut / total) * 100;
  const restPct = (restricted / total) * 100;
  const nearPct = (nearFull / total) * 100;
  return <div className="capacity-stack">
    <div className="stack-bar">
      <span className="seg-sold" style={{ width: `${soldPct}%` }} title={`售罄 ${soldOut}天`}/>
      <span className="seg-rest" style={{ width: `${restPct}%` }} title={`限流 ${restricted}天`}/>
      <span className="seg-near" style={{ width: `${nearPct}%` }} title={`近满载 ${nearFull}天`}/>
    </div>
    <div className="stack-legend">
      <span><i className="seg-sold"/>售罄 {soldOut}天</span>
      <span><i className="seg-rest"/>限流 {restricted}天</span>
      <span><i className="seg-near"/>近满载 {nearFull}天</span>
    </div>
  </div>;
}

// 温度范围条
function WeatherTempBar({ avg, min, max }: { avg: number; min: number; max: number }) {
  const range = max - min || 1;
  const avgPct = ((avg - min) / range) * 100;
  return <div className="temp-bar-wrap">
    <div className="temp-bar">
      <div className="temp-range" style={{ left: "0%", width: "100%" }}/>
      <div className="temp-avg" style={{ left: `${avgPct}%` }}/>
    </div>
    <div className="temp-legend"><span>{min}°C</span><span>均温 {avg}°C</span><span>{max}°C</span></div>
  </div>;
}

// 交通前后对比柱
function CompareBar({ label, before, after, lift }: { label: string; before: number; after: number; lift: number }) {
  const max = Math.max(before, after, 1);
  return <div className="compare-block">
    <div className="compare-label"><span>{label}</span><b className={lift >= 0 ? "kpi-up" : "kpi-down"}>{lift >= 0 ? "+" : ""}{lift}%</b></div>
    <div className="compare-bars">
      <div className="cmp-row"><small>开通前</small><div className="cmp-track"><span style={{ width: `${(before / max) * 100}%` }} className="cmp-before"/></div><b>{before?.toLocaleString()}</b></div>
      <div className="cmp-row"><small>开通后</small><div className="cmp-track"><span style={{ width: `${(after / max) * 100}%` }} className="cmp-after"/></div><b>{after?.toLocaleString()}</b></div>
    </div>
  </div>;
}

// 数据质量堆叠分布
function QualityStack({ cappedDays, outliers, missingDates, total }: { cappedDays: number; outliers: number; missingDates: number; total: number }) {
  const totalRows = Math.max(total, 1);
  const cappedPct = Math.min(100, (cappedDays / totalRows) * 100);
  const outliersPct = Math.min(100, (outliers / totalRows) * 100);
  return <div className="quality-stack">
    <div className="qual-row"><span>封顶天数</span><div className="qual-track"><span style={{ width: `${cappedPct * 4}%`, background: "#D85A30" }}/></div><b>{cappedDays}天</b></div>
    <div className="qual-row"><span>异常尖峰</span><div className="qual-track"><span style={{ width: `${outliersPct * 10}%`, background: "#BA7517" }}/></div><b>{outliers}个</b></div>
    <div className="qual-row"><span>缺失日期</span><div className="qual-track"><span style={{ width: `${Math.min(100, missingDates * 0.7)}%`, background: "#A32D2D" }}/></div><b>{missingDates}天</b></div>
  </div>;
}

/** 各业务主题的简要分析模板（页面概览层） */
const GROUP_INSIGHT: Record<string, (pct: number) => string> = {
  history: pct => `历史客流是模型最主要的预测依据（${pct.toFixed(1)}%）。近期走势与周期规律对次日预测影响最大，建议重点关注 7 日滚动趋势的拐点信号。`,
  calendar: pct => `节假日与季节因素贡献 ${pct.toFixed(1)}%。假期效应显著（数据显示节假日客流较平日提升明显），节前预留运力与票务额度是关键动作。`,
  weather: pct => `天气条件贡献 ${pct.toFixed(1)}%。降水与恶劣天气对客流有直接抑制，建议将天气预报纳入短期排班与分流预案。`,
  attention: pct => `网络关注度贡献 ${pct.toFixed(1)}%。搜索与百科热度对客流有领先指示作用，可作为营销效果与舆情监测的代理指标。`,
  operation: pct => `预约与运营因素贡献 ${pct.toFixed(1)}%。售罄与限流标记反映真实需求被截断，承载上限附近的预测应视为保守估计。`,
  transport: pct => `交通可达性贡献 ${pct.toFixed(1)}%。高铁与高速开通显著抬升客流基数，交通事件日历值得纳入中长期预测校准。`,
};

/** 各业务主题的语义色（与指标蓝图图表色一致） */
const GROUP_COLORS: Record<string, string> = {
  history: "#0F6E56", calendar: "#534AB7", weather: "#378ADD",
  attention: "#BA7517", operation: "#D85A30", transport: "#1D9E75",
};

function FeatureContribution({ importance, onAskAgent }: { importance: ImportancePayload | null; onAskAgent?: (question: string) => void }) {
  const groups = importance?.semantic_groups?.length
    ? importance.semantic_groups
    : fallbackGroups(importance?.feature_importance ?? []);
  const total = groups.reduce((sum, g) => sum + g.importance, 0) || 1;
  return (
    <section className="card contribution-card" id="contribution">
      <div className="section-heading">
        <div><h2>经营分析 · 客流影响因素</h2><p>页面为简要概览，点击「问 Agent」获取该因素的深度分析报告</p></div>
        <span className="explain-badge">模型贡献</span>
      </div>
      {!importance ? <div className="contribution-loading"><span/><span/><span/></div> : groups.length === 0 ? <p className="contribution-empty">本次分析没有足够的可解释贡献数据。</p> : (
        <ol className="contribution-list">
          {groups.slice(0, 6).map(group => {
            const color = GROUP_COLORS[group.key] ?? "#316b51";
            const insight = GROUP_INSIGHT[group.key]?.(group.importance);
            const question = `请深入分析「${group.label}」对客流的影响：贡献度 ${group.importance.toFixed(1)}%，结合历史数据、节假日效应与运营建议，输出可执行的经营分析报告。`;
            return <li key={group.key} style={{ "--theme": color, "--pct": `${Math.max(group.importance / total * 100, 2)}%` } as React.CSSProperties}>
              <div className="contribution-head">
                <span className="contribution-dot" />
                <div className="contribution-label"><div><strong>{group.label}</strong><small>{group.description}</small></div><b>{group.importance.toFixed(1)}%</b></div>
              </div>
              <div className="contribution-track" aria-hidden="true"><span style={{ width: `${Math.max(group.importance, 2)}%`, background: color }}/></div>
              {insight && <p className="contribution-insight">{insight}</p>}
              {onAskAgent && <button type="button" className="ask-agent-btn" onClick={() => onAskAgent(question)}>问 Agent 深入分析 →</button>}
            </li>;
          })}
        </ol>
      )}
      <p className="contribution-note">贡献度表示模型对各类信息的依赖程度，不等同于因果关系。Agent 报告将结合指标蓝图数据做交叉验证。</p>
    </section>
  );
}

function AccuracyRing({ mape, mae, validationDays }: { mape: number | null; mae: number | null; validationDays: number }) {
  const accuracy = mape == null ? null : Math.max(0, Math.min(100, 100 - mape));
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const offset = accuracy == null ? circumference : circumference * (1 - accuracy / 100);
  return (
    <section className="card accuracy-card">
      <div className="section-heading compact"><div><h2>预测准确率</h2><p>回测期内预测客流与实际客流的吻合度</p></div></div>
      <div className="ring-wrap">
        <svg className="accuracy-ring" viewBox="0 0 130 130" role="img" aria-label={`预测准确率 ${accuracy == null ? "未知" : accuracy.toFixed(1) + "%"}`}>
          <circle cx="65" cy="65" r={radius} className="ring-track"/>
          <circle cx="65" cy="65" r={radius} className="ring-progress" style={{ strokeDasharray: `${circumference}`, strokeDashoffset: offset }}/>
          <text x="65" y="62" textAnchor="middle" className="ring-value">{accuracy == null ? "—" : accuracy.toFixed(1)}</text>
          <text x="65" y="78" textAnchor="middle" className="ring-unit">%</text>
        </svg>
        <dl className="ring-stats">
          <div><dt>回测样本</dt><dd>{validationDays} 天</dd></div>
          <div><dt>平均绝对误差</dt><dd>{mae?.toLocaleString() ?? "—"} 人</dd></div>
          <div><dt>平均百分比误差</dt><dd>{mape == null ? "—" : `${mape}%`}</dd></div>
        </dl>
      </div>
    </section>
  );
}

/** 今日入园进度：已入园人数与预计入园人数的比值（真实数据） */
function AdmissionProgress({ result }: { result: AnalysisResult }) {
  const latest = result.latestActual;
  const next = result.forecastPoints[0];
  const expected = next?.predictedVisitors;
  const ratio = latest.visitors > 0 && expected && expected > 0
    ? Math.max(0, Math.min(100, (latest.visitors / expected) * 100))
    : null;
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const offset = ratio == null ? circumference : circumference * (1 - ratio / 100);
  return (
    <section className="card admission-card">
      <div className="section-heading compact"><div><h2>今日入园进度</h2><p>已入园人数与预计入园人数的比值</p></div></div>
      <div className="ring-wrap">
        <svg className="accuracy-ring" viewBox="0 0 130 130" role="img" aria-label={`今日入园进度 ${ratio == null ? "未知" : ratio.toFixed(1) + "%"}`}>
          <circle cx="65" cy="65" r={radius} className="ring-track"/>
          <circle cx="65" cy="65" r={radius} className="ring-progress" style={{ strokeDasharray: `${circumference}`, strokeDashoffset: offset }}/>
          <text x="65" y="62" textAnchor="middle" className="ring-value">{ratio == null ? "—" : ratio.toFixed(1)}</text>
          <text x="65" y="78" textAnchor="middle" className="ring-unit">%</text>
        </svg>
        <dl className="ring-stats">
          <div><dt>已入园</dt><dd>{latest.visitors.toLocaleString()} 人</dd></div>
          <div><dt>预计入园</dt><dd>{expected?.toLocaleString() ?? "—"} 人</dd></div>
          <div><dt>达成进度</dt><dd>{ratio == null ? "—" : `${ratio.toFixed(1)}%`}</dd></div>
        </dl>
      </div>
    </section>
  );
}

type ChatMessage = { role: "user" | "agent"; text: string; time: string };

function AgentChat({ analysisId, pendingQuestion, onQuestionConsumed }: { analysisId: string; pendingQuestion?: string | null; onQuestionConsumed?: () => void }) {
  const [open, setOpen] = useState(true);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "agent", text: "你好，我是智景分析助手。可以针对本次客流预测结果向你解答疑问，例如「下周哪天客流最高」「天气对预测有多大影响」。", time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const pendingRef = useRef<string | null>(null);

  async function reply(text: string) {
    const now = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    setMessages(prev => [...prev, { role: "user", text, time: now }]);
    setSending(true);
    try {
      const { answer } = await agentChat(analysisId, text);
      setMessages(prev => [...prev, { role: "agent", text: answer, time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) }]);
    } catch (reason) {
      setMessages(prev => [...prev, { role: "agent", text: reason instanceof Error ? reason.message : "Agent 暂时无法回答，请稍后重试。", time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) }]);
    } finally {
      setSending(false);
    }
  }

  function send() {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    reply(text);
  }

  if (pendingQuestion && pendingQuestion !== pendingRef.current) {
    pendingRef.current = pendingQuestion;
    setOpen(true);
    if (!sending) setTimeout(() => reply(pendingQuestion), 50);
    onQuestionConsumed?.();
  }

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages]);

  if (!open) {
    return (
      <button className="chat-fab" onClick={() => setOpen(true)} aria-label="展开智景助手">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
        </svg>
        <span className="chat-fab-badge">Agent</span>
      </button>
    );
  }

  return (
    <div className="chat-float">
      <div className="chat-float-header">
        <div className="chat-float-title"><span className="agent-badge">Agent</span><strong>智景助手</strong></div>
        <button className="chat-float-close" onClick={() => setOpen(false)} aria-label="收起">×</button>
      </div>
      <div className="chat-messages" ref={listRef}>
        {messages.map((msg, i) => <div key={i} className={`chat-msg chat-${msg.role}`}>
          <div className="chat-bubble"><p>{msg.text}</p></div>
          <small className="chat-time">{msg.time}</small>
        </div>)}
      </div>
      <div className="chat-input-row">
        <input
          type="text"
          className="chat-input"
          placeholder="输入问题，回车发送…"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); send(); } }}
          disabled={sending}
        />
        <button type="button" className="chat-send" onClick={send} disabled={sending || !input.trim()}>{sending ? "…" : "发送"}</button>
      </div>
    </div>
  );
}

const STAGE_LABELS: Record<string, string> = {
  coordinator: "任务编排", collector: "数据采集", analyst: "交叉分析",
  writer: "报告撰写", reviewer: "质量审核", llm: "AI 服务",
};
const TYPE_LABELS: Record<string, string> = { daily_brief: "每日简报", deep_dive: "深度分析", periodic: "周期报告" };

/** 轻量 Markdown → HTML（标题/加粗/列表/引用/段落，够用即可） */
function renderMarkdown(md: string): string {
  const escape = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return md.split("\n").map(line => {
    if (line.startsWith("# ")) return `<h1>${escape(line.slice(2))}</h1>`;
    if (line.startsWith("## ")) return `<h2>${escape(line.slice(3))}</h2>`;
    if (line.startsWith("### ")) return `<h3>${escape(line.slice(4))}</h3>`;
    if (line.startsWith("> ")) return `<blockquote>${escape(line.slice(2))}</blockquote>`;
    if (/^[-*] /.test(line)) return `<li>${inline(line.slice(2))}</li>`;
    if (!line.trim()) return "";
    return `<p>${inline(line)}</p>`;
  }).join("").replace(/(<li>.*?<\/li>)(?!<li>)/g, "<ul>$1</ul>");

  function inline(s: string): string {
    return escape(s)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`(.+?)`/g, "<code>$1</code>");
  }
}

function AgentReportView({ analysisId, result, importance }: { analysisId: string; result: AnalysisResult | null; importance: ImportancePayload | null }) {
  const [reports, setReports] = useState<any[]>([]);
  const [active, setActive] = useState<any | null>(null);
  const [generating, setGenerating] = useState(false);
  const [reportType, setReportType] = useState("daily_brief");
  const [period, setPeriod] = useState("7");
  const [question, setQuestion] = useState("");
  const [error, setError] = useState("");

  async function refresh() {
    try {
      const list = await getAgentReports();
      setReports(list);
      if (!active && list.length > 0) {
        const detail = await getAgentReport(list[0].reportId);
        setActive(detail);
      }
    } catch { /* 忽略 */ }
  }

  useEffect(() => { refresh(); }, [analysisId]);

  // 生成中轮询
  useEffect(() => {
    if (!generating || !active) return;
    const timer = setInterval(async () => {
      try {
        const detail = await getAgentReport(active.reportId);
        setActive(detail);
        setReports(prev => prev.map(r => r.reportId === detail.reportId ? detail : r));
        if (detail.status === "done" || detail.status === "failed") {
          setGenerating(false);
          clearInterval(timer);
        }
      } catch { /* 继续 */ }
    }, 2500);
    return () => clearInterval(timer);
  }, [generating, active?.reportId]);

  async function generate() {
    setError("");
    setGenerating(true);
    try {
      const q = reportType === "deep_dive" ? question.trim() || undefined : undefined;
      const p = reportType === "periodic" ? period : undefined;
      const created = await createAgentReport(analysisId, reportType, q, p);
      const detail = await getAgentReport(created.reportId);
      setActive(detail);
      setReports(prev => [detail, ...prev]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "生成失败");
      setGenerating(false);
    }
  }

  async function openReport(id: string) {
    try { setActive(await getAgentReport(id)); } catch { /* 忽略 */ }
  }

  async function downloadPdf() {
    if (!active?.reportId) return;
    try {
      const token = window.localStorage.getItem("scenicmind.accessToken") ?? "";
      const res = await fetch(`/api/v1/agent/report/${active.reportId}/pdf`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`下载失败 (${res.status})`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `经营分析报告_${active.reportId.slice(0, 8)}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "PDF 下载失败");
    }
  }

  return (
    <div className="report-layout">
      <section className="report-main">
        {!active ? <div className="report-empty-main">选择或生成一份报告</div> : active.status !== "done" ? (
          <div className="report-progress">
            <h3>Agent 协作中…</h3>
            <div className="progress-stages">
              {Object.entries(STAGE_LABELS).map(([key, label]) => {
                const stageState = active.progress?.stage === key
                  ? active.progress?.status : null;
                const passed = STAGE_ORDER.indexOf(key) < STAGE_ORDER.indexOf(active.progress?.stage ?? "coordinator");
                return <div key={key} className={`stage ${stageState ? `stage-${stageState}` : passed ? "stage-done" : ""}`}>
                  <i/><span>{label}</span>
                  {stageState === "running" && <small>进行中</small>}
                  {stageState === "done" && <small>完成</small>}
                </div>;
              })}
            </div>
            {active.progress?.detail && <p className="progress-detail">{active.progress.detail}</p>}
            {active.status === "failed" && <p className="report-error">{active.markdown}</p>}
          </div>
        ) : (
          <div className="report-doc-wrap">
            <div className="report-toolbar">
              <span className="report-toolbar-title">{TYPE_LABELS[active.reportType] ?? active.reportType}</span>
              <div className="report-toolbar-actions">
                <button type="button" className="report-download-btn" onClick={downloadPdf}>下载 PDF</button>
              </div>
            </div>
            <ReportSummary result={result} importance={importance} />
            <article className="report-doc" dangerouslySetInnerHTML={{ __html: renderMarkdown(active.markdown || "") }} />
          </div>
        )}
      </section>

      <aside className="report-side">
        <div className="report-gen-panel">
          <h3>生成新报告</h3>
          <div className="report-type-tabs">
            {Object.entries(TYPE_LABELS).map(([key, label]) => (
              <button key={key} type="button" className={reportType === key ? "active" : ""} onClick={() => setReportType(key)}>{label}</button>
            ))}
          </div>
          {reportType === "deep_dive" && (
            <input type="text" className="report-question" placeholder="深度分析主题，如：节假日效应" value={question} onChange={e => setQuestion(e.target.value)} />
          )}
          {reportType === "periodic" && (
            <div className="report-period-tabs">
              {["7", "14", "30"].map(d => (
                <button key={d} type="button" className={period === d ? "active" : ""} onClick={() => setPeriod(d)}>{d} 天</button>
              ))}
            </div>
          )}
          <button type="button" className="report-gen-btn" onClick={generate} disabled={generating}>
            {generating ? "生成中…" : "生成报告"}
          </button>
          {error && <p className="report-error">{error}</p>}
        </div>
        <div className="report-list">
          <h3>历史报告</h3>
          {reports.length === 0 && <p className="report-empty">暂无报告，先生成一份</p>}
          {reports.map(r => (
            <button key={r.reportId} type="button" className={`report-item ${active?.reportId === r.reportId ? "active" : ""}`} onClick={() => openReport(r.reportId)}>
              <span className="report-item-type">{TYPE_LABELS[r.reportType] ?? r.reportType}{r.period ? ` · ${r.period}天` : ""}</span>
              <small>{r.question || new Date(r.createdAt).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}</small>
              <span className={`report-status st-${r.status}`}>{r.status === "done" ? "完成" : r.status === "running" ? "生成中" : r.status === "failed" ? "失败" : r.status}</span>
            </button>
          ))}
        </div>
        <ReportChat analysisId={analysisId} reportTitle={active?.status === "done" ? TYPE_LABELS[active.reportType] ?? active.reportType : undefined} />
      </aside>
    </div>
  );
}

/** 报告问答区：针对报告内容发起提问（参考智景助手交互） */
function ReportChat({ analysisId, reportTitle }: { analysisId: string; reportTitle?: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  async function send() {
    const text = input.trim();
    if (!text || sending) return;
    const now = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    setMessages(prev => [...prev, { role: "user", text, time: now }]);
    setInput("");
    setSending(true);
    const q = reportTitle ? `针对「${reportTitle}」报告，${text}` : text;
    try {
      const { answer } = await agentChat(analysisId, q);
      setMessages(prev => [...prev, { role: "agent", text: answer, time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) }]);
    } catch (reason) {
      setMessages(prev => [...prev, { role: "agent", text: reason instanceof Error ? reason.message : "暂时无法回答，请稍后重试。", time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="report-chat">
      <h3>报告问答{reportTitle ? <small> · {reportTitle}</small> : ""}</h3>
      <div className="report-chat-messages">
        {messages.length === 0 && <p className="report-chat-hint">针对这份报告提问，例如「报告里的高峰日是哪天？」</p>}
        {messages.map((msg, i) => <div key={i} className={`chat-msg chat-${msg.role}`}>
          <div className="chat-bubble"><p>{msg.text}</p></div>
          <small className="chat-time">{msg.time}</small>
        </div>)}
      </div>
      <div className="chat-input-row">
        <input
          type="text" className="chat-input" placeholder="针对报告内容提问…"
          value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); send(); } }}
          disabled={sending}
        />
        <button type="button" className="chat-send" onClick={send} disabled={sending || !input.trim()}>{sending ? "…" : "发送"}</button>
      </div>
    </div>
  );
}

/** 报告摘要区：KPI 卡 + 预测趋势图 + 特征贡献占比（图文表结合） */
function ReportSummary({ result, importance }: { result: AnalysisResult | null; importance: ImportancePayload | null }) {
  if (!result) return null;
  const next = result.forecastPoints[0];
  const h7 = result.horizons["7"];
  const groups = importance?.semantic_groups ?? [];
  const total = groups.reduce((s, g) => s + g.importance, 0) || 1;

  const width = 640, height = 150, pad = { t: 16, r: 16, b: 24, l: 40 };
  const pts = result.forecastPoints.slice(0, 14);
  const values = pts.map(p => p.predictedVisitors ?? 0);
  const max = Math.ceil(Math.max(...values, 1) * 1.1 / 1000) * 1000;
  const x = (i: number) => pad.l + i * ((width - pad.l - pad.r) / Math.max(pts.length - 1, 1));
  const y = (v: number) => height - pad.b - (v / max) * (height - pad.t - pad.b);
  const linePath = pts.map((p, i) => `${i ? "L" : "M"} ${x(i)} ${y(p.predictedVisitors ?? 0)}`).join(" ");
  const areaPath = `M ${x(0)} ${height - pad.b} ${linePath.slice(1)} L ${x(pts.length - 1)} ${height - pad.b} Z`;

  return (
    <div className="report-summary">
      <div className="summary-kpis">
        <div className="summary-kpi"><span>最新真实客流</span><strong>{result.latestActual.visitors.toLocaleString()}<small>人</small></strong></div>
        <div className="summary-kpi"><span>下一日预测</span><strong>{next?.predictedVisitors?.toLocaleString() ?? "—"}<small>人</small></strong></div>
        <div className="summary-kpi"><span>未来 7 天日均</span><strong>{h7?.average.toLocaleString() ?? "—"}<small>人</small></strong></div>
        <div className="summary-kpi"><span>预测准确率</span><strong>{result.metrics.mape != null ? (100 - result.metrics.mape).toFixed(1) : "—"}<small>%</small></strong></div>
      </div>
      <div className="summary-body">
        <div className="summary-chart">
          <div className="summary-chart-title">未来 14 日客流预测</div>
          <svg viewBox={`0 0 ${width} ${height}`} className="summary-svg" preserveAspectRatio="none" role="img" aria-label="未来14日客流预测趋势">
            {[0, .5, 1].map(r => <line key={r} x1={pad.l} x2={width - pad.r} y1={y(max * r)} y2={y(max * r)} stroke="#e5ebe7" strokeWidth="0.5"/>)}
            <path d={areaPath} fill="#316b51" opacity="0.12"/>
            <path d={linePath} fill="none" stroke="#1f5a43" strokeWidth="2" strokeLinejoin="round"/>
            {pts.map((p, i) => <circle key={p.date} cx={x(i)} cy={y(p.predictedVisitors ?? 0)} r="2.5" fill="#1f5a43"><title>{p.date}：{p.predictedVisitors?.toLocaleString()} 人</title></circle>)}
            {pts.map((p, i) => (i % 2 === 0 ? <text key={i} x={x(i)} y={height - 8} textAnchor="middle" fontSize="7" fill="#96a29b">{p.date.slice(5).replace("-", "/")}</text> : null))}
          </svg>
        </div>
        <div className="summary-contribution">
          <div className="summary-chart-title">客流影响因素占比</div>
          <div className="summary-contrib-list">
            {groups.slice(0, 5).map(g => {
              const color = GROUP_COLORS[g.key] ?? "#316b51";
              return <div key={g.key} className="summary-contrib-row">
                <span className="summary-contrib-label">{g.label}</span>
                <div className="summary-contrib-track"><span style={{ width: `${(g.importance / total) * 100}%`, background: color }}/></div>
                <b>{g.importance.toFixed(1)}%</b>
              </div>;
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

const STAGE_ORDER = ["coordinator", "collector", "analyst", "writer", "reviewer", "llm"];

function LoadingState() {
  return <div className="dashboard-loading" aria-label="正在读取分析结果"><div className="loading-line wide"/><div className="loading-grid"><span/><span/><span/></div><div className="loading-chart"/></div>;
}

function EmptyState({ message }: { message: string }) {
  return <div className="dashboard-state"><h2>暂无可展示的分析结果</h2><p>{message}</p><button type="button" onClick={() => navigate("/upload")}>上传数据开始分析</button></div>;
}

function forecastLevel(value: number | null, minimum: number, peak: number) {
  if (value === null || peak <= minimum) return "normal";
  const position = (value - minimum) / (peak - minimum);
  if (position >= .67) return "high";
  if (position <= .33) return "low";
  return "normal";
}

export function DashboardPage() {
  const session = getSession();
  const [analysis, setAnalysis] = useState<AnalysisEnvelope | null>(null);
  const [importance, setImportance] = useState<ImportancePayload | null>(null);
  const [indicators, setIndicators] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [horizon, setHorizon] = useState<Horizon>(7);
  const [view, setView] = useState<"dashboard" | "indicators" | "analysis" | "reports">("dashboard");
  const [agentQuestion, setAgentQuestion] = useState<string | null>(null);

  function askAgent(question: string) {
    setAgentQuestion(question);
  }

  useEffect(() => {
    const activeId = window.localStorage.getItem("scenicmind.activeAnalysisId");
    const request = activeId ? getAnalysis(activeId) : getLatestAnalysis();
    request.then(async data => {
      setAnalysis(data);
      if (data.status === "completed") {
        try { setImportance(await getImportance(data.analysisId)); }
        catch { setImportance(null); }
        try { setIndicators(await getIndicators(data.analysisId)); }
        catch { setIndicators(null); }
      }
    }).catch(reason => {
      if (reason instanceof ApiError && reason.status === 401) {
        clearSession(); navigate("/login", { replace: true }); return;
      }
      setError(reason instanceof Error ? reason.message : "读取分析结果失败");
    }).finally(() => setLoading(false));
  }, []);

  async function logout() { await signOut(); navigate("/login", { replace: true }); }

  const result = analysis?.result;
  const summary = result?.horizons[String(horizon) as "7" | "14" | "30"];
  const nextForecast = result?.forecastPoints[0];
  const visibleForecast = result?.forecastPoints.slice(0, 7) ?? [];
  const change = result && nextForecast?.predictedVisitors !== null && nextForecast?.predictedVisitors !== undefined && result.latestActual.visitors > 0
    ? (nextForecast.predictedVisitors - result.latestActual.visitors) / result.latestActual.visitors * 100
    : null;

  return (
    <main className="dashboard-page">
      <aside className="sidebar">
        <div>
          <a className="brand-mark" href="/dashboard" onClick={event => { event.preventDefault(); navigate("/dashboard"); }}><span className="brand-glyph" aria-hidden="true"><i/><i/><i/></span><span><b>智景</b><small>SCENICMIND</small></span></a>
          <nav className="sidebar-nav" aria-label="主导航">
            <a className={view === "dashboard" ? "active" : ""} href="/dashboard" onClick={event => { event.preventDefault(); setView("dashboard"); }}><Icon name="dashboard"/><span>数据看板</span></a>
            <a className={view === "indicators" ? "active" : ""} href="#indicators" onClick={event => { event.preventDefault(); setView("indicators"); }}><Icon name="drivers"/><span>指标蓝图</span></a>
            <a className={view === "analysis" ? "active" : ""} href="#contribution" onClick={event => { event.preventDefault(); setView("analysis"); }}><Icon name="drivers"/><span>经营分析</span></a>
            <a className={view === "reports" ? "active" : ""} href="#reports" onClick={event => { event.preventDefault(); setView("reports"); }}><Icon name="report"/><span>Agent 报告</span></a>
            <a href="/upload" onClick={event => { event.preventDefault(); navigate("/upload"); }}><Icon name="upload"/><span>上传数据</span></a>
          </nav>
        </div>
        <div className="sidebar-foot">
          <span className="park-status"><i/>{analysis?.status === "completed" ? "分析完成" : "等待数据"}</span>
          <strong>{session?.username ?? "运营管理员"}</strong><small>{session?.email ?? "—"}</small>
          <div className="sidebar-actions"><button type="button" onClick={logout}>退出</button></div>
        </div>
      </aside>

      <section className="dashboard-main">
        {loading ? <LoadingState/> : !result ? <EmptyState message={error || analysis?.error || "请先上传包含日期与真实客流的数据文件。"}/> : view === "indicators" ? (
          <div className="dashboard-content">
            <header className="dashboard-header">
              <div><h1>指标蓝图</h1><p>{result.source.fileName} · 数据截止 {result.latestActual.date}</p></div>            </header>
            <IndicatorBlueprint indicators={indicators} mape={result.metrics.mape} mae={result.metrics.mae}/>
          </div>
        ) : view === "analysis" ? (
          <div className="dashboard-content">
            <header className="dashboard-header">
              <div><h1>经营分析</h1><p>{result.source.fileName} · 数据截止 {result.latestActual.date}</p></div>            </header>
            <FeatureContribution importance={importance} onAskAgent={askAgent}/>
          </div>
        ) : view === "reports" ? (
          <div className="dashboard-content">
            <header className="dashboard-header">
              <div><h1>Agent 报告</h1><p>多 Agent 协作生成 · {result.source.fileName}</p></div>            </header>
            <AgentReportView analysisId={analysis.analysisId} result={result} importance={importance}/>
          </div>
        ) : (
          <div className="dashboard-content">
            <header className="dashboard-header">
              <div><h1>客流预测总览</h1><p>{result.source.fileName} · 数据截止 {result.latestActual.date}</p></div>            </header>

            <div className="dashboard-grid">
              <div className="primary-column">
                <section className="snapshot-strip" aria-label="关键预测指标">
                  <article className="snapshot-primary"><span>最新真实客流</span><div><strong>{result.latestActual.visitors.toLocaleString()}</strong><small>人</small></div><p>{result.latestActual.date} · 上传真实值</p></article>
                  <article><span>下一日预测</span><div><strong>{nextForecast?.predictedVisitors?.toLocaleString() ?? "—"}</strong><small>人</small></div><p>{nextForecast?.date ?? "—"}{change === null ? "" : ` · 较最新真实值 ${change >= 0 ? "+" : ""}${change.toFixed(1)}%`}</p></article>
                  <article><span>未来 {horizon} 天日均</span><div><strong>{summary?.average.toLocaleString() ?? "—"}</strong><small>人</small></div><p>区间 {summary?.minimum.toLocaleString()}–{summary?.peak.toLocaleString()} 人</p></article>
                </section>

                <section className="card trend-card">
                  <div className="trend-heading">
                    <div><h2>真实客流与预测趋势</h2><p>悬停或键盘聚焦数据点，可对照查看真实值与模型预测值</p></div>
                    <div className="history-tabs" role="group" aria-label="预测范围">{([7, 14, 30] as Horizon[]).map(days => <button key={days} type="button" className={horizon === days ? "active" : ""} aria-pressed={horizon === days} onClick={() => setHorizon(days)}>{days}天</button>)}</div>
                  </div>
                  <div className="trend-legend"><span><i className="actual-line-legend"/>真实客流</span><span><i className="forecast-line-legend"/>回测 / 未来预测</span><b>未来 {horizon} 天峰值 {summary?.peak.toLocaleString()} 人</b></div>
                  <TrendChart result={result} horizon={horizon}/>
                  <div className="chart-caption"><span>预测起点：{nextForecast?.date}</span><span>模型：{result.model.name}</span></div>
                </section>

                <section className="forecast-detail">
                  <div className="section-heading"><div><h2>未来 7 日预测明细</h2><p>切换上方周期可同步更新日均、峰值与趋势范围</p></div></div>
                  <div className="week-list">{visibleForecast.map(point => <article className={`week-day level-${forecastLevel(point.predictedVisitors, summary?.minimum ?? 0, summary?.peak ?? 0)}`} key={point.date}><span>{point.date.slice(5)}</span><strong>{point.predictedVisitors?.toLocaleString()}</strong><small>预测人数</small></article>)}</div>
                </section>
              </div>

              <aside className="insight-column" aria-label="分析信息">
                <AdmissionProgress result={result}/>

                <section className="card source-card"><div className="section-heading compact"><div><h2>数据来源</h2><p>本次分析字段接入状态</p></div></div><ul className="availability-list">{Object.entries(result.dataAvailability).map(([key, item]) => <li key={key}><span className={item.status === "uploaded" ? "source-ok" : "source-pending"}/><div><strong>{item.label}</strong><small>{item.status === "uploaded" ? `已接入 · ${item.source}` : "待配置真实数据源"}</small></div></li>)}</ul></section>


              </aside>
            </div>
          </div>
        )}
      </section>
      {analysis && <AgentChat analysisId={analysis.analysisId} pendingQuestion={agentQuestion} onQuestionConsumed={() => setAgentQuestion(null)}/>}
    </main>
  );
}
