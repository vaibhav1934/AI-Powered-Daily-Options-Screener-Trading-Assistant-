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

export interface StockSynthesis {
  symbol: string;
  reasons: ReasonItem[];
  newsSummary: string | null;
}

export interface TechnicalIndicatorData {
  support_resistance?: {
    support?: number;
    resistance?: number;
    level_type?: string;
  };
  moving_averages?: {
    sma_20?: number | null;
    sma_50?: number | null;
    sma_200?: number | null;
    ema_9?: number | null;
    ema_21?: number | null;
    golden_cross?: boolean;
    death_cross?: boolean;
    trend_alignment?: string;
  };
  momentum_oscillators?: {
    rsi?: number | null;
    rsi_state?: string;
    macd?: {
      macd_line?: number | null;
      signal_line?: number | null;
      histogram?: number | null;
      trend?: string;
    } | null;
    bollinger?: {
      upper?: number | null;
      middle?: number | null;
      lower?: number | null;
      bandwidth?: number | null;
    } | null;
    stochastic?: {
      k?: number | null;
      d?: number | null;
    } | null;
  };
  volume_metrics?: {
    volume?: string;
    avg_volume_20d?: string | number | null;
    relative_volume?: number | null;
    volume_profile_state?: string;
  };
  implied_volatility?: {
    iv_current?: number | null;
    iv_rank?: number | null;
    iv_percentile?: number | null;
    regime?: string;
  };
  options_greeks?: {
    delta?: number | null;
    gamma?: number | null;
    theta?: number | null;
    vega?: number | null;
    description?: string;
  };
  options_open_interest?: {
    put_call_ratio?: number | null;
    pcr_state?: string;
    total_call_oi?: number | null;
    total_put_oi?: number | null;
  };
  atr_volatility?: {
    atr_14?: number | null;
    atr_pct?: number | null;
  } | null;
  high_low_52w?: {
    high_52w?: number | null;
    low_52w?: number | null;
    dist_from_high_pct?: number | null;
    dist_from_low_pct?: number | null;
  };
  high_low_6m?: {
    high_6m?: number | null;
    low_6m?: number | null;
    period?: string;
  };
  beta_correlation?: {
    beta?: number | null;
    sector_correlation?: number | null;
    sp500_correlation?: number | null;
  };
  earnings_consensus?: {
    consensus_eps_range?: string;
    status?: string;
  };
  historical_seasonality?: {
    hist_vol_30d?: number | null;
    seasonality_stats?: string;
  };
  sector_relative_strength?: {
    sector?: string;
    rank?: string;
    relative_strength?: string;
  };
  news_catalysts?: Array<{
    headline: string;
    source: string;
    publishedAt: string;
    url: string;
  }>;
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
  volume?: string;
  hardFlags: string[];
  levels: SupportResistanceLevels;
  sma_200?: number | null;
  high_52w?: number | null;
  low_52w?: number | null;
  high_6m?: number | null;
  low_6m?: number | null;
  technicalIndicators?: TechnicalIndicatorData;
  layerScores: LayerScoreItem[];
  reasons: ReasonItem[];
  news: NewsItem[];
  newsSummary?: string | null;
  execution_details?: {
    entry_price?: number;
    strike_price?: number | null;
    stop_loss?: number;
  };
  dualFramework?: {
    tactical: {
      score?: number | null;
      regime_gate_pass: boolean;
      regime_fail_reasons: string[];
      catalyst_signals: string[];
      technical_signals: string[];
      options_signals: string[];
      conviction_tier?: string | null;
      sizing_cap?: string | null;
      entry_cutoff?: string | null;
      binary_event_exit?: string | null;
      invalidation_rule?: string | null;
    };
    long_term: {
      status: string;
      score?: number | null;
      thesis_strength_score?: number | null;
      entry_timing_score?: number | null;
      portfolio_fit_score?: number | null;
      target_valuation_band?: string | null;
      moat_signals: string[];
      secular_signals: string[];
      management_signals: string[];
      thesis_change_event_detected: boolean;
      missing_inputs: string[];
      thesis_break_condition?: string | null;
    };
  };
}

export interface FactorBreakdownItem {
  code: string;
  status: "pass" | "neutral" | "fail";
  detail: string;
  evaluationStatus?: "LIVE" | "UNCONFIGURED" | string;
  stubbed?: boolean | null;
  reason?: string | null;
  sourceTier?: string | null;
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

export interface FactorAuditDecision {
  status: "pass" | "neutral" | "fail";
  triggered: boolean;
  vetoed: boolean;
  action?: string | null;
  evaluationStatus?: string | null;
  stubbed?: boolean | null;
  detail: string;
  metadata: Record<string, unknown>;
}

export interface FactorAuditItem {
  layer: string;
  layerRange: string;
  factorNumber: number;
  factorCode: string;
  factorName: string;
  decision: FactorAuditDecision;
  apiCalls: Array<Record<string, unknown>>;
}

export interface FactorAuditPayload {
  symbol: string;
  scanId: number;
  scanDate: string | null;
  generatedAt: string;
  dataPolicy: {
    liveOnly: boolean;
    mockData: boolean;
    stubbedFactors: boolean;
  };
  liveValidation?: {
    allFactorsLive: boolean;
    nonLiveFactors: string[];
    strictModeRequested: boolean;
  };
  scanApiCalls: Array<Record<string, unknown>>;
  scanInputs: Record<string, unknown>;
  factors: FactorAuditItem[];
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface DualHorizonCandidate {
  symbol: string;
  name: string;
  sector: string;
  score: number;
  sizingCap?: string | null;
  regimeGate?: string | null;
}

export interface DualHorizonResponse {
  scanDate: string;
  tacticalCount: number;
  longTermCount: number;
  tactical: DualHorizonCandidate[];
  longTerm: DualHorizonCandidate[];
}

export interface PortfolioComponentScore {
  name: string;
  weight: number;
  score?: number | null;
  status: string;
  detail: string;
}

export interface PortfolioScoreResponse {
  asOf: string;
  compositeScore?: number | null;
  band: string;
  components: PortfolioComponentScore[];
  missingComponents: string[];
  metrics: Record<string, unknown>;
}

export interface PortfolioAction {
  priority: number;
  action: string;
  symbol?: string | null;
  trigger: string;
  reason: string;
  metrics: Record<string, unknown>;
}

export interface PortfolioOptimizationResponse {
  asOf: string;
  cadence: string;
  triggeredSteps: string[];
  actions: PortfolioAction[];
  score: PortfolioScoreResponse;
}

export interface PositionItem {
  id: string;
  symbol: string;
  qty: number;
  entryPrice: number;
  currentPrice?: number | null;
  unrealizedPnl?: number | null;
  realizedPnl?: number | null;
  exitPrice?: number | null;
  status: string;
  openedAt?: string | null;
  closedAt?: string | null;
}

export interface PositionListResponse {
  results: PositionItem[];
}

export type ViewMode = "ALL_STOCKS" | "EARNINGS_TODAY" | "TACTICAL_30D" | "LONG_TERM";
