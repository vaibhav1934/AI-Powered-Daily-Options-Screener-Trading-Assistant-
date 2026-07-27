"use client";
import React from "react";
import { Sparkles } from "lucide-react";

interface QuickFiltersProps {
  showFilters: boolean;
  activeSector: string;
  onSectorToggle: (sector: string) => void;
  minScore: number;
  onMinScoreChange: (score: number) => void;
  activeQuick: string | null;
  onQuickChange: (quick: string | null) => void;
  sectors?: string[];
  onClearAll?: () => void;
  riskBucket: string;
  onRiskBucketChange: (bucket: string) => void;
}

const QUICK_FILTERS = [
  { id: "highConviction", label: "High conviction (7+)", icon: "★" },
  { id: "gainers", label: "Today's gainers", icon: "↑" },
  { id: "losers", label: "Today's losers", icon: "↓" },
  { id: "earningsSoon", label: "Earnings today", icon: "⚡" },
  { id: "clear", label: "Clear filters", icon: "×" },
];

const RISK_BUCKETS = [
  { id: "", label: "All Risk" },
  { id: "LOW", label: "Low Risk" },
  { id: "MODERATE", label: "Moderate" },
  { id: "HIGH_RISK_HALO", label: "Halo" },
];

export function QuickFilters({
  showFilters,
  activeSector,
  onSectorToggle,
  minScore,
  onMinScoreChange,
  activeQuick,
  onQuickChange,
  sectors = [],
  onClearAll,
  riskBucket,
  onRiskBucketChange,
}: QuickFiltersProps) {
  const applyQuickFilter = (id: string) => {
    if (id === "clear") {
      if (onClearAll) onClearAll();
      else {
        onSectorToggle("");
        onMinScoreChange(0);
        onQuickChange(null);
        onRiskBucketChange("");
      }
      return;
    }
    // Toggle off if already active
    if (activeQuick === id) {
      onQuickChange(null);
      onMinScoreChange(0);
      return;
    }
    onQuickChange(id);
    if (id === "highConviction") {
      onMinScoreChange(7);
      onSectorToggle("");
    } else {
      onMinScoreChange(0);
      onSectorToggle("");
    }
  };

  return (
    <div style={{ background: "#fff", flexShrink: 0 }}>
      {/* Quick prompts */}
      <div style={{ padding: "14px 24px 0", display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: "#80868b", marginRight: 4 }}>
          <Sparkles size={13} /> Try:
        </span>
        {QUICK_FILTERS.map((qf) => (
          <button
            key={qf.id}
            onClick={() => applyQuickFilter(qf.id)}
            style={{
              fontSize: 12.5,
              padding: "6px 12px",
              borderRadius: 16,
              cursor: "pointer",
              border: "1px solid " + (activeQuick === qf.id ? "#1a73e8" : "#e8eaed"),
              background: activeQuick === qf.id ? "#e8f0fe" : "#fff",
              color: activeQuick === qf.id ? "#1a73e8" : "#3c4043",
              fontWeight: 500,
              transition: "all 0.15s ease",
            }}
          >
            {qf.icon} {qf.label}
          </button>
        ))}

        {/* Risk Bucket pills */}
        <span style={{ width: 1, height: 18, background: "#e8eaed", margin: "0 4px" }} />
        {RISK_BUCKETS.map((rb) => (
          <button
            key={rb.id}
            onClick={() => onRiskBucketChange(riskBucket === rb.id ? "" : rb.id)}
            style={{
              fontSize: 12.5,
              padding: "6px 12px",
              borderRadius: 16,
              cursor: "pointer",
              border: "1px solid " + (riskBucket === rb.id && rb.id !== "" ? "#34a853" : "#e8eaed"),
              background: riskBucket === rb.id && rb.id !== "" ? "#e6f4ea" : "#fff",
              color: riskBucket === rb.id && rb.id !== "" ? "#188038" : "#3c4043",
              fontWeight: 500,
              transition: "all 0.15s ease",
              display: rb.id === "" && riskBucket === "" ? "none" : "inline-block",
            }}
          >
            {rb.label}
          </button>
        ))}
      </div>

      {/* Filter panel */}
      {showFilters && (
        <div style={{ margin: "12px 24px 12px", padding: "14px 16px", border: "1px solid #e8eaed", borderRadius: 10, background: "#f8f9fa" }}>
          {/* Sector pills — dynamically from real DB data */}
          {sectors.length > 0 && (
            <>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#5f6368", marginBottom: 8, letterSpacing: 0.5 }}>SECTOR (from live scan)</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
                {sectors.map((s) => {
                  const isActive = activeSector === s;
                  return (
                    <button
                      key={s}
                      onClick={() => onSectorToggle(isActive ? "" : s)}
                      style={{
                        fontSize: 12.5,
                        padding: "5px 12px",
                        borderRadius: 14,
                        cursor: "pointer",
                        border: "1px solid " + (isActive ? "#1a73e8" : "#dadce0"),
                        background: isActive ? "#1a73e8" : "#fff",
                        color: isActive ? "#fff" : "#3c4043",
                        fontWeight: 500,
                        transition: "all 0.15s ease",
                      }}
                    >
                      {s}
                    </button>
                  );
                })}
              </div>
            </>
          )}
          <div style={{ fontSize: 12, fontWeight: 600, color: "#5f6368", marginBottom: 8, letterSpacing: 0.5 }}>
            MINIMUM FRAMEWORK SCORE: <span style={{ color: "#1a73e8" }}>{minScore.toFixed(1)}</span>
          </div>
          <input
            type="range"
            min="0"
            max="10"
            step="0.5"
            value={minScore}
            onChange={(e) => {
              onQuickChange(null);
              onMinScoreChange(parseFloat(e.target.value));
            }}
            style={{ width: 280, accentColor: "#1a73e8", cursor: "pointer" }}
          />
        </div>
      )}
    </div>
  );
}
