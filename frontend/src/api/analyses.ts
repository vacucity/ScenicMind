import { apiRequest } from "./client";

export type ChartPoint = { date: string; actualVisitors: number | null; predictedVisitors: number | null; kind: "actual" | "forecast" };
export type AvailabilityItem = { label: string; status: "uploaded" | "requires_source"; source: string | null; columns: string[] };
export type AnalysisResult = {
  source: { fileName: string; rowCount: number; startDate: string; endDate: string; warnings: string[] };
  model: { name: string; version: string };
  latestActual: { date: string; visitors: number; predictedVisitors: number | null };
  historyPoints: ChartPoint[];
  forecastPoints: ChartPoint[];
  horizons: Record<"7" | "14" | "30", { average: number; peak: number; minimum: number }>;
  metrics: { validationDays: number; mae: number | null; rmse: number | null; mape: number | null };
  dataAvailability: Record<string, AvailabilityItem>;
};
export type AnalysisEnvelope = { analysisId: string; status: "processing" | "completed" | "failed"; createdAt: string; error: string | null; result: AnalysisResult | null };
export type FeatureImportanceItem = { feature: string; importance: number; rank: number; group?: string };
export type SemanticImportanceGroup = { key: string; label: string; description: string; importance: number };
export type ImportancePayload = {
  model_version?: string;
  degraded?: boolean;
  degraded_reason?: string;
  feature_importance?: FeatureImportanceItem[];
  semantic_groups?: SemanticImportanceGroup[];
};

export async function uploadAnalysis(file: File) {
  const body = new FormData(); body.append("file", file);
  return apiRequest<AnalysisEnvelope>("/api/v1/analyses", { method: "POST", body });
}
export const getLatestAnalysis = () => apiRequest<AnalysisEnvelope>("/api/v1/analyses/latest");
export const getAnalysis = (id: string) => apiRequest<AnalysisEnvelope>(`/api/v1/analyses/${id}`);
export type AnalysisHistoryItem = { analysisId: string; fileName: string; status: string; error: string | null; createdAt: string; completedAt: string | null };
export const listAnalyses = () => apiRequest<AnalysisHistoryItem[]>("/api/v1/analyses");
export const getImportance = (id: string) => apiRequest<ImportancePayload>(`/api/v1/analyses/${id}/importance`);
export const getIndicators = (id: string) => apiRequest<Record<string, any>>(`/api/v1/analyses/${id}/indicators`);

export type AgentReportListItem = { reportId: string; analysisId: string; reportType: string; status: string; question: string | null; period: string | null; createdAt: string; completedAt: string | null };
export type AgentReport = AgentReportListItem & { markdown: string | null; progress: { stage: string; status: string; detail: string } | null };
export const createAgentReport = (analysisId: string, reportType: string, question?: string, period?: string) =>
  apiRequest<{ reportId: string; status: string }>("/api/v1/agent/report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ analysis_id: analysisId, report_type: reportType, question: question ?? null, period: period ?? null }),
  });
export const getAgentReport = (id: string) => apiRequest<AgentReport>(`/api/v1/agent/report/${id}`);
export const getAgentReports = () => apiRequest<AgentReportListItem[]>(`/api/v1/agent/reports`);
export const agentChat = (analysisId: string, question: string) =>
  apiRequest<{ answer: string }>("/api/v1/agent/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ analysis_id: analysisId, question }),
  });
