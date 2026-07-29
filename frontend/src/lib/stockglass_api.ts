// src/lib/stockglass_api.ts
// Production API Client for StockGlass AI Contract v1 (Zero Client-Side Mock Data)
import { API_BASE_URL } from "./config";
import {
  IndexItem,
  StockListResponse,
  StockDetail,
  StockSynthesis,
  FullFactorBreakdown,
} from "@/types/stockglass";

const DEFAULT_HEADERS = {
  "Content-Type": "application/json",
  "X-API-Key": "dev_key",
};

export async function fetchIndices(): Promise<IndexItem[]> {
  console.log("[FLOW: Frontend API] ──> fetchIndices: Requesting GET", `${API_BASE_URL}/indices`);
  const res = await fetch(`${API_BASE_URL}/indices`, {
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── fetchIndices FAILED HTTP", res.status);
    throw new Error(`Failed to fetch indices (HTTP ${res.status})`);
  }
  const data = await res.json();
  console.log("[FLOW: Frontend API] <── fetchIndices: Received", data.length, "index proxies");
  return data;
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
  const res = await fetch(url.toString(), {
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── fetchStocks FAILED HTTP", res.status);
    throw new Error(`Failed to fetch stock list (HTTP ${res.status})`);
  }
  const data = await res.json();
  console.log("[FLOW: Frontend API] <── fetchStocks: Received", data.results?.length ?? 0, "stocks (Total:", data.total, ")");
  return data;
}

export async function fetchStockDetail(symbol: string): Promise<StockDetail> {
  const targetUrl = `${API_BASE_URL}/stocks/${encodeURIComponent(symbol)}`;
  console.log("[FLOW: Frontend API] ──> fetchStockDetail: Requesting GET", targetUrl);
  const res = await fetch(targetUrl, {
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── fetchStockDetail FAILED HTTP", res.status);
    throw new Error(`Failed to fetch stock detail for ${symbol} (HTTP ${res.status})`);
  }
  const data = await res.json();
  console.log("[FLOW: Frontend API] <── fetchStockDetail: Received detail for", data.symbol, "with score", data.score);
  return data;
}

export async function fetchStockSynthesis(symbol: string): Promise<StockSynthesis> {
  const targetUrl = `${API_BASE_URL}/stocks/${encodeURIComponent(symbol)}/synthesis`;
  console.log("[FLOW: Frontend API] ──> fetchStockSynthesis: Requesting GET", targetUrl);
  const res = await fetch(targetUrl, {
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── fetchStockSynthesis FAILED HTTP", res.status);
    throw new Error(`Failed to fetch synthesis for ${symbol} (HTTP ${res.status})`);
  }
  const data = await res.json();
  console.log("[FLOW: Frontend API] <── fetchStockSynthesis: Received synthesis for", data.symbol);
  return data;
}

export async function fetchStockFactors(symbol: string): Promise<FullFactorBreakdown> {
  const targetUrl = `${API_BASE_URL}/stocks/${encodeURIComponent(symbol)}/factors`;
  console.log("[FLOW: Frontend API] ──> fetchStockFactors: Requesting GET", targetUrl);
  const res = await fetch(targetUrl, {
    headers: DEFAULT_HEADERS,
    cache: "no-store",
  });
  if (!res.ok) {
    console.error("[FLOW: Frontend API] <── fetchStockFactors FAILED HTTP", res.status);
    throw new Error(`Failed to fetch factors for ${symbol} (HTTP ${res.status})`);
  }
  const data = await res.json();
  console.log("[FLOW: Frontend API] <── fetchStockFactors: Received 50-factor log for", data.symbol);
  return data;
}
