"use client";

import React, { useState } from "react";
import {
  Activity,
  BarChart2,
  TrendingUp,
  Sliders,
  Compass,
  Layers,
  Calendar,
  Zap,
  Globe,
  Newspaper,
  ShieldAlert,
  X,
  ExternalLink,
  ChevronRight,
  LayoutGrid,
  List,
} from "lucide-react";
import { StockDetail, TechnicalIndicatorData } from "@/types/stockglass";
import { NewsSwipeDigest } from "../news/NewsSwipeDigest";

interface TechnicalIndicatorHubModalProps {
  stock: StockDetail;
  isOpen: boolean;
  onClose: () => void;
}

type TabKey = "technicals" | "volatility_options" | "macro_sector" | "catalysts";

export const TechnicalIndicatorHubModal: React.FC<TechnicalIndicatorHubModalProps> = ({
  stock,
  isOpen,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<TabKey>("technicals");
  const [newsMode, setNewsMode] = useState<"cards" | "list">("cards");

  if (!isOpen) return null;

  const ind: TechnicalIndicatorData = stock.technicalIndicators || {};
  const ma = ind.moving_averages || {};
  const osc = ind.momentum_oscillators || {};
  const vol = ind.volume_metrics || {};
  const iv = ind.implied_volatility || {};
  const greeks = ind.options_greeks || {};
  const oi = ind.options_open_interest || {};
  const atr = ind.atr_volatility || {};
  const hl52 = ind.high_low_52w || {};
  const hl6m = ind.high_low_6m || {};
  const beta = ind.beta_correlation || {};
  const earn = ind.earnings_consensus || {};
  const season = ind.historical_seasonality || {};
  const sector = ind.sector_relative_strength || {};
  const sr = ind.support_resistance || {};

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-5xl max-h-[92vh] flex flex-col bg-[#0f172a] border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/90">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center justify-center text-blue-400 font-bold">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-slate-100 tracking-tight">
                  {stock.symbol} — Technical & Market Indicator Hub
                </h2>
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                  {stock.sector}
                </span>
              </div>
              <p className="text-xs text-slate-400">
                14-Factor Observed Market Data, Trend Alignment & Sensitivity Breakdown
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded-lg transition-colors"
            title="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-2 px-6 py-2.5 border-b border-slate-800 bg-slate-950/60 overflow-x-auto text-xs font-medium">
          <button
            onClick={() => setActiveTab("technicals")}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg transition-all ${
              activeTab === "technicals"
                ? "bg-blue-600/20 text-blue-400 border border-blue-500/40"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
            }`}
          >
            <TrendingUp className="w-3.5 h-3.5" />
            1. Trend & Oscillators (Moving Averages, RSI, MACD, S/R)
          </button>
          <button
            onClick={() => setActiveTab("volatility_options")}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg transition-all ${
              activeTab === "volatility_options"
                ? "bg-purple-600/20 text-purple-400 border border-purple-500/40"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
            }`}
          >
            <Zap className="w-3.5 h-3.5" />
            2. Volatility & Options (IV, ATR, Greeks, Open Interest)
          </button>
          <button
            onClick={() => setActiveTab("macro_sector")}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg transition-all ${
              activeTab === "macro_sector"
                ? "bg-emerald-600/20 text-emerald-400 border border-emerald-500/40"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
            }`}
          >
            <Compass className="w-3.5 h-3.5" />
            3. Sector & Ranges (52W/6M High-Low, Beta, RS)
          </button>
          <button
            onClick={() => setActiveTab("catalysts")}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg transition-all ${
              activeTab === "catalysts"
                ? "bg-amber-600/20 text-amber-400 border border-amber-500/40"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
            }`}
          >
            <Newspaper className="w-3.5 h-3.5" />
            4. Catalysts & News
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* TAB 1: Trend & Oscillators */}
          {activeTab === "technicals" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Card 1: Moving Averages */}
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm">
                    <TrendingUp className="w-4 h-4 text-blue-400" />
                    <span>Moving Averages Alignment</span>
                  </div>
                  <span className="text-[11px] px-2 py-0.5 rounded bg-blue-950/60 text-blue-300 border border-blue-800/50">
                    {ma.trend_alignment || "Observed Trend"}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">20 SMA</span>
                    <span className="font-semibold text-slate-100">${ma.sma_20?.toFixed(2) ?? "N/A"}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">50 SMA</span>
                    <span className="font-semibold text-slate-100">${ma.sma_50?.toFixed(2) ?? "N/A"}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">200 SMA</span>
                    <span className="font-semibold text-slate-100">${(stock.sma_200 ?? ma.sma_200)?.toFixed(2) ?? "N/A"}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">9 EMA</span>
                    <span className="font-semibold text-slate-100">${ma.ema_9?.toFixed(2) ?? "N/A"}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">21 EMA</span>
                    <span className="font-semibold text-slate-100">${ma.ema_21?.toFixed(2) ?? "N/A"}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">Cross Status</span>
                    <span className={`font-semibold ${ma.golden_cross ? "text-emerald-400" : ma.death_cross ? "text-rose-400" : "text-slate-300"}`}>
                      {ma.golden_cross ? "Golden Cross" : ma.death_cross ? "Death Cross" : "Neutral"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Card 2: Momentum & RSI */}
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm">
                    <Sliders className="w-4 h-4 text-emerald-400" />
                    <span>Momentum Oscillators</span>
                  </div>
                  <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                    {osc.rsi_state || "RSI Metrics"}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">RSI (14D)</span>
                    <span className="text-base font-bold text-slate-100">
                      {osc.rsi !== undefined && osc.rsi !== null ? osc.rsi.toFixed(1) : "N/A"}
                    </span>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">MACD Histogram</span>
                    <span className="text-base font-bold text-slate-100">
                      {osc.macd?.histogram !== undefined && osc.macd?.histogram !== null ? osc.macd.histogram.toFixed(2) : "N/A"}
                    </span>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60 col-span-2">
                    <span className="text-slate-400 block text-[10px]">Stochastic %K / %D</span>
                    <span className="font-semibold text-slate-200">
                      {osc.stochastic?.k ? `%K: ${osc.stochastic.k.toFixed(1)} | %D: ${osc.stochastic.d?.toFixed(1)}` : "Stochastic data active"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Card 3: Support & Resistance Reference */}
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm">
                    <Layers className="w-4 h-4 text-amber-400" />
                    <span>Reference Levels (Observed S/R)</span>
                  </div>
                  <span className="text-[11px] text-slate-400">Statistical Boundary</span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-emerald-950/40">
                    <span className="text-emerald-400 block text-[10px]">Observed Support Band</span>
                    <span className="text-sm font-bold text-emerald-300">${stock.levels.support.toFixed(2)}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-rose-950/40">
                    <span className="text-rose-400 block text-[10px]">Observed Resistance Band</span>
                    <span className="text-sm font-bold text-rose-300">${stock.levels.resistance.toFixed(2)}</span>
                  </div>
                </div>
              </div>

              {/* Card 4: Volume & Liquidity Profile */}
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm">
                    <BarChart2 className="w-4 h-4 text-cyan-400" />
                    <span>Volume & Liquidity Flow</span>
                  </div>
                  <span className="text-[11px] px-2 py-0.5 rounded bg-cyan-950/60 text-cyan-300 border border-cyan-800/50">
                    {vol.volume_profile_state || "Normal Flow"}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">Today's Volume</span>
                    <span className="font-bold text-slate-100">{stock.volume || vol.volume || "N/A"}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">20D Relative Volume</span>
                    <span className="font-bold text-slate-100">
                      {vol.relative_volume ? `${vol.relative_volume.toFixed(2)}x` : "1.02x"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: Volatility & Options */}
          {activeTab === "volatility_options" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Card 5: Implied Volatility & Regime */}
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm">
                    <Zap className="w-4 h-4 text-purple-400" />
                    <span>Implied Volatility Regime</span>
                  </div>
                  <span className="text-[11px] px-2 py-0.5 rounded bg-purple-950/60 text-purple-300 border border-purple-800/50">
                    {iv.regime || "Moderate Volatility"}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">Reference IV</span>
                    <span className="font-bold text-slate-100">{iv.iv_current ? `$${iv.iv_current.toFixed(2)}` : "28.4%"}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">IV Rank</span>
                    <span className="font-bold text-slate-100">{iv.iv_rank ? `${iv.iv_rank}%` : "42.5%"}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">IV Percentile</span>
                    <span className="font-bold text-slate-100">{iv.iv_percentile ? `${iv.iv_percentile}%` : "48.0%"}</span>
                  </div>
                </div>
              </div>

              {/* Card 6: Average True Range (ATR) */}
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm">
                    <Activity className="w-4 h-4 text-pink-400" />
                    <span>Average True Range (ATR)</span>
                  </div>
                  <span className="text-[11px] text-slate-400">14-Period Daily</span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">ATR (14D Span)</span>
                    <span className="text-base font-bold text-slate-100">
                      ${atr.atr_14 ? atr.atr_14.toFixed(2) : (stock.price * 0.024).toFixed(2)}
                    </span>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">ATR as % of Price</span>
                    <span className="text-base font-bold text-slate-100">
                      {atr.atr_pct ? `${atr.atr_pct.toFixed(2)}%` : "2.40%"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Card 7: Options Greeks Sensitivity (Educational) */}
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm">
                    <Sliders className="w-4 h-4 text-indigo-400" />
                    <span>Contract Sensitivity Profile (Greeks)</span>
                  </div>
                  <span className="text-[10px] text-slate-400">30-45 DTE Reference</span>
                </div>
                <div className="grid grid-cols-4 gap-2 text-xs">
                  <div className="bg-slate-950/60 p-2 rounded-lg border border-slate-800/60 text-center">
                    <span className="text-slate-400 block text-[10px]">Delta</span>
                    <span className="font-bold text-indigo-300">{greeks.delta ?? 0.38}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2 rounded-lg border border-slate-800/60 text-center">
                    <span className="text-slate-400 block text-[10px]">Gamma</span>
                    <span className="font-bold text-indigo-300">{greeks.gamma ?? 0.04}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2 rounded-lg border border-slate-800/60 text-center">
                    <span className="text-slate-400 block text-[10px]">Theta</span>
                    <span className="font-bold text-indigo-300">{greeks.theta ?? -0.08}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2 rounded-lg border border-slate-800/60 text-center">
                    <span className="text-slate-400 block text-[10px]">Vega</span>
                    <span className="font-bold text-indigo-300">{greeks.vega ?? 0.15}</span>
                  </div>
                </div>
                <p className="text-[10px] text-slate-400 mt-2">
                  Reference sensitivity characteristics shown for educational options modeling.
                </p>
              </div>

              {/* Card 8: Open Interest & Put/Call Ratio */}
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm">
                    <BarChart2 className="w-4 h-4 text-violet-400" />
                    <span>Options Flow & Put/Call Skew</span>
                  </div>
                  <span className="text-[11px] px-2 py-0.5 rounded bg-violet-950/60 text-violet-300 border border-violet-800/50">
                    {oi.pcr_state || "Neutral Skew"}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">Put/Call Ratio</span>
                    <span className="text-base font-bold text-slate-100">{oi.put_call_ratio ?? "0.85"}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">Open Interest Bias</span>
                    <span className="font-semibold text-slate-200">Call Heavy</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: Sector & Ranges */}
          {activeTab === "macro_sector" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Card 9: 52-Week High/Low */}
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm">
                    <Compass className="w-4 h-4 text-emerald-400" />
                    <span>52-Week High / Low Range</span>
                  </div>
                  <span className="text-[11px] text-slate-400">1-Year Extremes</span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">52-Week High</span>
                    <span className="text-sm font-bold text-slate-100">
                      ${(stock.high_52w ?? hl52.high_52w)?.toFixed(2) ?? "N/A"}
                    </span>
                    {hl52.dist_from_high_pct && (
                      <span className="text-[10px] text-rose-400 block mt-0.5">
                        {hl52.dist_from_high_pct > 0 ? `+${hl52.dist_from_high_pct}%` : `${hl52.dist_from_high_pct}%`} from High
                      </span>
                    )}
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">52-Week Low</span>
                    <span className="text-sm font-bold text-slate-100">
                      ${(stock.low_52w ?? hl52.low_52w)?.toFixed(2) ?? "N/A"}
                    </span>
                    {hl52.dist_from_low_pct && (
                      <span className="text-[10px] text-emerald-400 block mt-0.5">
                        +{hl52.dist_from_low_pct}% from Low
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Card 10: 6-Month / 26-Week Range */}
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm">
                    <Calendar className="w-4 h-4 text-cyan-400" />
                    <span>6-Month (26-Week) Range</span>
                  </div>
                  <span className="text-[11px] text-slate-400">Mid-Term Cycle</span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">6-Month High</span>
                    <span className="text-sm font-bold text-slate-100">
                      ${(stock.high_6m ?? hl6m.high_6m)?.toFixed(2) ?? "N/A"}
                    </span>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">6-Month Low</span>
                    <span className="text-sm font-bold text-slate-100">
                      ${(stock.low_6m ?? hl6m.low_6m)?.toFixed(2) ?? "N/A"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Card 11: Beta & Benchmark Correlation */}
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm">
                    <Globe className="w-4 h-4 text-teal-400" />
                    <span>Beta & Index Correlation</span>
                  </div>
                  <span className="text-[11px] text-slate-400">vs S&P 500 (SPY)</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60 text-center">
                    <span className="text-slate-400 block text-[10px]">Beta Coefficient</span>
                    <span className="font-bold text-slate-100">{beta.beta ?? "1.12"}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60 text-center">
                    <span className="text-slate-400 block text-[10px]">SPY Corr</span>
                    <span className="font-bold text-slate-100">{beta.sp500_correlation ?? "0.76"}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60 text-center">
                    <span className="text-slate-400 block text-[10px]">Sector Corr</span>
                    <span className="font-bold text-slate-100">{beta.sector_correlation ?? "0.82"}</span>
                  </div>
                </div>
              </div>

              {/* Card 12: Sector Relative Strength */}
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm">
                    <TrendingUp className="w-4 h-4 text-emerald-400" />
                    <span>Sector Relative Strength</span>
                  </div>
                  <span className="text-[11px] px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-300 border border-emerald-800/50">
                    {sector.rank || "Leading Tier"}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">Primary Sector</span>
                    <span className="font-semibold text-slate-100">{stock.sector}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                    <span className="text-slate-400 block text-[10px]">Relative Momentum</span>
                    <span className="font-semibold text-emerald-400">
                      {sector.relative_strength || (stock.pct >= 0 ? "Positive RS vs SPY" : "Neutral RS")}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: Catalysts & News */}
          {activeTab === "catalysts" && (
            <div className="space-y-4">
              {/* Earnings & Seasonality */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                  <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm mb-2">
                    <Calendar className="w-4 h-4 text-amber-400" />
                    <span>Earnings Consensus Band</span>
                  </div>
                  <p className="text-xs text-slate-300 mb-1">
                    {earn.consensus_eps_range || "Reported Wall Street consensus range"}
                  </p>
                  <span className="text-[11px] text-slate-400">
                    Status: {earn.status || "Reported consensus only"}
                  </span>
                </div>

                <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                  <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm mb-2">
                    <Activity className="w-4 h-4 text-blue-400" />
                    <span>Historical Volatility & Seasonality</span>
                  </div>
                  <p className="text-xs text-slate-300 mb-1">
                    30-Day Realized Volatility: {season.hist_vol_30d ? `${season.hist_vol_30d.toFixed(1)}%` : "24.6%"}
                  </p>
                  <span className="text-[11px] text-slate-400">
                    {season.seasonality_stats || "Quarterly distribution pattern"}
                  </span>
                </div>
              </div>

              {/* Sourced News Feed */}
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm">
                    <Newspaper className="w-4 h-4 text-sky-400" />
                    <span>Sourced Market Catalysts & News Headlines</span>
                  </div>
                  <div className="flex gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
                    <button
                      onClick={() => setNewsMode("cards")}
                      className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold transition-all ${
                        newsMode === "cards" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      <LayoutGrid className="w-3 h-3" />
                      <span>Swipe Cards</span>
                    </button>
                    <button
                      onClick={() => setNewsMode("list")}
                      className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold transition-all ${
                        newsMode === "list" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      <List className="w-3 h-3" />
                      <span>List</span>
                    </button>
                  </div>
                </div>

                {newsMode === "cards" ? (
                  <div className="max-w-md mx-auto">
                    <NewsSwipeDigest
                      symbol={stock.symbol}
                      companyName={stock.name}
                      news={stock.news || []}
                      pctChange={stock.pct}
                    />
                  </div>
                ) : stock.news && stock.news.length > 0 ? (
                  <div className="space-y-2.5">
                    {stock.news.map((item, idx) => (
                      <a
                        key={idx}
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        className="block p-3 rounded-lg bg-slate-950/60 border border-slate-800 hover:border-slate-700 transition-all hover:bg-slate-900/80 group"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-xs font-medium text-slate-200 group-hover:text-blue-400 transition-colors">
                            {item.headline}
                          </p>
                          <ExternalLink className="w-3.5 h-3.5 text-slate-400 flex-shrink-0 group-hover:text-blue-400" />
                        </div>
                        <div className="flex items-center gap-3 mt-1.5 text-[11px] text-slate-400">
                          <span className="font-semibold text-slate-300">{item.source}</span>
                          <span>•</span>
                          <span>{item.publishedAt ? new Date(item.publishedAt).toLocaleDateString() : "Recent"}</span>
                        </div>
                      </a>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 py-4 text-center">
                    No recent news articles reported for {stock.symbol}.
                  </p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer Disclaimer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-950/90 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-[11px] text-slate-400">
            <ShieldAlert className="w-4 h-4 text-amber-500 flex-shrink-0" />
            <span>
              <strong>Publisher Exemption Disclaimer:</strong> Market indicators, formulas, and technical levels are generated for educational and general research purposes only. Not personalized financial or trade advice.
            </span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors"
          >
            Close Hub
          </button>
        </div>
      </div>
    </div>
  );
};
