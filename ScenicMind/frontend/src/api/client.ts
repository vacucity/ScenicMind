const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export function getAccessToken() { return window.localStorage.getItem("scenicmind.accessToken"); }

export async function apiRequest<T>(path: string, options: RequestInit = {}, token = getAccessToken()): Promise<T> {
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(`${apiBaseUrl}${path}`, { ...options, headers });
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try { const payload = await response.json() as { detail?: string }; if (payload.detail) message = payload.detail; } catch { /* not JSON */ }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

