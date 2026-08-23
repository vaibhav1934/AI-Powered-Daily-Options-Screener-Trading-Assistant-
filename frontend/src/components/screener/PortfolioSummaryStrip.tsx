"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ArrowRight, Gauge, ShieldAlert, ChevronDown, ChevronUp } from "lucide-react";
import { PortfolioOptimizationResponse, PortfolioScoreResponse } from "@/types/stockglass";

interface PortfolioSummaryStripProps {
  score: PortfolioScoreResponse | null;
  optimization: PortfolioOptimizationResponse | null;
  loading: boolean;
  error?: string | null;
  isMobile?: boolean;
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

export function PortfolioSummaryStrip({ score, optimization, loading, error, isMobile }: PortfolioSummaryStripProps) {
  const [mobileExpanded, setMobileExpanded] = useState(false);
  const band = score?.band || "DATA_NOT_AVAILABLE";
  const colors = bandColor[band] || bandColor.DATA_NOT_AVAILABLE;
  const weakest = (score?.components || [])
    .slice()
    .sort((a, b) => (a.score ?? 999) - (b.score ?? 999))
    .slice(0, 2);
  const actionCount = optimization?.actions?.length || 0;

  if (isMobile) {
    return (
      <div style={{ maxWidth: 1400, margin: "6px auto 0", width: "100%", padding: "0 12px", boxSizing: "border-box", flexShrink: 0 }}>
        <div style={{ border: "1px solid #e8eaed", borderRadius: 12, padding: "8px 12px", background: "linear-gradient(180deg, #ffffff 0%, #fbfcff 100%)", boxShadow: "0 1px 3px rgba(0,0,0,0.03)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "nowrap", overflow: "hidden" }}>
              <Gauge size={15} color="#1a73e8" style={{ flexShrink: 0 }} />
              <span style={{ fontSize: 14, fontWeight: 700, color: "#202124" }}>
                {score?.compositeScore != null ? score.compositeScore.toFixed(1) : "N/A"}
              </span>
              <span style={{ background: colors.bg, color: colors.fg, border: `1px solid ${colors.border}`, borderRadius: 999, padding: "2px 7px", fontSize: 10, fontWeight: 700, whiteSpace: "nowrap" }}>
                {formatBand(band)}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
              <Link
                href="/portfolio"
                style={{ padding: "4px 9px", borderRadius: 8, background: "#1a73e8", color: "#fff", fontSize: 11, fontWeight: 600, textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 4 }}
              >
                Portfolio <ArrowRight size={11} />
              </Link>
              {weakest.length > 0 && (
                <button
                  onClick={() => setMobileExpanded((v) => !v)}
                  style={{ background: "none", border: "none", padding: "4px 2px", cursor: "pointer", color: "#5f6368", display: "flex", alignItems: "center" }}
                  aria-label="Toggle portfolio details"
                >
                  {mobileExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </button>
              )}
            </div>
          </div>
          {mobileExpanded && weakest.length > 0 && (
            <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid #e8eaed", display: "flex", gap: 6, flexWrap: "wrap" }}>
              <span style={{ fontSize: 10.5, color: "#5f6368", width: "100%", fontWeight: 600, textTransform: "uppercase" }}>Watch Items:</span>
              {weakest.map((c) => (
                <div key={c.name} style={{ background: "#fff", border: "1px solid #e8eaed", borderRadius: 999, padding: "2px 8px", fontSize: 11, color: "#3c4043" }}>
                  <span>{c.name}: </span>
                  <span style={{ color: "#c5221f", fontWeight: 700 }}>{c.score != null ? c.score.toFixed(1) : "N/A"}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

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
        className="portfolio-summary-grid portfolio-summary-minheight"
        style={{
          border: "1px solid #e8eaed",
          borderRadius: 14,
          padding: "12px 16px",
          background: "linear-gradient(180deg, #ffffff 0%, #fbfcff 100%)",
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <Gauge size={16} color="#1a73e8" />
            <div style={{ fontSize: 12, fontWeight: 700, color: "#202124", textTransform: "uppercase", letterSpacing: 0.4 }}>
              Portfolio Risk Alignment
            </div>
          </div>
          {loading ? (
            <div style={{ display: "grid", gap: 8, maxWidth: 340 }}>
              <div className="skeleton-pulse skeleton-line-md" style={{ width: "38%" }} />
              <div className="skeleton-pulse skeleton-line" style={{ width: "72%" }} />
            </div>
          ) : error ? (
            <div style={{ fontSize: 12, color: "#c5221f" }}>{error}</div>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <div style={{ fontSize: 28, fontWeight: 700, color: "#202124", lineHeight: 1 }}>
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
              <div style={{ fontSize: 12, color: "#5f6368" }}>
                {score?.missingComponents?.length
                  ? `Missing: ${score.missingComponents.join(", ")}`
                  : `${actionCount} analytical insight${actionCount === 1 ? "" : "s"}`}
              </div>
            </div>
          )}
        </div>

        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <ShieldAlert size={16} color="#b06000" />
            <div style={{ fontSize: 12, fontWeight: 700, color: "#202124", textTransform: "uppercase", letterSpacing: 0.4 }}>
              Top Watch Items
            </div>
          </div>
          {loading ? (
            <div style={{ display: "grid", gap: 8 }}>
              <div className="skeleton-pulse skeleton-line" style={{ width: "64%" }} />
              <div style={{ display: "flex", gap: 8 }}>
                <div className="skeleton-pulse skeleton-line" style={{ width: 94, height: 28, borderRadius: 999 }} />
                <div className="skeleton-pulse skeleton-line" style={{ width: 108, height: 28, borderRadius: 999 }} />
              </div>
            </div>
          ) : error ? (
            <div style={{ fontSize: 12, color: "#c5221f" }}>{error}</div>
          ) : weakest.length === 0 ? (
            <div style={{ fontSize: 12, color: "#5f6368" }}>
              No book-level issues yet. Add a paper position to activate portfolio analytics.
            </div>
          ) : (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {weakest.map((component) => (
                <div
                  key={component.name}
                  style={{
                    background: "#fff",
                    border: "1px solid #e8eaed",
                    borderRadius: 999,
                    padding: "6px 10px",
                    fontSize: 12,
                    color: "#3c4043",
                  }}
                >
                  <span style={{ fontWeight: 700 }}>{component.name}</span>
                  <span style={{ marginLeft: 6, color: "#c5221f", fontWeight: 700 }}>
                    {component.score != null ? component.score.toFixed(1) : "N/A"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <Link
            href="/portfolio"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "10px 14px",
              borderRadius: 12,
              background: "#1a73e8",
              color: "#fff",
              fontSize: 12,
              fontWeight: 700,
              textDecoration: "none",
              boxShadow: "0 8px 20px rgba(26,115,232,0.16)",
            }}
          >
            Open Portfolio Workspace <ArrowRight size={14} />
          </Link>
        </div>
      </div>
    </div>
  );
}
