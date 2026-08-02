// src/lib/stockglass_api.ts
// Production API Client for StockGlass AI Contract v1 (Zero Client-Side Mock Data)
import { API_BASE_URL } from "./config";
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

export async function fetchIndices(): Promise<IndexItem[]> {
  const targetUrl = `${API_BASE_URL}/indices`;
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
  const url = new URL(`${API_BASE_URL}/stocks`);
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
  const targetUrl = `${API_BASE_URL}/stocks/${encodeURIComponent(symbol)}`;
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
  const targetUrl = `${API_BASE_URL}/stocks/${encodeURIComponent(symbol)}/synthesis`;
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
  const targetUrl = `${API_BASE_URL}/stocks/${encodeURIComponent(symbol)}/factors`;
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
  const targetUrl = `${API_BASE_URL}/stocks/${encodeURIComponent(symbol)}/factor-audit?forceLive=true&requireAllLive=false`;
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
  const targetUrl = `${API_BASE_URL}/stocks/dual-horizon`;
  console.log("[FLOW: Frontend API] ──> fetchDualHorizonLists: Requesting GET", targetUrl);
  const res = await authFetch(targetUrl, {
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── fetchDualHorizonLists FAILED HTTP", res.status);
    throw new Error(`Failed to fetch dual-horizon lists (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchPortfolioScore(): Promise<PortfolioScoreResponse> {
  const targetUrl = `${API_BASE_URL}/portfolio/score`;
  console.log("[FLOW: Frontend API] ──> fetchPortfolioScore: Requesting GET", targetUrl);
  const res = await authFetchStrict(targetUrl, {
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── fetchPortfolioScore FAILED HTTP", res.status);
    throw new Error(`Failed to fetch portfolio score (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchPortfolioOptimization(cadence: "weekly" | "regime_shift" = "weekly"): Promise<PortfolioOptimizationResponse> {
  const targetUrl = `${API_BASE_URL}/portfolio/optimize?cadence=${encodeURIComponent(cadence)}`;
  console.log("[FLOW: Frontend API] ──> fetchPortfolioOptimization: Requesting GET", targetUrl);
  const res = await authFetchStrict(targetUrl, {
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── fetchPortfolioOptimization FAILED HTTP", res.status);
    throw new Error(`Failed to fetch portfolio optimization (HTTP ${res.status})`);
  }
  return res.json();
}

export async function createPaperPosition(input: { symbol: string; qty: number; entryPrice: number }): Promise<PositionItem> {
  const targetUrl = `${API_BASE_URL}/positions`;
  console.log("[FLOW: Frontend API] ──> createPaperPosition: Requesting POST", targetUrl);
  const res = await authFetchStrict(targetUrl, {
    method: "POST",
    headers: DEFAULT_HEADERS,
    cache: "no-store",
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── createPaperPosition FAILED HTTP", res.status);
    throw new Error(`Failed to create paper position (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchPaperPositions(status?: "open" | "closed"): Promise<PositionListResponse> {
  const targetUrl = new URL(`${API_BASE_URL}/positions`);
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
    throw new Error(`Failed to fetch paper positions (HTTP ${res.status})`);
  }
  return res.json();
}

export async function closePaperPosition(positionId: string): Promise<PositionItem> {
  const targetUrl = `${API_BASE_URL}/positions/${encodeURIComponent(positionId)}`;
  console.log("[FLOW: Frontend API] ──> closePaperPosition: Requesting DELETE", targetUrl);
  const res = await authFetchStrict(targetUrl, {
    method: "DELETE",
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── closePaperPosition FAILED HTTP", res.status);
    throw new Error(`Failed to close paper position (HTTP ${res.status})`);
  }
  return res.json();
}
