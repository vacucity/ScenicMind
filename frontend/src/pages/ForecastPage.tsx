import { useState } from "react";

import { useDashboard } from "../components/DashboardContext";
import { BackToDashboard } from "../components/DashboardLayout";
import { TrendChart, type HistoryRange } from "../components/TrendChart";
import { buildChartPoints, numberFormatter, shortLabel } from "../lib/format";

export function ForecastPage() {
  const { one, selectedSpot } = useDashboard();
  const [historyDays, setHistoryDays] = useState<HistoryRange>(7);

  const { historicalPoints, todayPoint, forecastPoints } = buildChartPoints(one);
  const peak = one.forecast.reduce((a, b) => (b.predicted > a.predicted ? b : a), one.forecast[0]);

  return (
    <div className="detail-page">
      <BackToDashboard />
      <header className="page-heading">
        <h1>客流预测</h1>
        <p>{selectedSpot} · 未来 7 天入园量预测与历史趋势</p>
      </header>

      <section className="metric-strip">
        <div className="metric-card forecast-metric">
          <span className="metric-kicker">今日预计入园</span>
          <div className="metric-value"><strong>{numberFormatter.format(one.today.predicted)}</strong><span>人</span></div>
          <div className="metric-footer">
            <span>区间 {numberFormatter.format(one.today.rangeLow)}–{numberFormatter.format(one.today.rangeHigh)}</span>
            <span className="attention-text">客流{one.today.level}</span>
          </div>
        </div>
        <div className="metric-card forecast-metric">
          <span className="metric-kicker">未来 7 天峰值</span>
          <div className="metric-value"><strong>{numberFormatter.format(peak.predicted)}</strong><span>人</span></div>
          <div className="metric-footer">
            <span>{shortLabel(peak.date)}</span>
            <span className="positive">峰值日</span>
          </div>
        </div>
        <div className="metric-card forecast-metric">
          <span className="metric-kicker">日承载量</span>
          <div className="metric-value"><strong>{numberFormatter.format(one.capacity)}</strong><span>人</span></div>
          <div className="metric-footer">
            <span>峰值承载率</span>
            <span>{Math.round((peak.predicted / one.capacity) * 100)}%</span>
          </div>
        </div>
      </section>

      <section className="card trend-card trend-card-lg">
        <div className="card-heading trend-heading">
          <div>
            <h2>预测趋势图</h2>
            <p>历史上限切换 · 悬停查看数据点 · 拖动两侧平移</p>
          </div>
          <div className="trend-controls">
            <div className="legend" aria-label="图例">
              <span><i className="actual-line-legend" />历史</span>
              <span><i className="line-legend" />未来预测</span>
            </div>
            <div className="history-tabs" role="group" aria-label="历史天数">
              {([7, 14, 30, "all"] as HistoryRange[]).map(days => (
                <button key={days} type="button" className={historyDays === days ? "active" : ""} aria-pressed={historyDays === days} onClick={() => setHistoryDays(days)}>{days === "all" ? "全部" : `${days}D`}</button>
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
      </section>

      <section className="card detail-table-card">
        <div className="card-heading"><h2>未来 7 天预测明细</h2></div>
        <table className="detail-table">
          <thead>
            <tr><th>日期</th><th>预测人数</th><th>P90 上限</th><th>承载率</th><th>客流等级</th><th>备注</th></tr>
          </thead>
          <tbody>
            {one.forecast.map(item => {
              const rate = Math.round((item.predicted / one.capacity) * 100);
              return (
                <tr key={item.date}>
                  <td>{item.date.slice(5)}</td>
                  <td>{numberFormatter.format(item.predicted)}</td>
                  <td>{numberFormatter.format(item.p90)}</td>
                  <td>{rate}%</td>
                  <td>{item.level}</td>
                  <td>{item.level === "较高" ? "建议启动分流预案" : "常规运营"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </div>
  );
}