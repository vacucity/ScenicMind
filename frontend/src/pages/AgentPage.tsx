import { useEffect, useState } from "react";

import { getAgentReport, type AgentReport } from "../api/modules";
import { AgentChat } from "../components/AgentChat";
import { useDashboard } from "../components/DashboardContext";
import { BackToDashboard } from "../components/DashboardLayout";
import { numberFormatter, shortLabel } from "../lib/format";

const CONFIDENCE_LABEL: Record<string, string> = { high: "高", medium: "中", low: "低" };

export function AgentPage() {
  const { selectedSpot } = useDashboard();
  const [report, setReport] = useState<AgentReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [agentOpen, setAgentOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setReport(null);
    setError(null);
    getAgentReport(selectedSpot)
      .then(data => {
        if (!cancelled) setReport(data);
      })
      .catch(() => {
        if (!cancelled) setError("报告加载失败，请确认后端服务已启动。");
      });
    return () => {
      cancelled = true;
    };
  }, [selectedSpot]);

  if (error) {
    return (
      <div className="detail-page">
        <BackToDashboard />
        <p className="detail-error">{error}</p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="detail-page">
        <BackToDashboard />
        <p className="detail-loading">正在生成经营报告…</p>
      </div>
    );
  }

  const risk = report.risk;
  const accuracy = report.accuracy;

  return (
    <div className="detail-page">
      <BackToDashboard />
      <header className="page-heading">
        <h1>Agent 数据报告</h1>
        <p>{report.title} · 证据约束型经营分析</p>
      </header>

      <section className="card summary-card">
        <div className="card-heading compact-heading">
          <div><h2>一、预测准确率复盘</h2></div>
          <button className="agent-consult-button agent-consult-inline" type="button" onClick={() => setAgentOpen(true)}>咨询 Agent</button>
        </div>
        <p className="summary-copy">
          日级 MAPE {Math.round(accuracy.mapeDaily * 1000) / 10}%（达标线 {Math.round(accuracy.mapeThreshold * 100)}%），
          模型状态 {accuracy.modelStatus}。
          {accuracy.driftDays.length > 0 ? `漂移日：${accuracy.driftDays.join("、")}` : "本周无显著漂移日。"}
        </p>
        <div className="summary-kpis">
          <div><span>模型状态</span><strong>{accuracy.modelStatus}</strong></div>
          <div><span>日级 MAPE</span><strong>{Math.round(accuracy.mapeDaily * 1000) / 10}%</strong></div>
          <div><span>达标线</span><strong>{Math.round(accuracy.mapeThreshold * 100)}%</strong></div>
          <div><span>达标判定</span><strong>{accuracy.passed ? "✅ 达标" : "❌ 未达标"}</strong></div>
          <div><span>报告置信度</span><strong>{report.reportConfidence}</strong></div>
        </div>
      </section>

      <section className="card detail-table-card">
        <div className="card-heading"><h2>二、客流归因</h2><p>SHAP 特征贡献 · 按影响绝对值从高到低</p></div>
        <table className="detail-table">
          <thead>
            <tr><th>驱动因素</th><th>方向</th><th>SHAP</th><th>占比</th><th>置信度</th><th>说明</th></tr>
          </thead>
          <tbody>
            {report.attribution.map(driver => (
              <tr key={driver.feature}>
                <td>{driver.label}</td>
                <td>{driver.direction === "positive" ? "↑ 拉升" : "↓ 抑制"}</td>
                <td style={{ fontVariantNumeric: "tabular-nums" }}>{driver.shap >= 0 ? "+" : ""}{numberFormatter.format(driver.shap)}</td>
                <td style={{ fontVariantNumeric: "tabular-nums" }}>{Math.round(Math.abs(driver.pct) * 100)}%</td>
                <td>{CONFIDENCE_LABEL[driver.confidence] ?? driver.confidence}</td>
                <td>{driver.explanation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card detail-table-card">
        <div className="card-heading"><h2>三、经营建议</h2><p>按优先级从高到低</p></div>
        <table className="detail-table">
          <thead>
            <tr><th>优先级</th><th>类别</th><th>建议</th><th>预期效果</th></tr>
          </thead>
          <tbody>
            {report.recommendations.map(rec => (
              <tr key={rec.recommendationId}>
                <td>{rec.priority}</td>
                <td>{rec.category}</td>
                <td>
                  <strong>{rec.title}</strong>
                  <p className="table-sub">{rec.action}</p>
                </td>
                <td>{rec.expectedImpact}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card detail-table-card">
        <div className="card-heading"><h2>四、风险提示</h2><p>峰值日运营风险</p></div>
        <div className="summary-kpis">
          <div><span>峰值日期</span><strong>{shortLabel(risk.peakDate)}</strong></div>
          <div><span>峰值承载率</span><strong>{Math.round(risk.peakCapacityRate * 100)}%</strong></div>
          <div><span>峰值客流</span><strong>{numberFormatter.format(risk.peakVisitors)}</strong></div>
          <div><span>风险等级</span><strong>{risk.riskLevel}</strong></div>
        </div>
        <p className="note-line">本报告由 AI 生成，供决策参考，不构成自动处置指令。</p>
      </section>

      {agentOpen && <AgentChat spot={selectedSpot} onClose={() => setAgentOpen(false)} />}
    </div>
  );
}