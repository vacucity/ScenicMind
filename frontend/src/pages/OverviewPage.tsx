import { useState } from "react";
import { Link } from "react-router-dom";

import { AdmissionProgressCard } from "../components/AdmissionProgressCard";
import { AgentChat } from "../components/AgentChat";
import { useDashboard } from "../components/DashboardContext";
import { Icon } from "../components/Icon";
import { TrendChart, type HistoryRange } from "../components/TrendChart";
import { buildChartPoints, chineseDate, numberFormatter, shortLabel, truncate } from "../lib/format";

export function OverviewPage() {
  const { one, report, selectedSpot } = useDashboard();
  const [historyDays, setHistoryDays] = useState<HistoryRange>(7);
  const [agentOpen, setAgentOpen] = useState(false);

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
    <>
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
                <p>更多预测分析请在「客流预测」查看</p>
              </div>
              <div className="trend-controls">
                <div className="legend" aria-label="图例">
                  <span><i className="actual-line-legend" />历史预测</span>
                  <span><i className="line-legend" />未来预测</span>
                </div>
                <span className="day-unit">DAY</span>
                <div className="history-tabs" role="group" aria-label="历史天数">
                  {([7, 14, 30, "all"] as HistoryRange[]).map(days => (
                    <button key={days} type="button" className={historyDays === days ? "active" : ""} aria-pressed={historyDays === days} onClick={() => setHistoryDays(days)}>{days === "all" ? "全部" : `${days}D`}</button>
                  ))}
                </div>
                <Link className="detail-link" to="/dashboard/forecast">详情 <Icon name="chevron" size={13} /></Link>
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
              <Link className="detail-link" to="/dashboard/forecast">查看预测详情 <Icon name="chevron" size={13} /></Link>
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
          </section>
        </div>

        <aside className="insight-column" aria-label="运营洞察">
          <AdmissionProgressCard entered={one.today.entered} predicted={one.today.predicted} />

          <section className="card agent-card" id="agent">
            <div className="card-heading compact-heading">
              <div><h2>Agent 数据报告</h2></div>
              <Link className="detail-link" to="/dashboard/agent">详情 <Icon name="chevron" size={13} /></Link>
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
              <Link className="detail-link" to="/dashboard/prepare">详情 <Icon name="chevron" size={13} /></Link>
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
              <Link className="prepare-footer-link" to="/dashboard/prepare">查看全部运营准备 <Icon name="chevron" size={13} /></Link>
            </div>
          </section>
        </aside>
      </div>

      {agentOpen && <AgentChat spot={selectedSpot} onClose={() => setAgentOpen(false)} />}
    </>
  );
}