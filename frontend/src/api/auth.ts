import { apiRequest } from "./client";

export type ApiUser = { id: number; username: string; email: string };
export type AuthResponse = { accessToken: string; tokenType: string; user: ApiUser };

export const register = (payload: { username: string; email: string; password: string }) =>
  apiRequest<AuthResponse>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(payload) }, null);
export const login = (payload: { username: string; password: string }) =>
  apiRequest<AuthResponse>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(payload) }, null);
export const logout = (token: string) => apiRequest<void>("/api/v1/auth/logout", { method: "POST" }, token);
export const me = () => apiRequest<ApiUser>("/api/v1/auth/me");

