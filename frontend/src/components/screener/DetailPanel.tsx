"use client";
import React, { useState, useEffect } from "react";
import { StockDetail, StockSynthesis } from "@/types/stockglass";
import { fetchStockSynthesis } from "@/lib/stockglass_api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { scoreColor } from "./ScreenerRow";
import {
  ExternalLink,
  Info,
  Newspaper,
  Sparkles,
  Upload,
  AlertCircle,
  Loader2,
  Activity,
  TrendingUp,
  Compass,
  ShieldAlert,
  LayoutGrid,
  List,
} from "lucide-react";
import { uploadOptionsChainScreenshot } from "@/lib/api";
import { TechnicalIndicatorHubModal } from "./TechnicalIndicatorHubModal";
import { NewsSwipeDigest } from "../news/NewsSwipeDigest";

const reasonColor: Record<string, string> = { bull: "#188038", bear: "#c5221f", neutral: "#5f6368" };

interface DetailPanelProps {
  symbol: string;
  detail: StockDetail | null;
  loading: boolean;
  error?: string | null;
  onOpenFactors: () => void;
  onAskAi?: (prompt: string) => void;
  onAddPaperTrade?: (payload: { symbol: string; entryPrice: number; qty: number }) => Promise<void>;
}

function formatOccSymbol(ticker: string, strike: number, isCall: boolean = true, targetDteDays: number = 35): string {
  const d = new Date();
  d.setDate(d.getDate() + targetDteDays);
  const yy = String(d.getFullYear()).slice(-2);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const cp = isCall ? "C" : "P";
  const strikeInt = Math.round(strike * 1000);
  const strikeStr = String(strikeInt).padStart(8, "0");
  return `${ticker.toUpperCase()}${yy}${mm}${dd}${cp}${strikeStr}`;
}

export function DetailPanel({
  symbol,
  detail,
  loading,
  error,
  onOpenFactors,
  onAskAi,
  onAddPaperTrade,
}: DetailPanelProps) {
  const [uploadingChain, setUploadingChain] = useState(false);
  const [localStrike, setLocalStrike] = useState<number | null>(null);
  const [aiSelection, setAiSelection] = useState<any>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [synthesis, setSynthesis] = useState<StockSynthesis | null>(null);
  const [loadingSynthesis, setLoadingSynthesis] = useState(false);
  const [addingStock, setAddingStock] = useState(false);
  const [addingOption, setAddingOption] = useState(false);
  const [paperMessage, setPaperMessage] = useState<string | null>(null);
  const [paperError, setPaperError] = useState<string | null>(null);
  const [showHubModal, setShowHubModal] = useState(false);
  const [newsViewMode, setNewsViewMode] = useState<"cards" | "list">("cards");

  useEffect(() => {
    if (detail) {
      setLocalStrike(detail.execution_details?.strike_price ?? null);
      setAiSelection(null);
      setUploadError(null);
      setSynthesis(null);
      setLoadingSynthesis(true);

      let isMounted = true;
      fetchStockSynthesis(detail.symbol)
        .then((data) => {
          if (isMounted) {
            setSynthesis(data);
            setLoadingSynthesis(false);
          }
        })
        .catch((err) => {
          if (isMounted) {
            console.error("Failed to fetch synthesis:", err);
            setLoadingSynthesis(false);
          }
        });

      return () => {
        isMounted = false;
      };
    }
  }, [detail]);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0 || !detail || !detail.id) return;
    const file = e.target.files[0];
    setUploadingChain(true);
    setUploadError(null);
    try {
      const res = await uploadOptionsChainScreenshot(detail.id, file);
      if (res && res.strike_price) {
        setLocalStrike(res.strike_price);
      }
      if (res && res.ai_selection) {
        setAiSelection(res.ai_selection);
        if (res.ai_selection.error) {
          setUploadError(res.ai_selection.error);
        }
      }
    } catch (err: any) {
      setUploadError(err.message || "Failed to upload options chain.");
    } finally {
      setUploadingChain(false);
    }
  };

  if (!symbol) {
    return (
      <div style={{ borderLeft: "1px solid #e8eaed", padding: 40, width: "100%", flexShrink: 0, background: "#fff", textAlign: "center", color: "#5f6368" }}>
        <p style={{ fontSize: 16, fontWeight: 500, color: "#202124" }}>Select a Setup</p>
        <p style={{ fontSize: 13, marginTop: 4 }}>Click any row on the left to review observed technical indicators and factor data.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ borderLeft: "1px solid #e8eaed", padding: 40, width: "100%", flexShrink: 0, background: "#fff", textAlign: "center", color: "#c5221f" }}>
        <AlertCircle size={32} style={{ margin: "0 auto", marginBottom: 12 }} />
        <p style={{ fontSize: 16, fontWeight: 500 }}>Detail Not Available</p>
        <p style={{ fontSize: 13, marginTop: 8 }}>{error}</p>
      </div>
    );
  }

  if (loading || !detail) {
    return (
      <div style={{ borderLeft: "1px solid #e8eaed", padding: 20, width: "100%", flexShrink: 0, background: "#fff", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%" }}>
        <Loader2 size={36} className="animate-spin" style={{ color: "#1a73e8", marginBottom: 16 }} />
        <p style={{ fontSize: 18, fontWeight: 600, color: "#202124" }}>Aggregating Technical Data...</p>
        <p style={{ fontSize: 14, color: "#5f6368", textAlign: "center", marginTop: 8, maxWidth: 280, lineHeight: 1.5 }}>
          Fetching moving averages, 52W extremes, news catalysts, and options factor data.
        </p>
      </div>
    );
  }

  const sc = scoreColor(detail.score);
  const isPos = detail.chg >= 0;
  const support = detail.levels?.support ?? 0;
  const resistance = detail.levels?.resistance ?? 0;

  const layerData = detail.layerScores?.map((l: any) => ({
    layer: l.layer ? String(l.layer).split("/")[0].split(" ")[0] : "?",
    val: l.value ?? 0,
  })) || [];

  const reasons = synthesis?.reasons || detail.reasons || [];
  const newsSummary = synthesis?.newsSummary || detail.newsSummary || null;

  return (
    <div style={{ borderLeft: "1px solid #e8eaed", padding: 20, width: "100%", flexShrink: 0, background: "#fff", overflowY: "auto", height: "100%" }}>
      {/* Top Header: Symbol, Company, Sector, Signal Score */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 22, fontWeight: 700, color: "#202124" }}>{detail.symbol}</span>
            <span style={{ fontSize: 11, background: "#f1f3f4", color: "#5f6368", padding: "2px 8px", borderRadius: 12, fontWeight: 600 }}>
              {detail.sector}
            </span>
          </div>
          <div style={{ fontSize: 13, color: "#5f6368", marginTop: 2 }}>{detail.name}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ background: sc.bg, color: sc.fg, fontSize: 13, fontWeight: 700, padding: "4px 10px", borderRadius: 14, display: "inline-block" }}>
            Signal: {detail.score.toFixed(1)} / 10
          </div>
          <div style={{ fontSize: 10, color: "#80868b", marginTop: 2 }}>Factor Model Alignment</div>
        </div>
      </div>

      {/* Price & Daily Change */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginTop: 10 }}>
        <span style={{ fontSize: 26, fontWeight: 700, color: "#202124" }}>${detail.price.toFixed(2)}</span>
        <span style={{ fontSize: 13, color: isPos ? "#188038" : "#c5221f", fontWeight: 600 }}>
          {isPos ? "+" : ""}{detail.chg.toFixed(2)} ({detail.pct.toFixed(2)}%)
        </span>
        {detail.volume && (
          <span style={{ color: "#5f6368", background: "#f1f3f4", padding: "2px 6px", borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
            Vol: {detail.volume}
          </span>
        )}
      </div>

      {/* Quick Technical Indicator Highlights Card */}
      <div style={{ background: "#f8f9fa", borderRadius: 8, padding: "10px 12px", marginTop: 12, marginBottom: 14, border: "1px solid #e8eaed" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 11.5 }}>
          <div>
            <span style={{ color: "#5f6368" }}>200-Day SMA:</span>{" "}
            <span style={{ fontWeight: 600, color: "#202124" }}>
              {detail.sma_200 ? `$${detail.sma_200.toFixed(2)}` : "Evaluating"}
            </span>
          </div>
          <div>
            <span style={{ color: "#5f6368" }}>Observed S / R:</span>{" "}
            <span style={{ fontWeight: 600, color: "#202124" }}>
              ${support.toFixed(2)} / ${resistance.toFixed(2)}
            </span>
          </div>
          <div>
            <span style={{ color: "#5f6368" }}>52W Range:</span>{" "}
            <span style={{ fontWeight: 600, color: "#202124" }}>
              {detail.low_52w && detail.high_52w ? `$${detail.low_52w.toFixed(0)} - $${detail.high_52w.toFixed(0)}` : "N/A"}
            </span>
          </div>
          <div>
            <span style={{ color: "#5f6368" }}>6M Range:</span>{" "}
            <span style={{ fontWeight: 600, color: "#202124" }}>
              {detail.low_6m && detail.high_6m ? `$${detail.low_6m.toFixed(0)} - $${detail.high_6m.toFixed(0)}` : "N/A"}
            </span>
          </div>
        </div>
      </div>

      {/* Prominent Openable Hub Button (14 Factors) */}
      <button
        onClick={() => setShowHubModal(true)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          background: "linear-gradient(135deg, #1a73e8 0%, #174ea6 100%)",
          color: "#fff",
          border: "none",
          borderRadius: 8,
          padding: "10px 14px",
          fontSize: 13,
          fontWeight: 600,
          cursor: "pointer",
          marginBottom: 16,
          boxShadow: "0 2px 4px rgba(26, 115, 232, 0.2)",
          transition: "all 0.2s ease",
        }}
      >
        <Activity size={16} /> Open Indicator & Technical Hub (14 Factors)
      </button>

      {/* Reference Technical Levels & Options Profiler Card */}
      <div style={{ background: "#f8f9fa", borderRadius: 8, padding: "12px 14px", marginBottom: 16, border: "1px solid #e8eaed" }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "#202124", marginBottom: 8, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span>Reference Technical Levels</span>
          <span style={{ fontSize: 10, background: "#e8f0fe", color: "#1a73e8", padding: "2px 6px", borderRadius: 4, fontWeight: 600 }}>
            Live Market Feed
          </span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 12, marginBottom: 8 }}>
          <div>
            <span style={{ color: "#5f6368" }}>Observed Reference:</span><br />
            <span style={{ fontWeight: 600, color: "#202124" }}>${detail.price.toFixed(2)}</span>
          </div>
          <div>
            <span style={{ color: "#5f6368" }}>Support Reference:</span><br />
            <span style={{ fontWeight: 600, color: "#188038" }}>${(detail.price * 0.98).toFixed(2)} (MA Ref)</span>
          </div>
        </div>

        <div style={{ borderTop: "1px solid #e8eaed", paddingTop: 8 }}>
          <div style={{ fontSize: 12, color: "#5f6368", marginBottom: 6 }}>Target Options Strike Reference (30-45 DTE):</div>
          {localStrike ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: "#e6f4ea", padding: "8px 10px", borderRadius: 6, border: "1px solid #ceead6" }}>
              <span style={{ fontWeight: 700, color: "#137333", fontSize: 13 }}>
                ${localStrike.toFixed(2)} {aiSelection?.contract_type || "Call/Put"}
              </span>
              <span style={{ fontSize: 11, color: "#137333", fontWeight: 600 }}>
                Reference Strike
              </span>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: 11.5, color: "#5f6368", fontWeight: 500, marginBottom: 8, display: "flex", alignItems: "center", gap: 4 }}>
                <Info size={14} /> Optional: Scan Live Broker Options Chain
              </div>
              
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 6,
                  background: uploadingChain ? "#f1f3f4" : "#1a73e8",
                  color: uploadingChain ? "#5f6368" : "#fff",
                  padding: "9px 12px",
                  borderRadius: 6,
                  fontSize: 12.5,
                  fontWeight: 600,
                  cursor: uploadingChain ? "not-allowed" : "pointer",
                  transition: "all 0.2s",
                  boxShadow: "0 1px 2px rgba(0,0,0,0.1)",
                }}
              >
                {uploadingChain ? (
                  <>
                    <Loader2 size={14} className="animate-spin" /> Scanning Chain Image...
                  </>
                ) : (
                  <>
                    <Upload size={14} /> Upload Broker Options Chain
                  </>
                )}
                <input
                  type="file"
                  accept="image/*"
                  disabled={uploadingChain}
                  style={{ display: "none" }}
                  onChange={handleFileChange}
                />
              </label>
            </div>
          )}

          {aiSelection && aiSelection.reasoning && (
            <div style={{ marginTop: 8, fontSize: 11, color: "#3c4043", background: "#fff", padding: "10px", borderRadius: 6, border: "1px solid #e8eaed", lineHeight: 1.45 }}>
              <div style={{ fontWeight: 600, color: "#1a73e8", marginBottom: 4, display: "flex", alignItems: "center", gap: 4 }}>
                <Sparkles size={13} /> Options Chain Sensitivity Profile ({aiSelection.expiration || "35 DTE"} | Delta {aiSelection.delta || "~0.38"}):
              </div>
              {aiSelection.reasoning}
              {aiSelection.open_interest && (
                <div style={{ marginTop: 6, color: "#5f6368", fontSize: 10.5, fontWeight: 500 }}>
                  OI: {aiSelection.open_interest} | Bid/Ask: {aiSelection.bid_ask || "Tight"}
                </div>
              )}
            </div>
          )}

          {onAddPaperTrade && (
            <div style={{ borderTop: "1px solid #e8eaed", marginTop: 10, paddingTop: 10 }}>
              <div style={{ fontSize: 11.5, fontWeight: 600, color: "#5f6368", marginBottom: 6 }}>
                Simulate in Paper Portfolio:
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  disabled={addingStock || addingOption}
                  onClick={async () => {
                    setPaperMessage(null);
                    setPaperError(null);
                    setAddingStock(true);
                    try {
                      await onAddPaperTrade({
                        symbol: detail.symbol,
                        entryPrice: detail.price,
                        qty: 1,
                      });
                      setPaperMessage(`Added ${detail.symbol} Stock to paper portfolio.`);
                    } catch (err: any) {
                      setPaperError(err?.message || "Failed to add stock position.");
                    } finally {
                      setAddingStock(false);
                    }
                  }}
                  style={{
                    flex: 1,
                    padding: "6px 10px",
                    fontSize: 11.5,
                    fontWeight: 600,
                    borderRadius: 6,
                    border: "1px solid #1a73e8",
                    background: "#e8f0fe",
                    color: "#1a73e8",
                    cursor: "pointer",
                  }}
                >
                  {addingStock ? "Adding..." : `+ Paper Stock ($${detail.price.toFixed(2)})`}
                </button>

                {localStrike ? (
                  <button
                    disabled={addingStock || addingOption}
                    onClick={async () => {
                      setPaperMessage(null);
                      setPaperError(null);
                      setAddingOption(true);
                      try {
                        const isCall = !(aiSelection?.contract_type || "").toLowerCase().includes("put");
                        const occSym = formatOccSymbol(detail.symbol, localStrike, isCall);
                        const estPrice = Math.round(Math.max(1.5, detail.price * 0.03) * 100) / 100;
                        await onAddPaperTrade({
                          symbol: occSym,
                          entryPrice: estPrice,
                          qty: 1,
                        });
                        setPaperMessage(`Added Option ${occSym} ($${localStrike} Strike) to paper portfolio.`);
                      } catch (err: any) {
                        setPaperError(err?.message || "Failed to add option position.");
                      } finally {
                        setAddingOption(false);
                      }
                    }}
                    style={{
                      flex: 1,
                      padding: "6px 10px",
                      fontSize: 11.5,
                      fontWeight: 600,
                      borderRadius: 6,
                      border: "1px solid #137333",
                      background: "#e6f4ea",
                      color: "#137333",
                      cursor: "pointer",
                    }}
                  >
                    {addingOption ? "Adding..." : `+ Paper Option ($${localStrike.toFixed(2)})`}
                  </button>
                ) : null}
              </div>

              {paperMessage && (
                <div style={{ marginTop: 6, fontSize: 11, color: "#137333", fontWeight: 500 }}>
                  {paperMessage}
                </div>
              )}
              {paperError && (
                <div style={{ marginTop: 6, fontSize: 11, color: "#c5221f", fontWeight: 500 }}>
                  {paperError}
                </div>
              )}
            </div>
          )}

          {uploadError && (
            <div style={{ marginTop: 8, fontSize: 11, color: "#c5221f", background: "#fce8e6", padding: "8px 10px", borderRadius: 6, border: "1px solid #fad2cf" }}>
              {uploadError}
            </div>
          )}
        </div>
      </div>

      {/* Layer Scores Bar Chart */}
      <div style={{ fontSize: 12, fontWeight: 600, color: "#202124", marginBottom: 6 }}>10-Layer Factor Scores</div>
      <ResponsiveContainer width="100%" height={110}>
        <BarChart data={layerData} margin={{ top: 0, right: 0, left: -24, bottom: 0 }}>
          <XAxis dataKey="layer" tick={{ fontSize: 9, fill: "#80868b" }} interval={0} angle={-35} textAnchor="end" height={40} />
          <YAxis hide domain={[0, 10]} />
          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e8eaed", background: "#fff" }} />
          <Bar dataKey="val" radius={[3, 3, 0, 0]}>
            {layerData.map((d, i) => (
              <Cell key={i} fill={d.val >= 7 ? "#188038" : d.val >= 5 ? "#f9ab00" : "#c5221f"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <button
        onClick={onOpenFactors}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 13,
          color: "#1a73e8",
          background: "none",
          border: "none",
          cursor: "pointer",
          padding: "10px 0",
          fontWeight: 500,
        }}
      >
        <Info size={14} /> View full 50-factor breakdown <ExternalLink size={12} />
      </button>

      {/* Factor Observations & Synthesis */}
      <div style={{ fontSize: 12, fontWeight: 600, color: "#202124", margin: "10px 0 8px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span>Observed Factor Drivers</span>
        {onAskAi && (
          <button
            onClick={() => onAskAi(`Summarize technical factor observations and risk characteristics for ${detail.symbol}`)}
            style={{ background: "none", border: "none", color: "#1a73e8", fontSize: 11, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}
          >
            <Sparkles size={12} /> Ask AI
          </button>
        )}
      </div>
      
      {loadingSynthesis ? (
        <div style={{ padding: "12px 0", display: "flex", alignItems: "center", gap: 8, color: "#1a73e8", fontSize: 13, fontWeight: 500 }}>
          <Loader2 size={16} className="animate-spin" /> Synthesizing factor observations...
        </div>
      ) : reasons.length > 0 ? (
        reasons.map((r: any, i: number) => {
          const text = typeof r === "string" ? r : r.text;
          const type = typeof r === "object" && r.type ? r.type : "neutral";
          const code = typeof r === "object" && r.factor ? r.factor : (r as any).code || (type === "bear" ? "F41" : "F44");
          return (
            <div key={i} style={{ display: "flex", gap: 8, marginBottom: 10, alignItems: "flex-start" }}>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: "#fff",
                  background: reasonColor[type] || "#5f6368",
                  borderRadius: 4,
                  padding: "2px 6px",
                  flexShrink: 0,
                  marginTop: 1,
                }}
              >
                {code}
              </span>
              <span style={{ fontSize: 12.5, color: "#3c4043", lineHeight: 1.45 }}>{text}</span>
            </div>
          );
        })
      ) : (
        <div style={{ fontSize: 12, color: "#80868b", fontStyle: "italic", marginBottom: 10 }}>
          No specific vetoes or risk conditions triggered.
        </div>
      )}

      {/* Sourced News Feed */}
      <div style={{ fontSize: 12, fontWeight: 600, color: "#202124", margin: "16px 0 10px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <Newspaper size={13} color="#1a73e8" /> <span>Sourced News & Catalysts</span>
        </div>
        <div style={{ display: "flex", gap: 2, background: "#f1f3f4", padding: 2, borderRadius: 6 }}>
          <button
            onClick={() => setNewsViewMode("cards")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              padding: "3px 8px",
              borderRadius: 4,
              border: "none",
              background: newsViewMode === "cards" ? "#fff" : "transparent",
              color: newsViewMode === "cards" ? "#1a73e8" : "#5f6368",
              fontSize: 11,
              fontWeight: 600,
              cursor: "pointer",
              boxShadow: newsViewMode === "cards" ? "0 1px 2px rgba(0,0,0,0.1)" : "none",
            }}
          >
            <LayoutGrid size={11} /> Swipe Digest
          </button>
          <button
            onClick={() => setNewsViewMode("list")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              padding: "3px 8px",
              borderRadius: 4,
              border: "none",
              background: newsViewMode === "list" ? "#fff" : "transparent",
              color: newsViewMode === "list" ? "#1a73e8" : "#5f6368",
              fontSize: 11,
              fontWeight: 600,
              cursor: "pointer",
              boxShadow: newsViewMode === "list" ? "0 1px 2px rgba(0,0,0,0.1)" : "none",
            }}
          >
            <List size={11} /> List
          </button>
        </div>
      </div>

      {loadingSynthesis ? (
        <div style={{ padding: "12px 12px", backgroundColor: "#f8fafd", border: "1px solid #e8f0fe", borderRadius: 8, marginBottom: 12, display: "flex", gap: 8, alignItems: "center", color: "#1a73e8", fontSize: 12 }}>
          <Loader2 size={15} className="animate-spin" /> Synthesizing market catalysts...
        </div>
      ) : newsSummary ? (
        <div style={{
          padding: "10px 12px",
          backgroundColor: "#f8fafd",
          border: "1px solid #e8f0fe",
          borderRadius: 8,
          marginBottom: 12,
          display: "flex",
          gap: 8,
          alignItems: "flex-start",
        }}>
          <Sparkles size={15} color="#1a73e8" style={{ marginTop: 2, flexShrink: 0 }} />
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: "#1a73e8", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 4 }}>
              Catalyst Context
            </div>
            <div style={{ fontSize: 12.5, color: "#3c4043", lineHeight: 1.4 }}>
              {newsSummary}
            </div>
          </div>
        </div>
      ) : null}

      {newsViewMode === "cards" ? (
        <NewsSwipeDigest
          symbol={detail.symbol}
          companyName={detail.name}
          news={detail.news || []}
          pctChange={detail.pct}
        />
      ) : detail.news && detail.news.length > 0 ? (
        detail.news.map((n, i) => {
          const title = n.headline;
          const source = n.source || "News";
          let time = "Today";
          if (n.publishedAt) {
            if (/^\d+$/.test(String(n.publishedAt))) {
              const num = Number(n.publishedAt);
              time = new Date(String(n.publishedAt).length <= 10 ? num * 1000 : num).toLocaleDateString();
            } else {
              const d = new Date(n.publishedAt);
              time = isNaN(d.getTime()) ? "Today" : d.toLocaleDateString();
            }
          }
          const url = n.url || "#";
          return (
            <div key={i} style={{ marginBottom: 10, paddingBottom: 10, borderBottom: i < detail.news.length - 1 ? "1px solid #f1f3f4" : "none" }}>
              <a href={url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none", color: "inherit" }}>
                <div style={{ fontSize: 12.5, color: "#202124", lineHeight: 1.4, fontWeight: 500 }}>{title}</div>
                <div style={{ fontSize: 11, color: "#80868b", marginTop: 2 }}>
                  {source} · {time}
                </div>
              </a>
            </div>
          );
        })
      ) : (
        <div style={{ fontSize: 12, color: "#80868b", fontStyle: "italic" }}>
          No recent news catalysts found.
        </div>
      )}

      {/* Compliance Disclaimer at Bottom of Panel */}
      <div style={{ marginTop: 24, padding: "10px 12px", background: "#f8f9fa", borderRadius: 8, border: "1px solid #e8eaed", display: "flex", gap: 8, alignItems: "center", fontSize: 11, color: "#5f6368" }}>
        <ShieldAlert size={14} color="#f2994a" style={{ flexShrink: 0 }} />
        <span>For educational and market research purposes only. Not investment advice.</span>
      </div>

      {/* 14-Factor Indicator Hub Modal */}
      <TechnicalIndicatorHubModal
        stock={detail}
        isOpen={showHubModal}
        onClose={() => setShowHubModal(false)}
      />
    </div>
  );
}
