import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  getModuleOneOutput,
  getModuleTwoOutput,
  getModuleTwoSpots,
  type ModuleOneData,
  type ModuleTwoReport,
} from "../api/modules";
import { AgentChat } from "../components/AgentChat";

type IconName = "dashboard" | "forecast" | "agent" | "prepare" | "history" | "bell" | "chevron";

type HistoryRange = 7 | 14 | 30;
type ChartPoint = {
  label: string;
  fullLabel: string;
  value: number;
  kind: "history" | "today" | "forecast";
};

const navItems: Array<{ label: string; icon: IconName; target: string }> = [
  { label: "数据看板", icon: "dashboard", target: "entrance" },
  { label: "客流预测", icon: "forecast", target: "trend" },
  { label: "Agent 报告", icon: "agent", target: "agent" },
  { label: "运营准备", icon: "prepare", target: "prepare" },
  { label: "历史记录", icon: "history", target: "trend" },
];

const numberFormatter = new Intl.NumberFormat("zh-CN");

function parseDate(iso: string): Date {
  return new Date(`${iso}T00:00:00`);
}

function shortLabel(iso: string): string {
  const date = parseDate(iso);
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

function chineseDate(iso: string): string {
  const date = parseDate(iso);
  const weekdays = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日 · ${weekdays[date.getDay()]}`;
}

function truncate(text: string, limit = 34): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  return normalized.length <= limit ? normalized : `${normalized.slice(0, limit)}…`;
}

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    dashboard: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
    forecast: <><path d="M4 18V9m6 9V5m6 13v-7m5 7H3"/><path d="m4 8 6-4 6 6 5-5"/></>,
    agent: <><path d="M8 4h8a4 4 0 0 1 4 4v7a4 4 0 0 1-4 4h-5l-4 3v-3a4 4 0 0 1-3-4V8a4 4 0 0 1 4-4Z"/><path d="M8 10h.01M12 10h.01M16 10h.01"/></>,
    prepare: <><path d="M4 5h16v14H4z"/><path d="M8 3v4m8-4v4M4 10h16M8 14h3m2 0h3"/></>,
    history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5m4-1v5l3 2"/></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></>,
    chevron: <path d="m9 18 6-6-6-6"/>,
  };

  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

function smoothPath(points: Array<[number, number]>) {
  if (!points.length) return "";
  if (points.length === 1) return `M ${points[0][0]} ${points[0][1]}`;

  return points.reduce((path, point, index) => {
    if (index === 0) return `M ${point[0]} ${point[1]}`;
    const previous = points[index - 1];
    const midX = (previous[0] + point[0]) / 2;
    return `${path} C ${midX} ${previous[1]}, ${midX} ${point[1]}, ${point[0]} ${point[1]}`;
  }, "");
}

function TrendChart({
  historicalPoints,
  todayPoint,
  forecastPoints,
  historyDays,
}: {
  historicalPoints: ChartPoint[];
  todayPoint: ChartPoint;
  forecastPoints: ChartPoint[];
  historyDays: HistoryRange;
}) {
  const points = useMemo(
    () => [...historicalPoints.slice(-historyDays), todayPoint, ...forecastPoints],
    [historicalPoints, todayPoint, forecastPoints, historyDays],
  );
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(historyDays);
  const [panDelta, setPanDelta] = useState(0);
  const width = 820;
  const height = 300;
  const pad = { top: 32, right: 24, bottom: 38, left: 48 };
  const maxValue = Math.max(...points.map(point => point.value)) * 1.16;
  const stepX = 72;
  const x = (index: number) => pad.left + index * stepX;
  const y = (value: number) => height - pad.bottom - (value / maxValue) * (height - pad.top - pad.bottom);
  const todayIndex = historyDays;
  const minPan = Math.min(0, width - pad.right - x(points.length - 1));
  const basePan = Math.max(minPan, Math.min(0, width * .5 - x(todayIndex)));
  const panX = Math.max(minPan, Math.min(0, basePan + panDelta));
  const actualLinePoints = points.slice(0, todayIndex + 1).map((point, index) => [x(index), y(point.value)] as [number, number]);
  const futureLinePoints = points.slice(todayIndex).map((point, index) => [x(todayIndex + index), y(point.value)] as [number, number]);
  const upperPoints = futureLinePoints.map((point, index) => [point[0], y(points[todayIndex + index].value * 1.1)] as [number, number]);
  const lowerPoints = futureLinePoints.map((point, index) => [point[0], y(points[todayIndex + index].value * 0.9)] as [number, number]).reverse();
  const areaPath = `${upperPoints.map((point, index) => `${index ? "L" : "M"} ${point[0]} ${point[1]}`).join(" ")} ${lowerPoints.map(point => `L ${point[0]} ${point[1]}`).join(" ")} Z`;
  const gridValues = [0.25, 0.5, 0.75, 1];
  const labelEvery = 2;
  const hoveredPoint = hoveredIndex === null ? null : points[hoveredIndex];
  const tooltipX = hoveredIndex === null ? 0 : Math.min(Math.max(x(hoveredIndex) + panX, 80), width - 80) - panX;
  const tooltipY = hoveredPoint ? Math.max(y(hoveredPoint.value) - 56, 8) : 0;

  useEffect(() => {
    setPanDelta(0);
    setHoveredIndex(historyDays);
  }, [historyDays, todayPoint]);

  const shiftChart = (direction: -1 | 1) => {
    setPanDelta(current => {
      const next = current + direction * 210;
      return Math.max(minPan - basePan, Math.min(-basePan, next));
    });
  };

  return (
    <div className="chart-wrap">
      <svg className="trend-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`近${historyDays}天历史预测与未来七天预测趋势`} onMouseLeave={() => setHoveredIndex(todayIndex)}>
        <defs>
          <clipPath id="trend-plot-clip">
            <rect x={pad.left - 8} y="0" width={width - pad.left - pad.right + 16} height={height} />
          </clipPath>
        </defs>
        {gridValues.map(rate => {
          const gridY = pad.top + (1 - rate) * (height - pad.top - pad.bottom);
          return <line key={rate} x1={pad.left} x2={width - pad.right} y1={gridY} y2={gridY} className="chart-grid" />;
        })}

        <g className="chart-pan-layer" clipPath="url(#trend-plot-clip)" style={{ transform: `translateX(${panX}px)` }}>
          <path d={areaPath} className="forecast-band" />
          <path d={smoothPath(actualLinePoints)} className="actual-line" />
          <path d={smoothPath(futureLinePoints)} className="forecast-line" />

          <line x1={x(todayIndex)} x2={x(todayIndex)} y1={pad.top - 5} y2={height - pad.bottom} className="today-line" />

          {points.map((point, index) => (
            <g key={`${point.fullLabel}-${point.kind}`}>
              <circle cx={x(index)} cy={y(point.value)} r={point.kind === "today" ? 6 : 2.8} className={point.kind === "today" ? "today-dot" : point.kind === "forecast" ? "forecast-dot" : "actual-dot"} />
              <circle
                cx={x(index)}
                cy={y(point.value)}
                r="13"
                className="chart-hit"
                tabIndex={0}
                aria-label={`${point.fullLabel} 预测客流 ${point.value.toLocaleString()} 人`}
                onMouseEnter={() => setHoveredIndex(index)}
                onFocus={() => setHoveredIndex(index)}
              />
            </g>
          ))}

          {points.map((point, index) => (index % labelEvery === 0 || index === todayIndex || index === points.length - 1) && (
            <text key={point.fullLabel} x={x(index)} y={height - 12} textAnchor="middle" className={point.kind === "today" ? "chart-label today-label" : "chart-label"}>{point.label}</text>
          ))}

          {hoveredPoint && (
            <g className="chart-tooltip" transform={`translate(${tooltipX - 58} ${tooltipY})`}>
              <rect width="116" height="42" rx="7" />
              <text x="10" y="16">{hoveredPoint.kind === "today" ? "今天预测" : hoveredPoint.fullLabel}</text>
              <text x="10" y="32" className="tooltip-value">{hoveredPoint.value.toLocaleString()} 人</text>
            </g>
          )}
        </g>
      </svg>
      <button className="chart-pan-zone chart-pan-left" type="button" aria-label="向左滑动查看更多日期" onMouseEnter={() => shiftChart(-1)} onFocus={() => shiftChart(-1)} onClick={() => shiftChart(-1)}><span>‹</span></button>
      <button className="chart-pan-zone chart-pan-right" type="button" aria-label="向右滑动查看历史日期" onMouseEnter={() => shiftChart(1)} onFocus={() => shiftChart(1)} onClick={() => shiftChart(1)}><span>›</span></button>
    </div>
  );
}

function MetricCard({ title, value, children, variant }: { title: string; value: string; children: ReactNode; variant?: "forecast" }) {
  return (
    <section className={`metric-card ${variant === "forecast" ? "forecast-metric" : ""}`}>
      <div className="metric-title-row">
        <span className="metric-kicker">{title}</span>
        <span className="metric-rule" />
      </div>
      <div className="metric-value"><strong>{value}</strong><span>人</span></div>
      <div className="metric-footer">{children}</div>
    </section>
  );
}

function buildChartPoints(one: ModuleOneData) {
  const historicalPoints: ChartPoint[] = one.history.map(item => ({
    label: shortLabel(item.date),
    fullLabel: item.date,
    value: item.visitors,
    kind: "history",
  }));
  const todayPoint: ChartPoint = {
    label: "今天",
    fullLabel: one.today.date,
    value: one.today.predicted,
    kind: "today",
  };
  const forecastPoints: ChartPoint[] = one.forecast.map(item => ({
    label: shortLabel(item.date),
    fullLabel: item.date,
    value: item.predicted,
    kind: "forecast",
  }));
  return { historicalPoints, todayPoint, forecastPoints };
}

export function DashboardPage() {
  const [historyDays, setHistoryDays] = useState<HistoryRange>(7);
  const [spots, setSpots] = useState<string[]>(["黄果树瀑布"]);
  const [selectedSpot, setSelectedSpot] = useState("黄果树瀑布");
  const [one, setOne] = useState<ModuleOneData | null>(null);
  const [report, setReport] = useState<ModuleTwoReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [agentOpen, setAgentOpen] = useState(false);
  const [showDetail, setShowDetail] = useState<"forecast" | "prepare" | null>(null);

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  useEffect(() => {
    let active = true;
    getModuleTwoSpots().then(list => {
      if (!active) return;
      if (list.length) {
        setSpots(list);
        if (!list.includes(selectedSpot)) {
          setSelectedSpot(list[0]);
        }
      }
    }).catch(() => undefined);
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    Promise.all([
      getModuleOneOutput(selectedSpot),
      getModuleTwoOutput(selectedSpot),
    ])
      .then(([oneOutput, reportOutput]) => {
        if (!active) return;
        setOne(oneOutput.data);
        setReport(reportOutput.data);
      })
      .catch((requestError: unknown) => {
        if (active) {
          setError(requestError instanceof Error ? requestError.message : "数据加载失败");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedSpot]);

  if (loading || !one || !report) {
    return (
      <main className="dashboard-page">
        <aside className="sidebar">
          <div>
            <a className="brand-mark" href="/dashboard" aria-label="智景 ScenicMind 首页">
              <span className="brand-glyph" aria-hidden="true"><i /><i /><i /></span>
              <span><b>智景</b><small>SCENICMIND</small></span>
            </a>
          </div>
        </aside>
        <section className="dashboard-main">
          <div className="card" style={{ padding: 48, textAlign: "center" }}>
            {error
              ? <><h2 style={{ margin: 0 }}>数据加载失败</h2><p style={{ color: "var(--muted)", margin: "8px 0 0" }}>{error}（请确认后端已启动于 127.0.0.1:8000）</p></>
              : <><h2 style={{ margin: 0 }}>正在加载经营驾驶舱…</h2><p style={{ color: "var(--muted)", margin: "8px 0 0" }}>正在请求客流预测与经营报告</p></>}
          </div>
        </section>
      </main>
    );
  }

  const { historicalPoints, todayPoint, forecastPoints } = buildChartPoints(one);
  const week = one.week.map(item => ({
    day: item.day,
    value: numberFormatter.format(item.value),
    level: item.level,
  }));
  const peak = one.forecast.reduce((a, b) => (b.predicted > a.predicted ? b : a), one.forecast[0]);
  const kpis = report.kpis;
  const leadingDriver = report.drivers.length
    ? report.drivers.reduce((a, b) => (Math.abs(b.contributionVisitors) > Math.abs(a.contributionVisitors) ? b : a))
    : null;
  const topRecommendation = report.recommendations[0];
  const recommendations = report.recommendations.slice(0, 4);
  const riskText = one.today.level === "较高" ? "较高客流" : one.today.level === "较低" ? "较低客流" : "正常客流";

  return (
    <main className="dashboard-page">
      <aside className="sidebar">
        <div>
          <a className="brand-mark" href="/dashboard" aria-label="智景 ScenicMind 首页">
            <span className="brand-glyph" aria-hidden="true"><i /><i /><i /></span>
            <span><b>智景</b><small>SCENICMIND</small></span>
          </a>

          <nav className="sidebar-nav" aria-label="主导航">
            {navItems.map((item, index) => (
              <a
                key={item.label}
                href={`#${item.target}`}
                className={index === 0 ? "active" : ""}
                aria-current={index === 0 ? "page" : undefined}
                onClick={event => {
                  event.preventDefault();
                  scrollTo(item.target);
                }}
              >
                <Icon name={item.icon} />
                <span>{item.label}</span>
              </a>
            ))}
          </nav>
        </div>

        <div className="sidebar-foot">
          <span className="park-status"><i />数据正常</span>
          <strong>{selectedSpot} · 全园</strong>
          <small>数据更新于 14:00</small>
        </div>
      </aside>

      <section className="dashboard-main">
        <div className="dashboard-header">
          <div className="header-tools">
            <label className="park-selector" aria-label="选择景点">
              <select
                value={selectedSpot}
                onChange={event => setSelectedSpot(event.target.value)}
                style={{ border: 0, background: "transparent", color: "inherit", fontSize: 11, cursor: "pointer", outline: "none", width: "100%" }}
              >
                {spots.map(spot => (
                  <option key={spot} value={spot}>{spot}</option>
                ))}
              </select>
            </label>
          </div>
        </div>

        <div className="dashboard-grid">
          <div className="primary-column">
            <section className="metric-card entrance-metric" id="entrance">
              <div className="entrance-stat">
                <div className="metric-title-row">
                  <span className="metric-kicker">今日预计总人数</span>
                </div>
                <div className="metric-value"><strong>{numberFormatter.format(one.today.predicted)}</strong><span>人</span></div>
                <div className="metric-footer">
                  <span>预计范围 {numberFormatter.format(one.today.rangeLow)}–{numberFormatter.format(one.today.rangeHigh)}</span>
                  <span className="attention-text">客流{one.today.level}</span>
                </div>
              </div>
              <div className="dashboard-in-card">
                <h1>Dashboard</h1>
                <p>{chineseDate(one.today.date)}</p>
              </div>
            </section>

            <section className="card trend-card" id="trend">
              <div className="card-heading trend-heading">
                <div>
                  <h2>客流预测趋势</h2>
                </div>
                <div className="trend-controls">
                  <div className="legend" aria-label="图例">
                    <span><i className="actual-line-legend" />历史预测</span>
                    <span><i className="line-legend" />未来预测</span>
                  </div>
                  <span className="day-unit">DAY</span>
                  <div className="history-tabs" role="group" aria-label="历史天数">
                    {([7, 14, 30] as HistoryRange[]).map(days => (
                      <button key={days} type="button" className={historyDays === days ? "active" : ""} aria-pressed={historyDays === days} onClick={() => setHistoryDays(days)}>{days}D</button>
                    ))}
                  </div>
                </div>
              </div>
              <TrendChart
                historicalPoints={historicalPoints}
                todayPoint={todayPoint}
                forecastPoints={forecastPoints}
                historyDays={historyDays}
              />
              <div className="chart-caption">
                <span className="chart-peak"><i />预计峰值 {numberFormatter.format(peak.predicted)} 人 · {shortLabel(peak.date)}</span>
                <span>悬停两侧滑动 · 数据点查看详情</span>
              </div>
            </section>

            <section className="card week-card">
              <div className="card-heading compact-heading">
                <div className="week-heading-copy"><h2>未来 7 天</h2><span>{selectedSpot}预计入园人数</span></div>
                <button
                  type="button"
                  className="text-link"
                  onClick={() => setShowDetail(showDetail === "forecast" ? null : "forecast")}
                >
                  {showDetail === "forecast" ? "收起详情" : "查看预测详情"} <Icon name="chevron" size={14} />
                </button>
              </div>
              <div className="week-list">
                {week.map(item => (
                  <div className={`week-day ${item.level === "较高" ? "level-high" : item.level === "较低" ? "level-low" : "level-normal"}`} key={item.day}>
                    <span>周{item.day}</span>
                    <strong>{item.value}</strong>
                    <small>{item.level}</small>
                  </div>
                ))}
              </div>
              {showDetail === "forecast" && (
                <div className="detail-panel">
                  <div className="detail-panel-head">未来 7 天预测明细（{selectedSpot}）</div>
                  <table className="detail-table">
                    <thead>
                      <tr><th>日期</th><th>预测人数</th><th>P90</th><th>客流等级</th></tr>
                    </thead>
                    <tbody>
                      {one.forecast.map(item => (
                        <tr key={item.date}>
                          <td>{item.date.slice(5)}</td>
                          <td>{numberFormatter.format(item.predicted)}</td>
                          <td>{numberFormatter.format(item.p90)}</td>
                          <td>{item.level}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>

          <aside className="insight-column" aria-label="运营洞察">
            <MetricCard title="今日已入园人数" value={numberFormatter.format(one.today.entered)}>
              <span>{one.today.enteredTime}</span>
              <span className="positive">{one.today.enteredWow}</span>
            </MetricCard>

            <section className="card agent-card" id="agent">
              <div className="card-heading compact-heading">
                <div><h2>Agent 数据报告</h2></div>
              </div>
              <div className="agent-list">
                <article><span>客流变化</span><p>{truncate(report.executiveSummary, 52)}</p></article>
                <article><span>可能原因</span><p>{leadingDriver ? truncate(`${leadingDriver.label}：${leadingDriver.explanation}`, 52) : "暂无归因数据"}</p></article>
                <article><span>运营建议</span><p>{topRecommendation ? truncate(`${topRecommendation.title}：${topRecommendation.action}`, 52) : "暂无建议"}</p></article>
              </div>
              <div className="agent-footer">
                <button className="agent-consult-button" type="button" onClick={() => setAgentOpen(true)}>咨询 Agent <Icon name="chevron" size={13} /></button>
              </div>
            </section>

            <section className="card prepare-card" id="prepare">
              <div className="card-heading compact-heading">
                <div><h2>运营准备</h2></div>
                <span className="risk-label"><i />{riskText}</span>
              </div>
              <p className="prepare-lead">峰值日 {shortLabel(kpis.peakDate)} · 预计达到承载量 {Math.round(kpis.peakCapacityRate * 100)}%</p>
              <div className="prepare-table">
                <div className="prepare-head"><span>建议项</span><span>优先级</span><span>预期效果</span></div>
                {recommendations.map(item => (
                  <div key={item.recommendationId}>
                    <span>{truncate(item.title, 18)}</span>
                    <b>{item.priority}</b>
                    <strong>{truncate(item.expectedImpact, 12)}</strong>
                  </div>
                ))}
                {!recommendations.length && (
                  <div><span>暂无运营建议</span><b>-</b><strong>-</strong></div>
                )}
              </div>
              <button
                className="prepare-button"
                type="button"
                onClick={() => setShowDetail(showDetail === "prepare" ? null : "prepare")}
              >
                {showDetail === "prepare" ? "收起详情" : "查看运营准备"} <Icon name="chevron" size={14} />
              </button>
              {showDetail === "prepare" && (
                <div className="detail-panel">
                  <div className="detail-panel-head">运营建议明细</div>
                  <div className="rec-list">
                    {report.recommendations.map(item => (
                      <div className="rec-item" key={item.recommendationId}>
                        <div className="rec-item-head">
                          <span className={`rec-priority rec-priority-${item.priority}`}>{item.priority}</span>
                          <strong>{item.title}</strong>
                        </div>
                        <p>{item.action}</p>
                        <div className="rec-item-meta">
                          <span>依据：{item.rationale}</span>
                          <span>预期效果：{item.expectedImpact}</span>
                          {item.evidenceRefs.length > 0 && <span>证据：{item.evidenceRefs.join("、")}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>
          </aside>
        </div>
      </section>

      {agentOpen && <AgentChat spot={selectedSpot} onClose={() => setAgentOpen(false)} />}
    </main>
  );
}