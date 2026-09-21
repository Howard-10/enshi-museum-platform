import { API_BASE_URL } from "./client";
import { clearAuthSession, saveAuthSession } from "../auth/session";
import type { AuthResponse, AuthUser } from "../types/auth";

async function readAuthResponse(response: Response): Promise<AuthResponse> {
  if (response.ok) return response.json() as Promise<AuthResponse>;
  let message = "登录服务暂时不可用，请稍后重试。";
  try {
    const payload = (await response.json()) as { detail?: string };
    if (payload.detail) message = payload.detail;
  } catch {
    // Keep the visitor-facing fallback when the server does not return JSON.
  }
  throw new Error(message);
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return saveAuthSession(await readAuthResponse(response));
}

export async function register(email: string, password: string, displayName: string): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, display_name: displayName }),
  });
  return saveAuthSession(await readAuthResponse(response));
}

export async function getCurrentUser(): Promise<AuthUser> {
  const token = window.localStorage.getItem("enshi-auth-token");
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    clearAuthSession();
    throw new Error("登录已失效，请重新登录。");
  }
  return response.json() as Promise<AuthUser>;
}
