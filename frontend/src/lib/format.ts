import type { ModuleOneData } from "../api/modules";

export const numberFormatter = new Intl.NumberFormat("zh-CN");

export type ChartPoint = {
  label: string;
  fullLabel: string;
  value: number;
  kind: "history" | "today" | "forecast";
};

export function parseDate(iso: string): Date {
  return new Date(`${iso}T00:00:00`);
}

export function shortLabel(iso: string): string {
  const date = parseDate(iso);
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

export function chineseDate(iso: string): string {
  const date = parseDate(iso);
  const weekdays = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日 · ${weekdays[date.getDay()]}`;
}

export function truncate(text: string, limit = 34): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  return normalized.length <= limit ? normalized : `${normalized.slice(0, limit)}…`;
}

export function buildChartPoints(one: ModuleOneData) {
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