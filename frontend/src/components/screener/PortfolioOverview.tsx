"use client";
import React from "react";
import { PortfolioOptimizationResponse, PortfolioScoreResponse } from "@/types/stockglass";
import { AlertTriangle, Gauge, ShieldAlert, Target } from "lucide-react";

interface PortfolioOverviewProps {
  score: PortfolioScoreResponse | null;
  optimization: PortfolioOptimizationResponse | null;
  loading: boolean;
  error?: string | null;
}

const bandColor: Record<string, { bg: string; fg: string; border: string }> = {
  WELL_OPTIMIZED: { bg: "#e6f4ea", fg: "#137333", border: "#ceead6" },
  HEALTHY_WITH_FLAGS: { bg: "#fef7e0", fg: "#b06000", border: "#fce8b2" },
  NEEDS_REBALANCING: { bg: "#fce8e6", fg: "#c5221f", border: "#fad2cf" },
  URGENT: { bg: "#fce8e6", fg: "#a50e0e", border: "#fad2cf" },
  DATA_NOT_AVAILABLE: { bg: "#f1f3f4", fg: "#5f6368", border: "#dadce0" },
};

function formatBand(band: string): string {
  const map: Record<string, string> = {
    WELL_OPTIMIZED: "Balanced Risk Profile",
    HEALTHY_WITH_FLAGS: "Moderate Concentration",
    NEEDS_REBALANCING: "High Sector Dispersion",
    URGENT: "Elevated Single-Stock Risk",
    DATA_NOT_AVAILABLE: "Awaiting Position Data",
  };
  return map[band] || band.replace(/_/g, " ");
}

export function PortfolioOverview({ score, optimization, loading, error }: PortfolioOverviewProps) {

  const band = score?.band || "DATA_NOT_AVAILABLE";
  const colors = bandColor[band] || bandColor.DATA_NOT_AVAILABLE;
  const topComponents = (score?.components || []).slice().sort((a, b) => {
    const av = a.score ?? -1;
    const bv = b.score ?? -1;
    return av - bv;
  }).slice(0, 4);
  const topActions = (optimization?.actions || []).slice(0, 4);

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
            <div style={{ fontSize: 13, fontWeight: 700, color: "#202124" }}>Risk Dispersion Score</div>
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
            </>
          )}

          <div style={{ marginTop: 14, background: "#fff", border: "1px solid #e8eaed", borderRadius: 10, padding: 12 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#202124", marginBottom: 6 }}>Paper Trading Entry</div>
            <div style={{ fontSize: 12, color: "#5f6368", lineHeight: 1.45 }}>
              Add positions directly from the screener list using the <span style={{ color: "#1a73e8", fontWeight: 700 }}>+ Paper</span> action on each stock row.
            </div>
          </div>
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
          ) : error ? (
            <div style={{ fontSize: 13, color: "#c5221f" }}>{error}</div>
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
            <div style={{ fontSize: 13, fontWeight: 700, color: "#202124" }}>Factor Insights & Risk Alerts</div>
          </div>
          {loading ? (
            <div style={{ display: "grid", gap: 8 }}>
              <div className="skeleton-pulse skeleton-block" style={{ height: 64 }} />
              <div className="skeleton-pulse skeleton-block" style={{ height: 64 }} />
            </div>
          ) : error ? (
            <div style={{ fontSize: 13, color: "#c5221f" }}>{error}</div>
          ) : topActions.length === 0 ? (
            <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12, color: "#5f6368", background: "#fff", border: "1px solid #e8eaed", borderRadius: 10, padding: "10px 12px" }}>
              <AlertTriangle size={14} color="#5f6368" />
              No risk alerts active for the current paper book.
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
