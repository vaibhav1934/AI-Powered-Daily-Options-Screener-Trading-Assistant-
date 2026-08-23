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
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "16px",
        backgroundColor: "rgba(32, 33, 36, 0.6)",
        backdropFilter: "blur(4px)",
      }}
    >
      <div
        style={{
          position: "relative",
          width: "100%",
          maxWidth: "1020px",
          maxHeight: "92vh",
          display: "flex",
          flexDirection: "column",
          backgroundColor: "#ffffff",
          border: "1px solid #dadce0",
          borderRadius: "16px",
          boxShadow: "0 20px 50px -12px rgba(32, 33, 36, 0.25)",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "16px 24px",
            borderBottom: "1px solid #e8eaed",
            backgroundColor: "#ffffff",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div
              style={{
                width: "40px",
                height: "40px",
                borderRadius: "10px",
                backgroundColor: "#e8f0fe",
                border: "1px solid #d2e3fc",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#1a73e8",
              }}
            >
              <Activity size={20} />
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <h2 style={{ fontSize: "18px", fontWeight: 700, color: "#202124", margin: 0 }}>
                  {stock.symbol} — Technical & Market Indicator Hub
                </h2>
                <span
                  style={{
                    fontSize: "11px",
                    padding: "2px 8px",
                    borderRadius: "999px",
                    backgroundColor: "#f1f3f4",
                    color: "#3c4043",
                    border: "1px solid #dadce0",
                    fontWeight: 600,
                  }}
                >
                  {stock.sector}
                </span>
              </div>
              <p style={{ fontSize: "12px", color: "#5f6368", margin: "2px 0 0 0" }}>
                14-Factor Observed Market Data, Trend Alignment & Sensitivity Breakdown
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              padding: "8px",
              color: "#5f6368",
              cursor: "pointer",
              borderRadius: "8px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
            title="Close modal"
          >
            <X size={20} />
          </button>
        </div>

        {/* Tab Navigation Bar */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "8px 20px",
            borderBottom: "1px solid #e8eaed",
            backgroundColor: "#f8f9fa",
            overflowX: "auto",
            fontSize: "12px",
            fontWeight: 500,
          }}
        >
          <button
            onClick={() => setActiveTab("technicals")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "7px 14px",
              borderRadius: "8px",
              border: activeTab === "technicals" ? "1px solid #d2e3fc" : "1px solid transparent",
              backgroundColor: activeTab === "technicals" ? "#ffffff" : "transparent",
              color: activeTab === "technicals" ? "#1a73e8" : "#5f6368",
              fontWeight: activeTab === "technicals" ? 700 : 500,
              cursor: "pointer",
              boxShadow: activeTab === "technicals" ? "0 1px 2px rgba(0,0,0,0.06)" : "none",
              transition: "all 0.15s ease",
            }}
          >
            <TrendingUp size={14} />
            <span>1. Trend & Oscillators (Moving Averages, RSI, MACD, S/R)</span>
          </button>
          <button
            onClick={() => setActiveTab("volatility_options")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "7px 14px",
              borderRadius: "8px",
              border: activeTab === "volatility_options" ? "1px solid #e1d2fc" : "1px solid transparent",
              backgroundColor: activeTab === "volatility_options" ? "#ffffff" : "transparent",
              color: activeTab === "volatility_options" ? "#8430ce" : "#5f6368",
              fontWeight: activeTab === "volatility_options" ? 700 : 500,
              cursor: "pointer",
              boxShadow: activeTab === "volatility_options" ? "0 1px 2px rgba(0,0,0,0.06)" : "none",
              transition: "all 0.15s ease",
            }}
          >
            <Zap size={14} />
            <span>2. Volatility & Options (IV, ATR, Greeks, Open Interest)</span>
          </button>
          <button
            onClick={() => setActiveTab("macro_sector")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "7px 14px",
              borderRadius: "8px",
              border: activeTab === "macro_sector" ? "1px solid #ceead6" : "1px solid transparent",
              backgroundColor: activeTab === "macro_sector" ? "#ffffff" : "transparent",
              color: activeTab === "macro_sector" ? "#137333" : "#5f6368",
              fontWeight: activeTab === "macro_sector" ? 700 : 500,
              cursor: "pointer",
              boxShadow: activeTab === "macro_sector" ? "0 1px 2px rgba(0,0,0,0.06)" : "none",
              transition: "all 0.15s ease",
            }}
          >
            <Compass size={14} />
            <span>3. Sector & Ranges (52W/6M High-Low, Beta, RS)</span>
          </button>
          <button
            onClick={() => setActiveTab("catalysts")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "7px 14px",
              borderRadius: "8px",
              border: activeTab === "catalysts" ? "1px solid #fce8b2" : "1px solid transparent",
              backgroundColor: activeTab === "catalysts" ? "#ffffff" : "transparent",
              color: activeTab === "catalysts" ? "#b06000" : "#5f6368",
              fontWeight: activeTab === "catalysts" ? 700 : 500,
              cursor: "pointer",
              boxShadow: activeTab === "catalysts" ? "0 1px 2px rgba(0,0,0,0.06)" : "none",
              transition: "all 0.15s ease",
            }}
          >
            <Newspaper size={14} />
            <span>4. Catalysts & News</span>
          </button>
        </div>

        {/* Content Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px", display: "flex", flexDirection: "column", gap: "16px", backgroundColor: "#fbfcff" }}>
          {/* TAB 1: Trend & Oscillators */}
          {activeTab === "technicals" && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: "16px" }}>
              {/* Card 1: Moving Averages */}
              <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#ffffff", border: "1px solid #e8eaed", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#202124", fontWeight: 600, fontSize: "13.5px" }}>
                    <TrendingUp size={16} color="#1a73e8" />
                    <span>Moving Averages Alignment</span>
                  </div>
                  <span style={{ fontSize: "11px", padding: "2px 8px", borderRadius: "4px", backgroundColor: "#e8f0fe", color: "#1a73e8", border: "1px solid #d2e3fc", fontWeight: 600 }}>
                    {ma.trend_alignment || "Observed Trend"}
                  </span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "8px", fontSize: "12px" }}>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>20 SMA</span>
                    <span style={{ fontWeight: 700, color: "#202124" }}>${ma.sma_20?.toFixed(2) ?? "N/A"}</span>
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>50 SMA</span>
                    <span style={{ fontWeight: 700, color: "#202124" }}>${ma.sma_50?.toFixed(2) ?? "N/A"}</span>
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>200 SMA</span>
                    <span style={{ fontWeight: 700, color: "#202124" }}>${(stock.sma_200 ?? ma.sma_200)?.toFixed(2) ?? "N/A"}</span>
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>9 EMA</span>
                    <span style={{ fontWeight: 700, color: "#202124" }}>${ma.ema_9?.toFixed(2) ?? "N/A"}</span>
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>21 EMA</span>
                    <span style={{ fontWeight: 700, color: "#202124" }}>${ma.ema_21?.toFixed(2) ?? "N/A"}</span>
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>Cross Status</span>
                    <span style={{ fontWeight: 700, color: ma.golden_cross ? "#137333" : ma.death_cross ? "#c5221f" : "#5f6368" }}>
                      {ma.golden_cross ? "Golden Cross" : ma.death_cross ? "Death Cross" : "Neutral"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Card 2: Momentum & RSI */}
              <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#ffffff", border: "1px solid #e8eaed", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#202124", fontWeight: 600, fontSize: "13.5px" }}>
                    <Sliders size={16} color="#137333" />
                    <span>Momentum Oscillators</span>
                  </div>
                  <span style={{ fontSize: "11px", padding: "2px 8px", borderRadius: "4px", backgroundColor: "#e6f4ea", color: "#137333", border: "1px solid #ceead6", fontWeight: 600 }}>
                    {osc.rsi_state || "RSI Metrics"}
                  </span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", fontSize: "12px" }}>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>RSI (14D)</span>
                    <span style={{ fontSize: "16px", fontWeight: 700, color: "#202124" }}>
                      {osc.rsi !== undefined && osc.rsi !== null ? osc.rsi.toFixed(1) : "N/A"}
                    </span>
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>MACD Histogram</span>
                    {(() => {
                      const macdObj = osc.macd as any;
                      const macdHist = macdObj?.histogram ?? macdObj?.hist;
                      const macdLine = macdObj?.macd_line ?? macdObj?.macd;
                      const macdSig = macdObj?.signal_line ?? macdObj?.signal;
                      return (
                        <>
                          <span style={{ fontSize: "16px", fontWeight: 700, color: macdHist && macdHist > 0 ? "#137333" : macdHist && macdHist < 0 ? "#c5221f" : "#202124" }}>
                            {macdHist !== undefined && macdHist !== null ? `${Number(macdHist) > 0 ? "+" : ""}${Number(macdHist).toFixed(2)}` : "N/A"}
                          </span>
                          {macdLine !== undefined && macdLine !== null && macdSig !== undefined && macdSig !== null && (
                            <span style={{ fontSize: "10px", color: "#5f6368", display: "block", marginTop: "2px" }}>
                              Line: {Number(macdLine).toFixed(2)} | Sig: {Number(macdSig).toFixed(2)}
                            </span>
                          )}
                        </>
                      );
                    })()}
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed", gridColumn: "span 2" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>Stochastic %K / %D</span>
                    <span style={{ fontWeight: 600, color: "#3c4043" }}>
                      {osc.stochastic?.k != null ? `%K: ${Number(osc.stochastic.k).toFixed(1)} | %D: ${osc.stochastic.d != null ? Number(osc.stochastic.d).toFixed(1) : "N/A"}` : "N/A"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Card 3: Support & Resistance Reference */}
              <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#ffffff", border: "1px solid #e8eaed", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#202124", fontWeight: 600, fontSize: "13.5px" }}>
                    <Layers size={16} color="#b06000" />
                    <span>Reference Levels (Observed S/R)</span>
                  </div>
                  <span style={{ fontSize: "11px", color: "#5f6368" }}>Statistical Boundary</span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", fontSize: "12px" }}>
                  <div style={{ backgroundColor: "#e6f4ea", padding: "10px", borderRadius: "8px", border: "1px solid #ceead6" }}>
                    <span style={{ color: "#137333", display: "block", fontSize: "10.5px", fontWeight: 600 }}>Observed Support Band</span>
                    <span style={{ fontSize: "15px", fontWeight: 700, color: "#137333" }}>${stock.levels.support.toFixed(2)}</span>
                  </div>
                  <div style={{ backgroundColor: "#fce8e6", padding: "10px", borderRadius: "8px", border: "1px solid #fad2cf" }}>
                    <span style={{ color: "#c5221f", display: "block", fontSize: "10.5px", fontWeight: 600 }}>Observed Resistance Band</span>
                    <span style={{ fontSize: "15px", fontWeight: 700, color: "#c5221f" }}>${stock.levels.resistance.toFixed(2)}</span>
                  </div>
                </div>
              </div>

              {/* Card 4: Volume & Liquidity Profile */}
              <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#ffffff", border: "1px solid #e8eaed", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#202124", fontWeight: 600, fontSize: "13.5px" }}>
                    <BarChart2 size={16} color="#007b83" />
                    <span>Volume & Liquidity Flow</span>
                  </div>
                  <span style={{ fontSize: "11px", padding: "2px 8px", borderRadius: "4px", backgroundColor: "#e0f2f1", color: "#007b83", border: "1px solid #b2dfdb", fontWeight: 600 }}>
                    {vol.volume_profile_state || "Normal Flow"}
                  </span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", fontSize: "12px" }}>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>Today's Volume</span>
                    <span style={{ fontWeight: 700, color: "#202124" }}>{stock.volume || vol.volume || "N/A"}</span>
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>20D Relative Volume</span>
                    <span style={{ fontWeight: 700, color: "#202124" }}>
                      {vol.relative_volume != null ? `${Number(vol.relative_volume).toFixed(2)}x` : "N/A"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: Volatility & Options */}
          {activeTab === "volatility_options" && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: "16px" }}>
              {/* Card 5: Implied Volatility & Regime */}
              <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#ffffff", border: "1px solid #e8eaed", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#202124", fontWeight: 600, fontSize: "13.5px" }}>
                    <Zap size={16} color="#8430ce" />
                    <span>Implied Volatility Regime</span>
                  </div>
                  <span style={{ fontSize: "11px", padding: "2px 8px", borderRadius: "4px", backgroundColor: "#f3e8fd", color: "#8430ce", border: "1px solid #e1d2fc", fontWeight: 600 }}>
                    {iv.regime || "Data Not Available"}
                  </span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "8px", fontSize: "12px" }}>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>Reference IV</span>
                    <span style={{ fontWeight: 700, color: "#202124" }}>
                      {iv.iv_current != null ? (Number(iv.iv_current) > 1.0 ? `${Number(iv.iv_current).toFixed(1)}%` : `${(Number(iv.iv_current) * 100).toFixed(1)}%`) : "N/A"}
                    </span>
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>IV Rank</span>
                    <span style={{ fontWeight: 700, color: "#202124" }}>{iv.iv_rank != null ? `${Number(iv.iv_rank).toFixed(1)}%` : "N/A"}</span>
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>IV Percentile</span>
                    <span style={{ fontWeight: 700, color: "#202124" }}>{iv.iv_percentile != null ? `${Number(iv.iv_percentile).toFixed(1)}%` : "N/A"}</span>
                  </div>
                </div>
              </div>

              {/* Card 6: Average True Range (ATR) */}
              <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#ffffff", border: "1px solid #e8eaed", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#202124", fontWeight: 600, fontSize: "13.5px" }}>
                    <Activity size={16} color="#d93025" />
                    <span>Average True Range (ATR)</span>
                  </div>
                  <span style={{ fontSize: "11px", color: "#5f6368" }}>14-Period Daily</span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", fontSize: "12px" }}>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>ATR (14D Span)</span>
                    <span style={{ fontSize: "16px", fontWeight: 700, color: "#202124" }}>
                      {(atr.atr_14 ?? (atr as any).atr) != null ? `$${Number(atr.atr_14 ?? (atr as any).atr).toFixed(2)}` : "N/A"}
                    </span>
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>ATR as % of Price</span>
                    <span style={{ fontSize: "16px", fontWeight: 700, color: "#202124" }}>
                      {atr.atr_pct != null ? (Number(atr.atr_pct) > 1.0 ? `${Number(atr.atr_pct).toFixed(2)}%` : `${(Number(atr.atr_pct) * 100).toFixed(2)}%`) : "N/A"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Card 7: Options Greeks Sensitivity (Educational) */}
              <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#ffffff", border: "1px solid #e8eaed", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#202124", fontWeight: 600, fontSize: "13.5px" }}>
                    <Sliders size={16} color="#1a73e8" />
                    <span>Contract Sensitivity Profile (Greeks)</span>
                  </div>
                  <span style={{ fontSize: "10.5px", color: "#5f6368" }}>30-45 DTE Reference</span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "8px", fontSize: "12px" }}>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "8px", borderRadius: "8px", border: "1px solid #e8eaed", textAlign: "center" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>Delta</span>
                    <span style={{ fontWeight: 700, color: "#1a73e8" }}>{greeks.delta != null ? Number(greeks.delta).toFixed(2) : "N/A"}</span>
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "8px", borderRadius: "8px", border: "1px solid #e8eaed", textAlign: "center" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>Gamma</span>
                    <span style={{ fontWeight: 700, color: "#1a73e8" }}>{greeks.gamma != null ? Number(greeks.gamma).toFixed(4) : "N/A"}</span>
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "8px", borderRadius: "8px", border: "1px solid #e8eaed", textAlign: "center" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>Theta</span>
                    <span style={{ fontWeight: 700, color: "#1a73e8" }}>{greeks.theta != null ? Number(greeks.theta).toFixed(2) : "N/A"}</span>
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "8px", borderRadius: "8px", border: "1px solid #e8eaed", textAlign: "center" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>Vega</span>
                    <span style={{ fontWeight: 700, color: "#1a73e8" }}>{greeks.vega != null ? Number(greeks.vega).toFixed(3) : "N/A"}</span>
                  </div>
                </div>
                <p style={{ fontSize: "10.5px", color: "#80868b", margin: "8px 0 0 0" }}>
                  Reference sensitivity characteristics shown for educational options modeling.
                </p>
              </div>

              {/* Card 8: Options Open Interest & Put/Call Ratio */}
              <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#ffffff", border: "1px solid #e8eaed", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#202124", fontWeight: 600, fontSize: "13.5px" }}>
                    <Activity size={16} color="#e37400" />
                    <span>Options Flow & Open Interest (OI)</span>
                  </div>
                  <span style={{ fontSize: "11px", padding: "2px 8px", borderRadius: "4px", backgroundColor: "#fef7e0", color: "#b06000", border: "1px solid #fce8b2", fontWeight: 600 }}>
                    {oi.pcr_state || "Data Not Available"}
                  </span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", fontSize: "12px" }}>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>Put / Call Ratio</span>
                    <span style={{ fontSize: "16px", fontWeight: 700, color: "#202124" }}>{oi.put_call_ratio != null ? Number(oi.put_call_ratio).toFixed(2) : "N/A"}</span>
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>Call Open Interest</span>
                    <span style={{ fontSize: "16px", fontWeight: 700, color: "#137333" }}>
                      {(oi.total_call_oi ?? (oi as any).call_open_interest) != null ? Number(oi.total_call_oi ?? (oi as any).call_open_interest).toLocaleString() : "N/A"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: Sector & Macro Ranges */}
          {activeTab === "macro_sector" && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: "16px" }}>
              {/* Card 9: 52-Week High / Low Range */}
              <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#ffffff", border: "1px solid #e8eaed", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#202124", fontWeight: 600, fontSize: "13.5px" }}>
                    <Compass size={16} color="#137333" />
                    <span>52-Week High / Low Range</span>
                  </div>
                  <span style={{ fontSize: "11px", color: "#5f6368" }}>1-Year Extremes</span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", fontSize: "12px" }}>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>52-Week High</span>
                    <span style={{ fontSize: "15px", fontWeight: 700, color: "#202124" }}>
                      ${(stock.high_52w ?? hl52.high_52w)?.toFixed(2) ?? "N/A"}
                    </span>
                    {hl52.dist_from_high_pct && (
                      <span style={{ fontSize: "10.5px", color: "#c5221f", display: "block", marginTop: "2px" }}>
                        {hl52.dist_from_high_pct > 0 ? `+${hl52.dist_from_high_pct}%` : `${hl52.dist_from_high_pct}%`} from High
                      </span>
                    )}
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>52-Week Low</span>
                    <span style={{ fontSize: "15px", fontWeight: 700, color: "#202124" }}>
                      ${(stock.low_52w ?? hl52.low_52w)?.toFixed(2) ?? "N/A"}
                    </span>
                    {hl52.dist_from_low_pct && (
                      <span style={{ fontSize: "10.5px", color: "#137333", display: "block", marginTop: "2px" }}>
                        +{hl52.dist_from_low_pct}% from Low
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Card 10: 6-Month / 26-Week Range */}
              <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#ffffff", border: "1px solid #e8eaed", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#202124", fontWeight: 600, fontSize: "13.5px" }}>
                    <Calendar size={16} color="#007b83" />
                    <span>6-Month (26-Week) Range</span>
                  </div>
                  <span style={{ fontSize: "11px", color: "#5f6368" }}>Mid-Term Cycle</span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", fontSize: "12px" }}>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>6-Month High</span>
                    <span style={{ fontSize: "15px", fontWeight: 700, color: "#202124" }}>
                      ${(stock.high_6m ?? hl6m.high_6m)?.toFixed(2) ?? "N/A"}
                    </span>
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>6-Month Low</span>
                    <span style={{ fontSize: "15px", fontWeight: 700, color: "#202124" }}>
                      ${(stock.low_6m ?? hl6m.low_6m)?.toFixed(2) ?? "N/A"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Card 11: Beta & Benchmark Correlation */}
              <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#ffffff", border: "1px solid #e8eaed", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#202124", fontWeight: 600, fontSize: "13.5px" }}>
                    <Globe size={16} color="#1a73e8" />
                    <span>Beta & Index Correlation</span>
                  </div>
                  <span style={{ fontSize: "11px", color: "#5f6368" }}>vs S&P 500 (SPY)</span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "8px", fontSize: "12px" }}>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed", textAlign: "center" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>Beta (vs. SPY)</span>
                    <span style={{ fontWeight: 700, color: "#202124" }}>{beta.beta != null ? Number(beta.beta).toFixed(2) : "N/A"}</span>
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed", textAlign: "center" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>S&P 500 Corr</span>
                    <span style={{ fontWeight: 700, color: "#202124" }}>{beta.sp500_correlation != null ? `${(Number(beta.sp500_correlation) * 100).toFixed(0)}%` : "N/A"}</span>
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed", textAlign: "center" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>Sector Corr</span>
                    <span style={{ fontWeight: 700, color: "#202124" }}>{beta.sector_correlation != null ? `${(Number(beta.sector_correlation) * 100).toFixed(0)}%` : "N/A"}</span>
                  </div>
                </div>
              </div>

              {/* Card 12: Sector Relative Strength */}
              <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#ffffff", border: "1px solid #e8eaed", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#202124", fontWeight: 600, fontSize: "13.5px" }}>
                    <TrendingUp size={16} color="#137333" />
                    <span>Sector Relative Strength</span>
                  </div>
                  <span style={{ fontSize: "11px", padding: "2px 8px", borderRadius: "4px", backgroundColor: "#e6f4ea", color: "#137333", border: "1px solid #ceead6", fontWeight: 600 }}>
                    {sector.rank || "Data Not Available"}
                  </span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", fontSize: "12px" }}>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>Primary Sector</span>
                    <span style={{ fontWeight: 700, color: "#202124" }}>{sector.sector || stock.sector || "N/A"}</span>
                  </div>
                  <div style={{ backgroundColor: "#f8f9fa", padding: "10px", borderRadius: "8px", border: "1px solid #e8eaed" }}>
                    <span style={{ color: "#5f6368", display: "block", fontSize: "10.5px" }}>RS vs S&P 500</span>
                    <span style={{ fontWeight: 700, color: "#137333" }}>{sector.relative_strength || "N/A"}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: Catalysts, Consensus & News */}
          {activeTab === "catalysts" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: "16px" }}>
                {/* Card 13: Earnings Consensus */}
                <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#ffffff", border: "1px solid #e8eaed", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#202124", fontWeight: 600, fontSize: "13.5px", marginBottom: "8px" }}>
                    <Calendar size={16} color="#1a73e8" />
                    <span>Earnings Consensus Band</span>
                  </div>
                  <p style={{ fontSize: "13px", color: "#202124", margin: "0 0 4px 0", fontWeight: 500 }}>
                    {earn.consensus_eps_range || "Reported Wall Street consensus range"}
                  </p>
                  <span style={{ fontSize: "11px", color: "#5f6368" }}>
                    Status: {earn.status || "Reported consensus only"}
                  </span>
                </div>

                {/* Realized Volatility */}
                <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#ffffff", border: "1px solid #e8eaed", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#202124", fontWeight: 600, fontSize: "13.5px", marginBottom: "8px" }}>
                    <Activity size={16} color="#1a73e8" />
                    <span>Historical Volatility & Seasonality</span>
                  </div>
                  <p style={{ fontSize: "13px", color: "#202124", margin: "0 0 4px 0", fontWeight: 500 }}>
                    30-Day Realized Volatility: {season.hist_vol_30d != null ? `${Number(season.hist_vol_30d).toFixed(1)}%` : "N/A"}
                  </p>
                  <span style={{ fontSize: "11px", color: "#5f6368" }}>
                    {season.seasonality_stats || "Quarterly distribution pattern"}
                  </span>
                </div>
              </div>

              {/* Card 14: Sourced News Feed */}
              <div style={{ padding: "16px", borderRadius: "12px", backgroundColor: "#ffffff", border: "1px solid #e8eaed", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#202124", fontWeight: 600, fontSize: "13.5px" }}>
                    <Newspaper size={16} color="#1a73e8" />
                    <span>Sourced Market Catalysts & News Headlines</span>
                  </div>
                  <div style={{ display: "flex", gap: "2px", backgroundColor: "#f1f3f4", padding: "2px", borderRadius: "6px" }}>
                    <button
                      onClick={() => setNewsMode("cards")}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "4px",
                        padding: "3px 8px",
                        borderRadius: "4px",
                        border: "none",
                        backgroundColor: newsMode === "cards" ? "#ffffff" : "transparent",
                        color: newsMode === "cards" ? "#1a73e8" : "#5f6368",
                        fontSize: "11px",
                        fontWeight: 600,
                        cursor: "pointer",
                        boxShadow: newsMode === "cards" ? "0 1px 2px rgba(0,0,0,0.1)" : "none",
                      }}
                    >
                      <LayoutGrid size={12} />
                      <span>Swipe Cards</span>
                    </button>
                    <button
                      onClick={() => setNewsMode("list")}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "4px",
                        padding: "3px 8px",
                        borderRadius: "4px",
                        border: "none",
                        backgroundColor: newsMode === "list" ? "#ffffff" : "transparent",
                        color: newsMode === "list" ? "#1a73e8" : "#5f6368",
                        fontSize: "11px",
                        fontWeight: 600,
                        cursor: "pointer",
                        boxShadow: newsMode === "list" ? "0 1px 2px rgba(0,0,0,0.1)" : "none",
                      }}
                    >
                      <List size={12} />
                      <span>List</span>
                    </button>
                  </div>
                </div>

                {newsMode === "cards" ? (
                  <div style={{ maxWidth: "480px", margin: "0 auto" }}>
                    <NewsSwipeDigest
                      symbol={stock.symbol}
                      companyName={stock.name}
                      news={stock.news || []}
                      pctChange={stock.pct}
                    />
                  </div>
                ) : stock.news && stock.news.length > 0 ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {stock.news.map((item, idx) => (
                      <a
                        key={idx}
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        style={{
                          display: "block",
                          padding: "12px",
                          borderRadius: "8px",
                          backgroundColor: "#f8f9fa",
                          border: "1px solid #e8eaed",
                          textDecoration: "none",
                          color: "inherit",
                          transition: "all 0.15s ease",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "8px" }}>
                          <p style={{ fontSize: "13px", fontWeight: 600, color: "#202124", margin: 0, lineHeight: 1.4 }}>
                            {item.headline}
                          </p>
                          <ExternalLink size={14} color="#5f6368" style={{ flexShrink: 0, marginTop: "2px" }} />
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "6px", fontSize: "11px", color: "#5f6368" }}>
                          <span style={{ fontWeight: 600, color: "#3c4043" }}>{item.source}</span>
                          <span>•</span>
                          <span>{item.publishedAt ? new Date(item.publishedAt).toLocaleDateString() : "Recent"}</span>
                        </div>
                      </a>
                    ))}
                  </div>
                ) : (
                  <p style={{ fontSize: "12px", color: "#5f6368", padding: "16px 0", textAlign: "center", margin: 0 }}>
                    No recent news articles reported for {stock.symbol}.
                  </p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer Disclaimer */}
        <div
          style={{
            padding: "12px 24px",
            borderTop: "1px solid #e8eaed",
            backgroundColor: "#f8f9fa",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "8px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "11px", color: "#5f6368" }}>
            <ShieldAlert size={14} color="#b06000" style={{ flexShrink: 0 }} />
            <span>
              <strong>Publisher Exemption Disclaimer:</strong> Market indicators, formulas, and technical levels are generated for educational and general research purposes only. Not personalized financial or trade advice.
            </span>
          </div>
          <span style={{ fontSize: "11px", color: "#80868b", whiteSpace: "nowrap" }}>
            Finnhub • SEC EDGAR
          </span>
        </div>
      </div>
    </div>
  );
};
