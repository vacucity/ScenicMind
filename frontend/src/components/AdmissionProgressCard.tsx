import { numberFormatter } from "../lib/format";

export function AdmissionProgressCard({ entered, predicted }: { entered: number; predicted: number }) {
  const admissionPercent = predicted > 0 ? Math.min(100, Math.round((entered / predicted) * 100)) : 0;
  const segmentCount = 27;
  const activeSegments = Math.round(segmentCount * admissionPercent / 100);

  return (
    <section className="metric-card admission-progress-card" aria-label={`今日已入园人数占预计总人数百分之${admissionPercent}`}>
      <div className="admission-progress-copy">
        <span className="metric-kicker">今日已入园人数</span>
        <div className="admission-count"><strong>{numberFormatter.format(entered)}</strong><span> / {numberFormatter.format(predicted)} 人</span></div>
        <small>已入园 / 今日预计</small>
      </div>
      <div className="admission-ring" aria-hidden="true">
        <svg viewBox="0 0 72 72">
          {Array.from({ length: segmentCount }, (_, index) => {
            const angle = -135 + index * (270 / (segmentCount - 1));
            return <line key={index} className={index < activeSegments ? "admission-segment active" : "admission-segment"} x1="36" y1="5" x2="36" y2="13" transform={`rotate(${angle} 36 36)`} />;
          })}
          <text x="36" y="40" textAnchor="middle">{admissionPercent}%</text>
        </svg>
      </div>
    </section>
  );
}