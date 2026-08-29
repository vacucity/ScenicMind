import { useDashboard } from "../components/DashboardContext";
import { BackToDashboard } from "../components/DashboardLayout";
import { numberFormatter, shortLabel } from "../lib/format";

export function PreparePage() {
  const { one, report } = useDashboard();
  const kpis = report.kpis;
  const recommendations = report.recommendations;
  const riskText = one.today.level === "较高" ? "较高客流" : one.today.level === "较低" ? "较低客流" : "正常客流";

  return (
    <div className="detail-page">
      <BackToDashboard />
      <header className="page-heading">
        <h1>运营准备</h1>
        <p>峰值日 {shortLabel(kpis.peakDate)} · 预计达到承载量 {Math.round(kpis.peakCapacityRate * 100)}% · 当前{riskText}</p>
      </header>

      <div className="rec-list">
        {recommendations.map(item => (
          <article key={item.recommendationId} className="rec-item rec-item-full">
            <div className="rec-item-head">
              <span className={`rec-priority rec-priority-${item.priority}`}>{item.priority}</span>
              <span className="rec-category">{item.category}</span>
              <strong>{item.title}</strong>
            </div>
            <p className="rec-action">{item.action}</p>
            <div className="rec-item-meta">
              <span>依据：{item.rationale}</span>
              <span>预期效果：{item.expectedImpact}</span>
              {item.evidenceRefs.length > 0 && <span>证据：{item.evidenceRefs.join("、")}</span>}
            </div>
          </article>
        ))}
      </div>

      <section className="card guardrail-card">
        <div className="card-heading"><h2>护栏说明</h2></div>
        <ul className="guardrail-list">
          {report.guardrails.map((text, index) => (
            <li key={index}>{text}</li>
          ))}
        </ul>
        <p className="guardrail-note">报告 ID：{report.reportId} · 生成模式：{report.trace.generationMode} · 模型版本：{report.trace.modelVersion}</p>
      </section>
    </div>
  );
}