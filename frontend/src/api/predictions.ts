export type PredictionResult<TData = unknown> = {
  generatedAt: string;
  data: TData;
  text: string | null;
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

export async function getLatestPrediction<TData = unknown>(): Promise<PredictionResult<TData>> {
  const response = await fetch(`${apiBaseUrl}/api/v1/predictions/latest`);

  if (!response.ok) {
    throw new Error(`Prediction request failed: ${response.status}`);
  }

  return response.json() as Promise<PredictionResult<TData>>;
}
