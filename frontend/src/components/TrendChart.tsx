import { useEffect, useMemo, useState } from "react";

import type { ChartPoint } from "../lib/format";

export type HistoryRange = 7 | 14 | 30 | "all";

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

export function TrendChart({
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
  const points = useMemo(() => {
    if (historyDays === "all") {
      return [...historicalPoints, todayPoint, ...forecastPoints];
    }
    const n = historyDays;
    const fc = Math.min(Math.floor((n - 1) / 2), forecastPoints.length);
    const hc = n - 1 - fc;
    return [
      ...historicalPoints.slice(-hc),
      todayPoint,
      ...forecastPoints.slice(0, fc),
    ];
  }, [historicalPoints, todayPoint, forecastPoints, historyDays]);

  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [panDelta, setPanDelta] = useState(0);
  const width = 820;
  const height = 300;
  // 左右各留 30px 给数值标签和日期标签不被遮挡
  const pad = { top: 36, right: 30, bottom: 38, left: 30 };
  const maxValue = Math.max(...points.map(point => point.value)) * 1.18;
  const availWidth = width - pad.left - pad.right;
  // 点数少时撑满可用宽度；点数多时最小 6px
  const stepX = points.length > 1 ? Math.max(6, availWidth / (points.length - 1)) : 72;
  const x = (index: number) => pad.left + index * stepX;
  const y = (value: number) => height - pad.bottom - (value / maxValue) * (height - pad.top - pad.bottom);
  const todayIndex = points.findIndex(p => p.kind === "today");
  // 内容是否超出可视宽度（需要平移）
  const contentWidth = points.length > 1 ? x(points.length - 1) - x(0) : 0;
  const needsPan = contentWidth > availWidth;
  const minPan = needsPan ? Math.min(0, width - pad.right - x(points.length - 1)) : 0;
  const basePan = needsPan ? Math.max(minPan, Math.min(0, width * .5 - x(todayIndex >= 0 ? todayIndex : 0))) : 0;
  const panX = needsPan ? Math.max(minPan, Math.min(0, basePan + panDelta)) : 0;
  const actualLinePoints = todayIndex >= 0
    ? points.slice(0, todayIndex + 1).map((point, index) => [x(index), y(point.value)] as [number, number])
    : points.map((point, index) => [x(index), y(point.value)] as [number, number]);
  const futureLinePoints = todayIndex >= 0
    ? points.slice(todayIndex).map((point, index) => [x(todayIndex + index), y(point.value)] as [number, number])
    : [];
  const gridValues = [0.25, 0.5, 0.75, 1];
  const labelEvery = points.length <= 31 ? 1 : Math.ceil(points.length / 14);
  const showValueLabels = points.length <= 45;
  const hoveredPoint = hoveredIndex === null ? null : points[hoveredIndex];
  const tooltipX = hoveredIndex === null ? 0 : Math.min(Math.max(x(hoveredIndex) + panX, 80), width - 80) - panX;
  const tooltipY = hoveredPoint ? Math.max(y(hoveredPoint.value) - 56, 8) : 0;

  useEffect(() => {
    setPanDelta(0);
    setHoveredIndex(null);
  }, [historyDays, todayPoint]);

  const shiftChart = (direction: -1 | 1) => {
    setPanDelta(current => {
      const next = current + direction * 210;
      return Math.max(minPan - basePan, Math.min(-basePan, next));
    });
  };

  const rangeLabel = historyDays === "all" ? "全部" : `${historyDays}天`;
  const lastIdx = points.length - 1;

  return (
    <div className="chart-wrap">
      <svg className="trend-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`近${rangeLabel}客流预测趋势`} onMouseLeave={() => setHoveredIndex(null)}>
        {gridValues.map(rate => {
          const gridY = pad.top + (1 - rate) * (height - pad.top - pad.bottom);
          return <line key={rate} x1={pad.left} x2={width - pad.right} y1={gridY} y2={gridY} className="chart-grid" />;
        })}

        <g className="chart-pan-layer" style={{ transform: `translateX(${panX}px)` }}>
          <path d={smoothPath(actualLinePoints)} className="actual-line" />
          {futureLinePoints.length > 0 && <path d={smoothPath(futureLinePoints)} className="forecast-line" />}

          {todayIndex >= 0 && (
            <line x1={x(todayIndex)} x2={x(todayIndex)} y1={pad.top - 5} y2={height - pad.bottom} className="today-line" />
          )}

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
              {showValueLabels && (
                <text x={x(index)} y={y(point.value) - 12} textAnchor="middle" className="chart-value">{point.value.toLocaleString()}</text>
              )}
            </g>
          ))}

          {points.map((point, index) => {
            if (!(index % labelEvery === 0 || index === todayIndex || index === lastIdx)) return null;
            // 首尾标签调整锚点，避免被容器边缘截断
            const anchor = index === 0 ? "start" : index === lastIdx ? "end" : "middle";
            return (
              <text key={point.fullLabel} x={x(index)} y={height - 12} textAnchor={anchor} className={point.kind === "today" ? "chart-label today-label" : "chart-label"}>{point.label}</text>
            );
          })}

          {hoveredPoint && (
            <g className="chart-tooltip" transform={`translate(${tooltipX - 58} ${tooltipY})`}>
              <rect width="116" height="42" rx="7" />
              <text x="10" y="16">{hoveredPoint.kind === "today" ? "今天预测" : hoveredPoint.fullLabel}</text>
              <text x="10" y="32" className="tooltip-value">{hoveredPoint.value.toLocaleString()} 人</text>
            </g>
          )}
        </g>
      </svg>
      {needsPan && (
        <>
          <button className="chart-pan-zone chart-pan-left" type="button" aria-label="查看更早的历史日期" onClick={() => shiftChart(1)}><span>‹</span></button>
          <button className="chart-pan-zone chart-pan-right" type="button" aria-label="查看更远的未来日期" onClick={() => shiftChart(-1)}><span>›</span></button>
        </>
      )}
    </div>
  );
}
