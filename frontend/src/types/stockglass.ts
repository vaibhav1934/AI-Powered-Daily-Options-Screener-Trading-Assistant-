// src/types/stockglass.ts
// Pure TypeScript interfaces matching StockGlass AI Contract v1 Backend API Schema

export interface IndexItem {
  name: string;
  value: string;   // formatted string e.g. "5,432.11"
  chg: number;     // dollar change
  pct: number;     // percent change
}

export interface SupportResistanceLevels {
  support: number;
  resistance: number;
}

export interface StockListItem {
  symbol: string;
  name: string;
  sector: string;
  price: number;
  chg: number;           // dollar change
  pct: number;           // percent change
  volume: string;        // pre-formatted e.g. "25.4M"
  score: number;         // conviction score 0-10
  earningsSoon: boolean;
  hardFlags: string[];
  sparkline: number[];
  levels: SupportResistanceLevels;
  // Aliases for backwards compat with sort logic in page.tsx
  convictionScore?: number;
  changePercent?: number;
}

export interface StockListResponse {
  count: number;
  total: number;
  page?: number;
  page_size?: number;
  total_pages?: number;
  results: StockListItem[];
  // Alias for backwards compat
  items?: StockListItem[];
}

export interface LayerScoreItem {
  layer: string;
  value: number;
}

export interface ReasonItem {
  type: "bull" | "bear";
  code: string;
  text: string;
}

export interface NewsItem {
  headline: string;
  source: string;
  url: string;
  publishedAt: string;
}

export interface StockDetail {
  id?: number;
  symbol: string;
  name: string;
  sector: string;
  price: number;
  chg: number;
  pct: number;
  score: number;
  hardFlags: string[];
  levels: SupportResistanceLevels;
  layerScores: LayerScoreItem[];
  reasons: ReasonItem[];
  news: NewsItem[];
  newsSummary?: string | null;
  execution_details?: {
    entry_price?: number;
    strike_price?: number | null;
    stop_loss?: number;
  };
}

export interface FactorBreakdownItem {
  code: string;
  status: "pass" | "neutral" | "fail";
  detail: string;
}

export interface LayerBreakdownItem {
  layer: string;
  range: string;
  factors: FactorBreakdownItem[];
}

export interface FactorSummary {
  pass: number;
  neutral: number;
  fail: number;
}

export interface FullFactorBreakdown {
  symbol: string;
  summary: FactorSummary;
  layers: LayerBreakdownItem[];
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}
