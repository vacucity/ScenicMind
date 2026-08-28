import { useEffect, useMemo, useState, type ReactNode } from "react";

type IconName = "dashboard" | "forecast" | "agent" | "prepare" | "history" | "bell" | "chevron";

type HistoryRange = 7 | 14 | 30;
type ChartPoint = {
  label: string;
  fullLabel: string;
  value: number;
  kind: "history" | "today" | "forecast";
};

const historyValues = [
  5400, 6100, 5800, 6900, 7200, 6700, 7600, 8100, 7400, 6900,
  8300, 8800, 7900, 7100, 6500, 7200, 7600, 8400, 9100, 7800,
  7300, 6900, 7600, 8200, 8700, 7400, 6800, 7900, 8100, 8250,
];
const futureValues = [12800, 9600, 6300, 5900, 7200, 8100, 10400];

function dateLabel(offset: number) {
  const date = new Date(2026, 7, 28);
  date.setDate(date.getDate() + offset);
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

const historicalPoints: ChartPoint[] = historyValues.map((value, index) => ({
  label: dateLabel(index - historyValues.length),
  fullLabel: `2026/${dateLabel(index - historyValues.length)}`,
  value,
  kind: "history",
}));

const todayPoint: ChartPoint = { label: "今天", fullLabel: "2026/8/28", value: 12800, kind: "today" };
const forecastPoints: ChartPoint[] = futureValues.map((value, index) => ({
  label: dateLabel(index + 1),
  fullLabel: `2026/${dateLabel(index + 1)}`,
  value,
  kind: "forecast",
}));

const navItems: Array<{ label: string; icon: IconName }> = [
  { label: "数据看板", icon: "dashboard" },
  { label: "客流预测", icon: "forecast" },
  { label: "Agent 报告", icon: "agent" },
  { label: "运营准备", icon: "prepare" },
  { label: "历史记录", icon: "history" },
];

const weekForecast = [
  { day: "六", value: "12,800", level: "较高" },
  { day: "日", value: "9,600", level: "正常" },
  { day: "一", value: "6,300", level: "较低" },
  { day: "二", value: "5,900", level: "较低" },
  { day: "三", value: "7,200", level: "正常" },
  { day: "四", value: "8,100", level: "正常" },
  { day: "五", value: "10,400", level: "较高" },
];

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

function TrendChart({ historyDays }: { historyDays: HistoryRange }) {
  const points = useMemo(
    () => [...historicalPoints.slice(-historyDays), todayPoint, ...forecastPoints],
    [historyDays],
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
  }, [historyDays]);

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

export function DashboardPage() {
  const [historyDays, setHistoryDays] = useState<HistoryRange>(7);

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
              <a key={item.label} href={index === 0 ? "/dashboard" : `#${item.icon}`} className={index === 0 ? "active" : ""} aria-current={index === 0 ? "page" : undefined}>
                <Icon name={item.icon} />
                <span>{item.label}</span>
              </a>
            ))}
          </nav>
        </div>

        <div className="sidebar-foot">
          <span className="park-status"><i />数据正常</span>
          <strong>示范景区 · 全园</strong>
          <small>数据更新于 14:00</small>
        </div>
      </aside>

      <section className="dashboard-main">
        <div className="dashboard-grid">
          <div className="primary-column">
            <section className="metric-card entrance-metric">
              <div className="entrance-stat">
                <div className="metric-title-row">
                  <span className="metric-kicker">今日预计总人数</span>
                </div>
                <div className="metric-value"><strong>12,800</strong><span>人</span></div>
                <div className="metric-footer">
                  <span>预计范围 11,900–13,700</span>
                  <span className="attention-text">客流较高</span>
                </div>
              </div>
              <div className="dashboard-in-card">
                <h1>Dashboard</h1>
                <p>2026年8月28日 · 星期五</p>
              </div>
            </section>

            <section className="card trend-card">
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
              <TrendChart historyDays={historyDays} />
              <div className="chart-caption">
                <span className="chart-peak"><i />预计峰值 12,800 人 · 8月29日</span>
                <span>悬停两侧滑动 · 数据点查看详情</span>
              </div>
            </section>

            <section className="card week-card">
              <div className="card-heading compact-heading">
                <div className="week-heading-copy"><h2>未来 7 天</h2><span>全园预计入园人数</span></div>
                <button type="button" className="text-link">查看预测详情 <Icon name="chevron" size={14} /></button>
              </div>
              <div className="week-list">
                {weekForecast.map(item => (
                  <div className={`week-day ${item.level === "较高" ? "level-high" : item.level === "较低" ? "level-low" : "level-normal"}`} key={item.day}>
                    <span>周{item.day}</span>
                    <strong>{item.value}</strong>
                    <small>{item.level}</small>
                  </div>
                ))}
              </div>
            </section>
          </div>

          <aside className="insight-column" aria-label="运营洞察">
            <MetricCard title="今日已入园人数" value="8,426">
              <span>截至 14:00</span>
              <span className="positive">较上周同期 +8.4%</span>
            </MetricCard>

            <section className="card agent-card">
              <div className="card-heading compact-heading">
                <div><h2>Agent 数据报告</h2></div>
              </div>
              <div className="agent-list">
                <article><span>客流变化</span><p>今日客流预计较上周同期增长 11%。</p></article>
                <article><span>可能原因</span><p>天气晴朗，上午预约量持续上升。</p></article>
                <article><span>运营建议</span><p>15:00 前确认高峰接待预案。</p></article>
              </div>
              <div className="agent-footer">
                <button className="agent-consult-button" type="button">咨询 Agent <Icon name="chevron" size={13} /></button>
              </div>
            </section>

            <section className="card prepare-card">
              <div className="card-heading compact-heading">
                <div><h2>运营准备</h2></div>
                <span className="risk-label"><i />较高客流</span>
              </div>
              <p className="prepare-lead">周六 · 建议检查高峰接待预案</p>
              <div className="prepare-table">
                <div className="prepare-head"><span>资源</span><span>当前</span><span>建议</span></div>
                <div><span>开放入口</span><b>3</b><strong>4</strong></div>
                <div><span>摆渡车辆</span><b>6</b><strong>8</strong></div>
                <div><span>现场人员</span><b>42</b><strong>48</strong></div>
              </div>
              <button className="prepare-button" type="button">查看运营准备 <Icon name="chevron" size={14} /></button>
            </section>
          </aside>
        </div>
      </section>
    </main>
  );
}
