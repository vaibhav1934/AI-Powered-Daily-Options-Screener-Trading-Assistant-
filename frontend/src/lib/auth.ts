// src/lib/auth.ts
// Client-side authentication service for StockGlass AI (JWT Access & Refresh Token Management)
import { API_BASE_URL, API_BASE_URL_ERROR } from "./config";

export interface UserProfile {
  username: string;
  is_active: boolean;
  created_at?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

const DEV_API_KEY = "dev_key";

const ACCESS_TOKEN_KEY = "stockglass_access_token";
const REFRESH_TOKEN_KEY = "stockglass_refresh_token";
const USER_PROFILE_KEY = "stockglass_user_profile";

function requireApiBaseUrl(): string {
  if (API_BASE_URL_ERROR) {
    throw new Error(API_BASE_URL_ERROR);
  }
  return API_BASE_URL;
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function getStoredUser(): UserProfile | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_PROFILE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as UserProfile;
  } catch {
    return null;
  }
}

export function isAuthenticated(): boolean {
  return !!getAccessToken() && !!getStoredUser();
}

export function setAuthTokens(tokens: TokenResponse, user?: UserProfile): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
  if (user) {
    localStorage.setItem(USER_PROFILE_KEY, JSON.stringify(user));
  }
}

export function logout(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_PROFILE_KEY);
  window.dispatchEvent(new Event("stockglass_auth_changed"));
}

export async function loginUser(username: string, password: string): Promise<UserProfile> {
  const baseUrl = requireApiBaseUrl();
  const res = await fetch(`${baseUrl}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (!res.ok) {
    let errMsg = "Invalid username or password";
    try {
      const errJson = await res.json();
      if (errJson.error?.message) errMsg = errJson.error.message;
    } catch {}
    throw new Error(errMsg);
  }

  const tokens: TokenResponse = await res.json();
  setAuthTokens(tokens);

  const profile = await fetchCurrentUser(tokens.access_token);
  setAuthTokens(tokens, profile);
  window.dispatchEvent(new Event("stockglass_auth_changed"));
  return profile;
}

export async function registerUser(username: string, password: string): Promise<UserProfile> {
  const baseUrl = requireApiBaseUrl();
  const res = await fetch(`${baseUrl}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (!res.ok) {
    let errMsg = "Registration failed";
    try {
      const errJson = await res.json();
      if (errJson.error?.message) errMsg = errJson.error.message;
    } catch {}
    throw new Error(errMsg);
  }

  const tokens: TokenResponse = await res.json();
  setAuthTokens(tokens);
  const profile = await fetchCurrentUser(tokens.access_token);
  setAuthTokens(tokens, profile);
  window.dispatchEvent(new Event("stockglass_auth_changed"));
  return profile;
}

export async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    logout();
    return null;
  }

  try {
    const baseUrl = requireApiBaseUrl();
    const res = await fetch(`${baseUrl}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) {
      logout();
      return null;
    }

    const tokens: TokenResponse = await res.json();
    const existingUser = getStoredUser();
    setAuthTokens(tokens, existingUser || undefined);
    return tokens.access_token;
  } catch (err) {
    console.error("[Auth] Token refresh failed:", err);
    logout();
    return null;
  }
}

export async function fetchCurrentUser(tokenOverride?: string): Promise<UserProfile> {
  const token = tokenOverride || getAccessToken();
  if (!token) throw new Error("No access token available");
  const baseUrl = requireApiBaseUrl();

  const res = await fetch(`${baseUrl}/auth/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });

  if (!res.ok) {
    if (res.status === 401 && !tokenOverride) {
      const newToken = await refreshAccessToken();
      if (newToken) return fetchCurrentUser(newToken);
    }
    throw new Error("Failed to verify user profile");
  }

  const profile: UserProfile = await res.json();
  if (typeof window !== "undefined") {
    localStorage.setItem(USER_PROFILE_KEY, JSON.stringify(profile));
  }
  return profile;
}

export async function authFetch(url: string | URL, options: RequestInit = {}): Promise<Response> {
  let token = getAccessToken();
  const headers = new Headers(options.headers || {});
  
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  } else if (!token && !headers.has("Authorization") && !headers.has("X-API-Key")) {
    headers.set("X-API-Key", DEV_API_KEY);
  }

  let res = await fetch(url, { ...options, headers });

  if (res.status === 401 && token) {
    console.log("[Auth] 401 Unauthorized encountered. Attempting token refresh...");
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers.set("Authorization", `Bearer ${newToken}`);
      res = await fetch(url, { ...options, headers });
    }
  }

  return res;
}

export async function authFetchStrict(url: string | URL, options: RequestInit = {}): Promise<Response> {
  let token = getAccessToken();
  if (!token) {
    throw new Error("Login required");
  }

  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${token}`);
  headers.delete("X-API-Key");

  let res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    const newToken = await refreshAccessToken();
    if (!newToken) {
      throw new Error("Login required");
    }

    token = newToken;
    headers.set("Authorization", `Bearer ${token}`);
    res = await fetch(url, { ...options, headers });
  }

  if (res.status === 401) {
    throw new Error("Login required");
  }

  return res;
}
