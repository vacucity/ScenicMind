import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ApiError } from "../../../api/client";
import {
  getAnalysis,
  getImportance,
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
type IconName = "dashboard" | "upload" | "drivers";

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
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function pathFor(points: Array<[number, number]>) {
  return points.map((point, index) => `${index ? "L" : "M"} ${point[0]} ${point[1]}`).join(" ");
}

function TrendChart({ result, horizon }: { result: AnalysisResult; horizon: Horizon }) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [drawProgress, setDrawProgress] = useState(0);
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
      // easeOutCubic
      const eased = 1 - Math.pow(1 - t, 3);
      setDrawProgress(eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
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
  const actual = points.map((point, index) => point.actualVisitors === null ? null : [x(index), y(point.actualVisitors)] as [number, number]).filter((point): point is [number, number] => point !== null);
  const predicted = points.map((point, index) => point.predictedVisitors === null ? null : [x(index), y(point.predictedVisitors)] as [number, number]).filter((point): point is [number, number] => point !== null);
  const forecastStart = result.historyPoints.slice(-30).length;
  const labelEvery = Math.max(1, Math.ceil(points.length / 8));
  const activePoint = activeIndex === null ? null : points[activeIndex];
  const tooltipX = activeIndex === null ? 0 : Math.min(Math.max(x(activeIndex) - 72, pad.left), width - pad.right - 144);
  const tooltipY = activePoint
    ? Math.max(8, Math.min(y(activePoint.predictedVisitors ?? activePoint.actualVisitors ?? 0) - 72, height - 104))
    : 0;

  // 动态绘制：通过 stroke-dasharray 控制可见长度
  const actualLen = actualRef.current?.getTotalLength() ?? 0;
  const forecastLen = forecastRef.current?.getTotalLength() ?? 0;
  // 真实线先绘制（0~55%），预测线后绘制（55%~100%）
  const actualVisible = drawProgress <= 0.55 ? drawProgress / 0.55 : 1;
  const forecastVisible = drawProgress <= 0.55 ? 0 : (drawProgress - 0.55) / 0.45;

  return (
    <div className="chart-wrap">
      <svg className="trend-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`真实客流、历史回测与未来${horizon}天预测趋势`} onMouseLeave={() => setActiveIndex(null)}>
        <rect x={x(forecastStart) - 8} y={pad.top} width={width - pad.right - x(forecastStart) + 8} height={height - pad.top - pad.bottom} className="forecast-zone"/>
        {[0, .25, .5, .75, 1].map(rate => <g key={rate}><line x1={pad.left} x2={width - pad.right} y1={y(max * rate)} y2={y(max * rate)} className="chart-grid"/><text x={pad.left - 12} y={y(max * rate) + 4} textAnchor="end" className="chart-axis-label">{Math.round(max * rate / 1000)}k</text></g>)}
        <line x1={x(forecastStart)} x2={x(forecastStart)} y1={pad.top} y2={height - pad.bottom} className="forecast-boundary"/>
        <text x={x(forecastStart) + 8} y={pad.top + 12} className="forecast-boundary-label">预测开始</text>
        <path
          ref={actualRef}
          d={pathFor(actual)}
          className="actual-line chart-series"
          style={actualLen ? { strokeDasharray: `${actualLen * actualVisible} ${actualLen}` } : undefined}
        />
        <path
          ref={forecastRef}
          d={pathFor(predicted)}
          className="forecast-line chart-series"
          style={forecastLen ? { strokeDasharray: `${forecastLen * forecastVisible} ${forecastLen}` } : undefined}
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

function FeatureContribution({ importance }: { importance: ImportancePayload | null }) {
  const groups = importance?.semantic_groups?.length
    ? importance.semantic_groups
    : fallbackGroups(importance?.feature_importance ?? []);
  return (
    <section className="card contribution-card" id="contribution">
      <div className="section-heading">
        <div><h2>客流影响因素</h2><p>已将技术特征聚合为可解释的业务主题，不展示单个滞后与滚动指标</p></div>
        <span className="explain-badge">模型贡献</span>
      </div>
      {!importance ? <div className="contribution-loading"><span/><span/><span/></div> : groups.length === 0 ? <p className="contribution-empty">本次分析没有足够的可解释贡献数据。</p> : (
        <ol className="contribution-list">
          {groups.slice(0, 6).map(group => <li key={group.key}>
            <div className="contribution-label"><div><strong>{group.label}</strong><small>{group.description}</small></div><b>{group.importance.toFixed(1)}%</b></div>
            <div className="contribution-track" aria-hidden="true"><span style={{ width: `${Math.max(group.importance, 2)}%` }}/></div>
          </li>)}
        </ol>
      )}
      <p className="contribution-note">贡献度表示模型对各类信息的依赖程度，不等同于因果关系。</p>
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

type ChatMessage = { role: "user" | "agent"; text: string; time: string };

function AgentChat({ analysisId }: { analysisId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "agent", text: "你好，我是智景分析助手。可以针对本次客流预测结果向你解答疑问，例如「下周哪天客流最高」「天气对预测有多大影响」。", time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages]);

  function send() {
    const text = input.trim();
    if (!text || sending) return;
    const now = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    setMessages(prev => [...prev, { role: "user", text, time: now }]);
    setInput("");
    setSending(true);
    // 模拟 Agent 回复（后端 Agent 接入后替换为真实 API 调用）
    setTimeout(() => {
      setMessages(prev => [...prev, {
        role: "agent",
        text: `已收到你的问题「${text}」。Agent 推理服务正在接入中，接入完成后将基于本次分析（${analysisId.slice(0, 8)}）给出实时解答。`,
        time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
      }]);
      setSending(false);
    }, 800);
  }

  return (
    <section className="card agent-chat-card">
      <div className="section-heading compact"><div><h2>智景助手</h2><p>针对本次预测结果提问</p></div><span className="agent-badge">Agent</span></div>
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
    </section>
  );
}

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [horizon, setHorizon] = useState<Horizon>(7);

  useEffect(() => {
    const activeId = window.localStorage.getItem("scenicmind.activeAnalysisId");
    const request = activeId ? getAnalysis(activeId) : getLatestAnalysis();
    request.then(async data => {
      setAnalysis(data);
      if (data.status === "completed") {
        try { setImportance(await getImportance(data.analysisId)); }
        catch { setImportance(null); }
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
            <a className="active" href="/dashboard" onClick={event => event.preventDefault()}><Icon name="dashboard"/><span>数据看板</span></a>
            <a href="#contribution"><Icon name="drivers"/><span>影响因素</span></a>
          </nav>
        </div>
        <div className="sidebar-foot">
          <span className="park-status"><i/>{analysis?.status === "completed" ? "分析完成" : "等待数据"}</span>
          <strong>{session?.username ?? "运营管理员"}</strong><small>{session?.email ?? "—"}</small>
          <div className="sidebar-actions"><button type="button" onClick={logout}>退出</button></div>
        </div>
      </aside>

      <section className="dashboard-main">
        {loading ? <LoadingState/> : !result ? <EmptyState message={error || analysis?.error || "请先上传包含日期与真实客流的数据文件。"}/> : (
          <div className="dashboard-content">
            <header className="dashboard-header">
              <div><h1>客流预测总览</h1><p>{result.source.fileName} · 数据截止 {result.latestActual.date}</p></div>
              <button type="button" className="header-upload" onClick={() => navigate("/upload")}><Icon name="upload" size={16}/>上传新数据</button>
            </header>

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
                    <div className="history-tabs" role="group" aria-label="预测范围">{([7, 14, 30] as Horizon[]).map(days => <button key={days} type="button" className={horizon === days ? "active" : ""} aria-pressed={horizon === days} onClick={() => setHorizon(days)}>{days}D</button>)}</div>
                  </div>
                  <div className="trend-legend"><span><i className="actual-line-legend"/>真实客流</span><span><i className="forecast-line-legend"/>回测 / 未来预测</span><b>未来 {horizon} 天峰值 {summary?.peak.toLocaleString()} 人</b></div>
                  <TrendChart result={result} horizon={horizon}/>
                  <div className="chart-caption"><span>预测起点：{nextForecast?.date}</span><span>模型：{result.model.name}</span></div>
                </section>

                <section className="forecast-detail">
                  <div className="section-heading"><div><h2>未来 7 日预测明细</h2><p>切换上方周期可同步更新日均、峰值与趋势范围</p></div></div>
                  <div className="week-list">{visibleForecast.map(point => <article className={`week-day level-${forecastLevel(point.predictedVisitors, summary?.minimum ?? 0, summary?.peak ?? 0)}`} key={point.date}><span>{point.date.slice(5)}</span><strong>{point.predictedVisitors?.toLocaleString()}</strong><small>预测人数</small></article>)}</div>
                </section>

                <FeatureContribution importance={importance}/>
              </div>

              <aside className="insight-column" aria-label="分析信息">
                <AccuracyRing mape={result.metrics.mape} mae={result.metrics.mae} validationDays={result.metrics.validationDays}/>

                <section className="card source-card"><div className="section-heading compact"><div><h2>数据来源</h2><p>本次分析字段接入状态</p></div></div><ul className="availability-list">{Object.entries(result.dataAvailability).map(([key, item]) => <li key={key}><span className={item.status === "uploaded" ? "source-ok" : "source-pending"}/><div><strong>{item.label}</strong><small>{item.status === "uploaded" ? `已接入 · ${item.source}` : "待配置真实数据源"}</small></div></li>)}</ul></section>

                <AgentChat analysisId={analysis.analysisId}/>
              </aside>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
