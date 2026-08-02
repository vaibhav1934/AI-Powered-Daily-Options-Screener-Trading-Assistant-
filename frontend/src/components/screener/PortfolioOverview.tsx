"use client";
import React from "react";
import { useEffect, useState } from "react";
import { PortfolioOptimizationResponse, PortfolioScoreResponse } from "@/types/stockglass";
import { AlertTriangle, Gauge, ShieldAlert, Target } from "lucide-react";
import { createPaperPosition } from "@/lib/stockglass_api";

interface PortfolioOverviewProps {
  score: PortfolioScoreResponse | null;
  optimization: PortfolioOptimizationResponse | null;
  loading: boolean;
  error?: string | null;
  selectedSymbol?: string;
  selectedPrice?: number | null;
  onRefresh?: () => Promise<void> | void;
}

const bandColor: Record<string, { bg: string; fg: string; border: string }> = {
  WELL_OPTIMIZED: { bg: "#e6f4ea", fg: "#137333", border: "#ceead6" },
  HEALTHY_WITH_FLAGS: { bg: "#fef7e0", fg: "#b06000", border: "#fce8b2" },
  NEEDS_REBALANCING: { bg: "#fce8e6", fg: "#c5221f", border: "#fad2cf" },
  URGENT: { bg: "#fce8e6", fg: "#a50e0e", border: "#fad2cf" },
  DATA_NOT_AVAILABLE: { bg: "#f1f3f4", fg: "#5f6368", border: "#dadce0" },
};

function formatBand(band: string): string {
  return band.replace(/_/g, " ");
}

export function PortfolioOverview({ score, optimization, loading, error, selectedSymbol, selectedPrice, onRefresh }: PortfolioOverviewProps) {
  const [symbol, setSymbol] = useState(selectedSymbol || "");
  const [qty, setQty] = useState("10");
  const [entryPrice, setEntryPrice] = useState(selectedPrice ? String(Number(selectedPrice.toFixed(2))) : "");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);

  useEffect(() => {
    if (selectedSymbol) {
      setSymbol((prev) => prev || selectedSymbol);
    }
  }, [selectedSymbol]);

  useEffect(() => {
    if (selectedPrice && Number.isFinite(selectedPrice)) {
      setEntryPrice((prev) => prev || String(Number(selectedPrice.toFixed(2))));
    }
  }, [selectedPrice]);

  const band = score?.band || "DATA_NOT_AVAILABLE";
  const colors = bandColor[band] || bandColor.DATA_NOT_AVAILABLE;
  const topComponents = (score?.components || []).slice().sort((a, b) => {
    const av = a.score ?? -1;
    const bv = b.score ?? -1;
    return av - bv;
  }).slice(0, 4);
  const topActions = (optimization?.actions || []).slice(0, 4);

  const handleCreatePosition = async () => {
    setSubmitError(null);
    setSubmitMessage(null);

    const parsedQty = Number(qty);
    const parsedEntry = Number(entryPrice);
    if (!symbol.trim()) {
      setSubmitError("Enter a symbol to open a paper position.");
      return;
    }
    if (!Number.isFinite(parsedQty) || parsedQty <= 0) {
      setSubmitError("Quantity must be a positive number.");
      return;
    }
    if (!Number.isFinite(parsedEntry) || parsedEntry <= 0) {
      setSubmitError("Entry price must be a positive number.");
      return;
    }

    setSubmitting(true);
    try {
      await createPaperPosition({
        symbol: symbol.trim().toUpperCase(),
        qty: parsedQty,
        entryPrice: parsedEntry,
      });
      setSubmitMessage(`Paper position opened for ${symbol.trim().toUpperCase()}.`);
      if (onRefresh) {
        await onRefresh();
      }
    } catch (err: any) {
      setSubmitError(err?.message || "Failed to create paper position.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        maxWidth: 1400,
        margin: "8px auto 0",
        width: "100%",
        padding: "0 24px",
        boxSizing: "border-box",
      }}
    >
      <div
        className="portfolio-overview-grid"
        style={{
          border: "1px solid #e8eaed",
          borderRadius: 14,
          background: "linear-gradient(180deg, #ffffff 0%, #f8f9fa 100%)",
          padding: 16,
        }}
      >
        <div className="portfolio-card-minheight" style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <Gauge size={16} color="#1a73e8" />
            <div style={{ fontSize: 13, fontWeight: 700, color: "#202124" }}>Portfolio Score</div>
          </div>

          {loading ? (
            <div style={{ display: "grid", gap: 10 }}>
              <div className="skeleton-pulse skeleton-line-md" style={{ width: "36%" }} />
              <div className="skeleton-pulse skeleton-line" style={{ width: "82%" }} />
              <div className="skeleton-pulse skeleton-line" style={{ width: "74%" }} />
              <div className="skeleton-pulse skeleton-block" />
            </div>
          ) : error ? (
            <div style={{ fontSize: 13, color: "#c5221f" }}>{error}</div>
          ) : (
            <>
              <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
                <div style={{ fontSize: 34, fontWeight: 700, color: "#202124", lineHeight: 1 }}>
                  {score?.compositeScore != null ? score.compositeScore.toFixed(1) : "N/A"}
                </div>
                <div
                  style={{
                    background: colors.bg,
                    color: colors.fg,
                    border: `1px solid ${colors.border}`,
                    borderRadius: 999,
                    padding: "4px 10px",
                    fontSize: 11,
                    fontWeight: 700,
                    textTransform: "uppercase",
                  }}
                >
                  {formatBand(band)}
                </div>
              </div>
              <div style={{ fontSize: 12, color: "#5f6368", marginTop: 8, lineHeight: 1.45 }}>
                {score?.missingComponents?.length
                  ? `Missing: ${score.missingComponents.join(", ")}`
                  : "Composite portfolio health from concentration, return quality, liquidity, greeks, conviction, and tax structure."}
              </div>

              <div style={{ marginTop: 14, background: "#fff", border: "1px solid #e8eaed", borderRadius: 10, padding: 12 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: "#202124", marginBottom: 8 }}>Open Paper Position</div>
                <div className="portfolio-form-grid">
                  <div>
                    <div style={{ fontSize: 11, color: "#5f6368", marginBottom: 4 }}>Symbol</div>
                    <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} placeholder="NVDA" style={{ width: "100%", padding: "8px 10px", borderRadius: 8, border: "1px solid #dadce0", fontSize: 12, outline: "none", boxSizing: "border-box" }} />
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: "#5f6368", marginBottom: 4 }}>Qty</div>
                    <input value={qty} onChange={(e) => setQty(e.target.value)} inputMode="decimal" placeholder="10" style={{ width: "100%", padding: "8px 10px", borderRadius: 8, border: "1px solid #dadce0", fontSize: 12, outline: "none", boxSizing: "border-box" }} />
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: "#5f6368", marginBottom: 4 }}>Entry Price</div>
                    <input value={entryPrice} onChange={(e) => setEntryPrice(e.target.value)} inputMode="decimal" placeholder="178.42" style={{ width: "100%", padding: "8px 10px", borderRadius: 8, border: "1px solid #dadce0", fontSize: 12, outline: "none", boxSizing: "border-box" }} />
                  </div>
                  <button onClick={handleCreatePosition} disabled={submitting} style={{ height: 34, padding: "0 12px", borderRadius: 8, border: "none", background: submitting ? "#dadce0" : "#1a73e8", color: "#fff", fontSize: 12, fontWeight: 700, cursor: submitting ? "not-allowed" : "pointer" }}>
                    {submitting ? "Adding..." : "Add"}
                  </button>
                </div>
                {selectedSymbol && selectedPrice ? (
                  <div style={{ fontSize: 11, color: "#5f6368", marginTop: 8 }}>
                    Selected setup detected: {selectedSymbol} at ${selectedPrice.toFixed(2)}. You can edit before adding.
                  </div>
                ) : null}
                {submitError ? <div style={{ fontSize: 11, color: "#c5221f", marginTop: 8 }}>{submitError}</div> : null}
                {submitMessage ? <div style={{ fontSize: 11, color: "#137333", marginTop: 8 }}>{submitMessage}</div> : null}
              </div>
            </>
          )}
        </div>

        <div className="portfolio-card-minheight" style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <ShieldAlert size={16} color="#b06000" />
            <div style={{ fontSize: 13, fontWeight: 700, color: "#202124" }}>Weakest Components</div>
          </div>
          {loading ? (
            <div style={{ display: "grid", gap: 8 }}>
              <div className="skeleton-pulse skeleton-block" style={{ height: 62 }} />
              <div className="skeleton-pulse skeleton-block" style={{ height: 62 }} />
              <div className="skeleton-pulse skeleton-block" style={{ height: 62 }} />
            </div>
          ) : topComponents.length === 0 ? (
            <div style={{ fontSize: 12, color: "#5f6368" }}>No component data yet.</div>
          ) : (
            <div style={{ display: "grid", gap: 8 }}>
              {topComponents.map((component) => (
                <div key={component.name} style={{ background: "#fff", border: "1px solid #e8eaed", borderRadius: 10, padding: "8px 10px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "#202124" }}>{component.name}</div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: component.score != null && component.score >= 70 ? "#137333" : "#c5221f" }}>
                      {component.score != null ? component.score.toFixed(1) : "N/A"}
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: "#5f6368", marginTop: 4, lineHeight: 1.35 }}>{component.detail}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="portfolio-card-minheight" style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <Target size={16} color="#1a73e8" />
            <div style={{ fontSize: 13, fontWeight: 700, color: "#202124" }}>Optimizer Actions</div>
          </div>
          {loading ? (
            <div style={{ display: "grid", gap: 8 }}>
              <div className="skeleton-pulse skeleton-block" style={{ height: 64 }} />
              <div className="skeleton-pulse skeleton-block" style={{ height: 64 }} />
            </div>
          ) : topActions.length === 0 ? (
            <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12, color: "#5f6368", background: "#fff", border: "1px solid #e8eaed", borderRadius: 10, padding: "10px 12px" }}>
              <AlertTriangle size={14} color="#5f6368" />
              No optimizer actions fired for the current paper book.
            </div>
          ) : (
            <div style={{ display: "grid", gap: 8 }}>
              {topActions.map((action) => (
                <div key={`${action.priority}-${action.trigger}-${action.symbol || "book"}`} style={{ background: "#fff", border: "1px solid #e8eaed", borderRadius: 10, padding: "8px 10px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: "#202124" }}>
                      {action.action}{action.symbol ? ` • ${action.symbol}` : ""}
                    </div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: "#1a73e8" }}>P{action.priority}</div>
                  </div>
                  <div style={{ fontSize: 11, color: "#5f6368", marginTop: 4, lineHeight: 1.35 }}>{action.reason}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
