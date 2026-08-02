// src/lib/stockglass_api.ts
// Production API Client for StockGlass AI Contract v1 (Zero Client-Side Mock Data)
import { API_BASE_URL, API_BASE_URL_ERROR } from "./config";
import { authFetch, authFetchStrict } from "./auth";
import {
  DualHorizonResponse,
  FullFactorBreakdown,
  FactorAuditPayload,
  IndexItem,
  PortfolioOptimizationResponse,
  PortfolioScoreResponse,
  PositionItem,
  PositionListResponse,
  StockDetail,
  StockListResponse,
  StockSynthesis,
} from "@/types/stockglass";

const DEFAULT_HEADERS: HeadersInit = {
  "Content-Type": "application/json",
  "X-API-Key": "dev_key",
};

async function readBackendErrorMessage(res: Response): Promise<string | null> {
  try {
    const body = await res.clone().json();
    const nestedMessage = body?.error?.message;
    if (typeof nestedMessage === "string" && nestedMessage.trim()) {
      return nestedMessage.trim();
    }
    const detailMessage = body?.detail?.message;
    if (typeof detailMessage === "string" && detailMessage.trim()) {
      return detailMessage.trim();
    }
  } catch {
    // Response is not JSON; ignore and use generic fallback.
  }
  return null;
}

function requireApiBaseUrl(): string {
  if (API_BASE_URL_ERROR) {
    throw new Error(API_BASE_URL_ERROR);
  }
  return API_BASE_URL;
}

export async function fetchIndices(): Promise<IndexItem[]> {
  const targetUrl = `${requireApiBaseUrl()}/indices`;
  console.log("[FLOW: Frontend API] ──> fetchIndices: Requesting GET", targetUrl);
  const res = await authFetch(targetUrl, {
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── fetchIndices FAILED HTTP", res.status);
    throw new Error(`Failed to fetch indices (HTTP ${res.status})`);
  }
  return res.json();
}

export interface FetchStocksParams {
  list?: "list1" | "list2";
  sector?: string;
  minScore?: number;
  direction?: "gainers" | "losers";
  q?: string;
  earningsSoon?: boolean;
  riskBucket?: string;
  page?: number;
  pageSize?: number;
}

export async function fetchStocks(params: FetchStocksParams = {}): Promise<StockListResponse> {
  const url = new URL(`${requireApiBaseUrl()}/stocks`);
  if (params.list) url.searchParams.append("list", params.list);
  if (params.sector) url.searchParams.append("sector", params.sector);
  if (params.minScore !== undefined) url.searchParams.append("minScore", params.minScore.toString());
  if (params.direction) url.searchParams.append("direction", params.direction);
  if (params.q) url.searchParams.append("q", params.q);
  if (params.earningsSoon !== undefined) url.searchParams.append("earningsSoon", params.earningsSoon.toString());
  if (params.riskBucket) url.searchParams.append("riskBucket", params.riskBucket);
  if (params.page !== undefined) url.searchParams.append("page", params.page.toString());
  if (params.pageSize !== undefined) url.searchParams.append("pageSize", params.pageSize.toString());

  console.log("[FLOW: Frontend API] ──> fetchStocks: Requesting GET", url.toString());
  const res = await authFetch(url.toString(), {
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── fetchStocks FAILED HTTP", res.status);
    throw new Error(`Failed to fetch stock list (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchStockDetail(symbol: string): Promise<StockDetail> {
  const targetUrl = `${requireApiBaseUrl()}/stocks/${encodeURIComponent(symbol)}`;
  console.log("[FLOW: Frontend API] ──> fetchStockDetail: Requesting GET", targetUrl);
  const res = await authFetch(targetUrl, {
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── fetchStockDetail FAILED HTTP", res.status);
    throw new Error(`Failed to fetch stock detail for ${symbol} (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchStockSynthesis(symbol: string): Promise<StockSynthesis> {
  const targetUrl = `${requireApiBaseUrl()}/stocks/${encodeURIComponent(symbol)}/synthesis`;
  console.log("[FLOW: Frontend API] ──> fetchStockSynthesis: Requesting GET", targetUrl);
  const res = await authFetch(targetUrl, {
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── fetchStockSynthesis FAILED HTTP", res.status);
    throw new Error(`Failed to fetch synthesis for ${symbol} (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchStockFactors(symbol: string): Promise<FullFactorBreakdown> {
  const targetUrl = `${requireApiBaseUrl()}/stocks/${encodeURIComponent(symbol)}/factors`;
  console.log("[FLOW: Frontend API] ──> fetchStockFactors: Requesting GET", targetUrl);
  const res = await authFetch(targetUrl, {
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── fetchStockFactors FAILED HTTP", res.status);
    throw new Error(`Failed to fetch factors for ${symbol} (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchStockFactorAudit(symbol: string): Promise<FactorAuditPayload> {
  const targetUrl = `${requireApiBaseUrl()}/stocks/${encodeURIComponent(symbol)}/factor-audit?forceLive=true&requireAllLive=false`;
  console.log("[FLOW: Frontend API] ──> fetchStockFactorAudit: Requesting GET", targetUrl);
  const res = await authFetch(targetUrl, {
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── fetchStockFactorAudit FAILED HTTP", res.status);
    throw new Error(`Failed to fetch factor audit for ${symbol} (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchDualHorizonLists(): Promise<DualHorizonResponse> {
  const targetUrl = `${requireApiBaseUrl()}/stocks/dual-horizon`;
  console.log("[FLOW: Frontend API] ──> fetchDualHorizonLists: Requesting GET", targetUrl);
  const res = await authFetch(targetUrl, {
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── fetchDualHorizonLists FAILED HTTP", res.status);
    if (res.status === 404) {
      throw new Error(`Dual-horizon endpoint not found at ${targetUrl}. Check NEXT_PUBLIC_API_URL and backend route deployment.`);
    }
    throw new Error(`Failed to fetch dual-horizon lists from ${targetUrl} (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchPortfolioScore(): Promise<PortfolioScoreResponse> {
  const targetUrl = `${requireApiBaseUrl()}/portfolio/score`;
  console.log("[FLOW: Frontend API] ──> fetchPortfolioScore: Requesting GET", targetUrl);
  const res = await authFetchStrict(targetUrl, {
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── fetchPortfolioScore FAILED HTTP", res.status);
    const backendMessage = await readBackendErrorMessage(res);
    if (backendMessage && backendMessage.toLowerCase().includes("database connection failed")) {
      throw new Error("Database unavailable. Check backend DATABASE_URL / host DNS resolution and retry.");
    }
    if (res.status === 404) {
      throw new Error(`Portfolio score endpoint not found at ${targetUrl}. Check NEXT_PUBLIC_API_URL and backend route deployment.`);
    }
    if (res.status === 401 || res.status === 403) {
      throw new Error("Portfolio score requires a valid logged-in session. Please log in again.");
    }
    throw new Error(`Failed to fetch portfolio score from ${targetUrl} (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchPortfolioOptimization(cadence: "weekly" | "regime_shift" = "weekly"): Promise<PortfolioOptimizationResponse> {
  const targetUrl = `${requireApiBaseUrl()}/portfolio/optimize?cadence=${encodeURIComponent(cadence)}`;
  console.log("[FLOW: Frontend API] ──> fetchPortfolioOptimization: Requesting GET", targetUrl);
  const res = await authFetchStrict(targetUrl, {
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── fetchPortfolioOptimization FAILED HTTP", res.status);
    const backendMessage = await readBackendErrorMessage(res);
    if (backendMessage && backendMessage.toLowerCase().includes("database connection failed")) {
      throw new Error("Database unavailable. Check backend DATABASE_URL / host DNS resolution and retry.");
    }
    if (res.status === 404) {
      throw new Error(`Portfolio optimization endpoint not found at ${targetUrl}. Check NEXT_PUBLIC_API_URL and backend route deployment.`);
    }
    if (res.status === 401 || res.status === 403) {
      throw new Error("Portfolio optimization requires a valid logged-in session. Please log in again.");
    }
    throw new Error(`Failed to fetch portfolio optimization from ${targetUrl} (HTTP ${res.status})`);
  }
  return res.json();
}

export async function createPaperPosition(input: { symbol: string; qty: number; entryPrice: number }): Promise<PositionItem> {
  const targetUrl = `${requireApiBaseUrl()}/positions`;
  console.log("[FLOW: Frontend API] ──> createPaperPosition: Requesting POST", targetUrl);
  const res = await authFetchStrict(targetUrl, {
    method: "POST",
    headers: DEFAULT_HEADERS,
    cache: "no-store",
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── createPaperPosition FAILED HTTP", res.status);
    const backendMessage = await readBackendErrorMessage(res);
    if (backendMessage && backendMessage.toLowerCase().includes("database connection failed")) {
      throw new Error("Database unavailable. Cannot create paper position until DB connectivity is restored.");
    }
    throw new Error(`Failed to create paper position (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchPaperPositions(status?: "open" | "closed"): Promise<PositionListResponse> {
  const targetUrl = new URL(`${requireApiBaseUrl()}/positions`);
  if (status) {
    targetUrl.searchParams.append("status", status);
  }
  console.log("[FLOW: Frontend API] ──> fetchPaperPositions: Requesting GET", targetUrl.toString());
  const res = await authFetchStrict(targetUrl.toString(), {
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── fetchPaperPositions FAILED HTTP", res.status);
    const backendMessage = await readBackendErrorMessage(res);
    if (backendMessage && backendMessage.toLowerCase().includes("database connection failed")) {
      throw new Error("Database unavailable. Cannot load paper positions until DB connectivity is restored.");
    }
    throw new Error(`Failed to fetch paper positions (HTTP ${res.status})`);
  }
  return res.json();
}

export async function closePaperPosition(positionId: string): Promise<PositionItem> {
  const targetUrl = `${requireApiBaseUrl()}/positions/${encodeURIComponent(positionId)}`;
  console.log("[FLOW: Frontend API] ──> closePaperPosition: Requesting DELETE", targetUrl);
  const res = await authFetchStrict(targetUrl, {
    method: "DELETE",
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── closePaperPosition FAILED HTTP", res.status);
    const backendMessage = await readBackendErrorMessage(res);
    if (backendMessage && backendMessage.toLowerCase().includes("database connection failed")) {
      throw new Error("Database unavailable. Cannot close paper position until DB connectivity is restored.");
    }
    throw new Error(`Failed to close paper position (HTTP ${res.status})`);
  }
  return res.json();
}
