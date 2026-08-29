import * as authApi from "../../../api/auth";
import type { ApiUser } from "../../../api/auth";

export type UserSession = ApiUser;
const TOKEN_KEY = "scenicmind.accessToken";
const USER_KEY = "scenicmind.user";

function saveSession(accessToken: string, user: ApiUser) {
  window.localStorage.setItem(TOKEN_KEY, accessToken);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export async function registerUser(user: { username: string; email: string; password: string }) {
  const response = await authApi.register(user);
  await authApi.logout(response.accessToken).catch(() => undefined);
}

export async function signIn(username: string, password: string): Promise<UserSession> {
  const response = await authApi.login({ username, password });
  saveSession(response.accessToken, response.user);
  return response.user;
}

export function getSession(): UserSession | null {
  const raw = window.localStorage.getItem(USER_KEY);
  const token = window.localStorage.getItem(TOKEN_KEY);
  if (!raw || !token) return null;
  try { return JSON.parse(raw) as UserSession; }
  catch { clearSession(); return null; }
}

export function clearSession() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
  window.localStorage.removeItem("scenicmind.activeAnalysisId");
}

export async function signOut() {
  const token = window.localStorage.getItem(TOKEN_KEY);
  clearSession();
  if (token) await authApi.logout(token).catch(() => undefined);
}

