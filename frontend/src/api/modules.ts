export type ModuleName = "module-one" | "module-two";

export type ModuleOutput<TData = unknown> = {
  generatedAt: string;
  data: TData;
  text: string | null;
};

export type ForecastPoint = {
  date: string;
  predictedVisitors: number;
  p90Visitors: number;
  capacity: number;
  actualVisitors: number | null;
};

export type FeatureDriver = {
  feature: string;
  label: string;
  contributionVisitors: number;
  direction: "positive" | "negative";
  explanation: string;
};

export type ModuleTwoReport = {
  reportId: string;
  title: string;
  spotId: string;
  spotName: string;
  periodLabel: string;
  executiveSummary: string;
  kpis: {
    forecastTotal: number;
    peakDate: string;
    peakVisitors: number;
    peakCapacityRate: number;
    riskLevel: "低" | "中" | "高";
    confidence: number;
  };
  forecast: ForecastPoint[];
  drivers: FeatureDriver[];
  visitorInsight: {
    sampleScope: string;
    commentCount: number;
    confidence: "低" | "中" | "高";
    sentiments: Array<{ label: string; count: number; share: number }>;
    topTopics: Array<{ label: string; count: number; share: number }>;
    evidence: Array<{
      evidenceId: string;
      category: string;
      sentiment: string;
      impactScore: number;
      quote: string;
      sourceUrl: string;
    }>;
  };
  recommendations: Array<{
    recommendationId: string;
    priority: "高" | "中" | "低";
    category: string;
    title: string;
    action: string;
    rationale: string;
    expectedImpact: string;
    evidenceRefs: string[];
    status: "待评估" | "已采纳";
  }>;
  guardrails: string[];
  trace: {
    modelVersion: string;
    dataSnapshot: string;
    insightSource: string;
    generationMode: string;
    promptVersion: string;
  };
};

export type ModuleOneData = {
  spotId: string;
  spotName: string;
  capacity: number;
  today: {
    date: string;
    predicted: number;
    rangeLow: number;
    rangeHigh: number;
    level: "较低" | "正常" | "较高";
    entered: number;
    enteredTime: string;
    enteredWow: string;
  };
  history: Array<{ date: string; visitors: number }>;
  forecast: Array<{
    date: string;
    predicted: number;
    p90: number;
    level: "较低" | "正常" | "较高";
  }>;
  week: Array<{ day: string; value: number; level: "较低" | "正常" | "较高" }>;
  demo: boolean;
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

export async function getModuleOutput<TData = unknown>(module: ModuleName): Promise<ModuleOutput<TData>> {
  const response = await fetch(`${apiBaseUrl}/api/v1/${module}/output`);

  if (!response.ok) {
    throw new Error(`${module} request failed: ${response.status}`);
  }

  return response.json() as Promise<ModuleOutput<TData>>;
}

export async function getModuleTwoOutput(spot: string): Promise<ModuleOutput<ModuleTwoReport>> {
  const response = await fetch(`${apiBaseUrl}/api/v1/module-two/output?spot=${encodeURIComponent(spot)}`);
  if (!response.ok) {
    throw new Error(`经营报告请求失败：${response.status}`);
  }
  return response.json() as Promise<ModuleOutput<ModuleTwoReport>>;
}

export async function getModuleOneOutput(spot: string): Promise<ModuleOutput<ModuleOneData>> {
  const response = await fetch(`${apiBaseUrl}/api/v1/module-one/output?spot=${encodeURIComponent(spot)}`);
  if (!response.ok) {
    throw new Error(`客流预测请求失败：${response.status}`);
  }
  return response.json() as Promise<ModuleOutput<ModuleOneData>>;
}

export async function getModuleTwoSpots(): Promise<string[]> {
  const response = await fetch(`${apiBaseUrl}/api/v1/module-two/spots`);
  if (!response.ok) {
    throw new Error(`景点列表请求失败：${response.status}`);
  }
  const result = (await response.json()) as { spots: string[] };
  return result.spots;
}

export type AgentEvidence = {
  type: "driver" | "voice" | "metric" | "knowledge";
  label: string;
  value: string;
  ref: string;
};

export type AgentAttribution = {
  feature: string;
  label: string;
  shap: number;
  pct: number;
  direction: "positive" | "negative";
  confidence: "high" | "medium" | "low";
  explanation: string;
};

export type AgentReport = {
  spot: string;
  title: string;
  accuracy: {
    mapeDaily: number;
    mapeThreshold: number;
    passed: boolean;
    modelStatus: string;
    driftDays: string[];
  };
  attribution: AgentAttribution[];
  reportConfidence: number;
  recommendations: Array<{
    recommendationId: string;
    priority: "高" | "中" | "低";
    category: string;
    title: string;
    action: string;
    rationale: string;
    expectedImpact: string;
    evidenceRefs: string[];
    status: "待评估" | "已采纳";
  }>;
  risk: {
    peakDate: string;
    peakCapacityRate: number;
    peakVisitors: number;
    riskLevel: string;
  };
};

export type AgentChatResponse = {
  reply: string;
  intent: string;
  spot: string;
  evidence: AgentEvidence[];
  suggestions: string[];
  trace: {
    agentVersion: string;
    intentSource: string;
    generationMode: string;
    evidenceBound: boolean;
  };
};

export async function getAgentReport(spot: string): Promise<AgentReport> {
  const response = await fetch(`${apiBaseUrl}/api/v1/agent/report?spot=${encodeURIComponent(spot)}`);
  if (!response.ok) {
    throw new Error(`Agent 报告请求失败：${response.status}`);
  }
  return response.json() as Promise<AgentReport>;
}

export async function agentChat(message: string, spot: string, sessionId?: string): Promise<AgentChatResponse> {
  const response = await fetch(`${apiBaseUrl}/api/v1/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, spot, sessionId }),
  });
  if (!response.ok) {
    throw new Error(`Agent 请求失败：${response.status}`);
  }
  return response.json() as Promise<AgentChatResponse>;
}
