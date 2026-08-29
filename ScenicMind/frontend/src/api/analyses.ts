import { apiRequest } from "./client";

export type ChartPoint = { date: string; actualVisitors: number | null; predictedVisitors: number | null; kind: "actual" | "forecast" };
export type AvailabilityItem = { label: string; status: "uploaded" | "requires_source"; source: string | null; columns: string[] };
export type AnalysisResult = {
  source: { fileName: string; rowCount: number; startDate: string; endDate: string; warnings: string[] };
  model: { name: string; version: string };
  latestActual: { date: string; visitors: number };
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
  feature_importance?: FeatureImportanceItem[];
  semantic_groups?: SemanticImportanceGroup[];
};

export async function uploadAnalysis(file: File) {
  const body = new FormData(); body.append("file", file);
  return apiRequest<AnalysisEnvelope>("/api/v1/analyses", { method: "POST", body });
}
export const getLatestAnalysis = () => apiRequest<AnalysisEnvelope>("/api/v1/analyses/latest");
export const getAnalysis = (id: string) => apiRequest<AnalysisEnvelope>(`/api/v1/analyses/${id}`);
export const getImportance = (id: string) => apiRequest<ImportancePayload>(`/api/v1/analyses/${id}/importance`);
