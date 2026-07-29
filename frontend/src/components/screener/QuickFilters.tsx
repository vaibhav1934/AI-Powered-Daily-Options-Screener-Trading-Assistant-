"use client";
import React, { useRef, useEffect } from "react";
import { Sparkles, X, SlidersHorizontal } from "lucide-react";
import { createPortal } from "react-dom";

interface QuickFiltersProps {
  showFilters: boolean;
  onToggleFilters: () => void;
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
  onToggleFilters,
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
  const filterBtnRef = useRef<HTMLButtonElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);

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

  // Close popup on outside click
  useEffect(() => {
    if (!showFilters) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (
        popupRef.current &&
        !popupRef.current.contains(e.target as Node) &&
        filterBtnRef.current &&
        !filterBtnRef.current.contains(e.target as Node)
      ) {
        onToggleFilters();
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showFilters, onToggleFilters]);

  // Centered modal style — always in the middle of the screen
  const getPopupStyle = (): React.CSSProperties => ({
    position: "fixed",
    top: "50%",
    left: "50%",
    transform: "translate(-50%, -50%)",
    zIndex: 1000,
  });

  const hasActiveFilters =
    activeSector !== "" || minScore > 0 || activeQuick !== null || riskBucket !== "";

  const filterPopup = showFilters
    ? createPortal(
        <>
          {/* Backdrop */}
          <div
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 999,
              background: "rgba(0,0,0,0.35)",
              backdropFilter: "blur(2px)",
            }}
            onClick={onToggleFilters}
          />

          {/* Popup card */}
          <div
            ref={popupRef}
            style={{
              ...getPopupStyle(),
              width: "90vw",
              maxWidth: 400,
              maxHeight: "85vh",
              display: "flex",
              flexDirection: "column",
              background: "#fff",
              borderRadius: 20,
              boxShadow:
                "0 24px 64px rgba(0,0,0,0.22), 0 4px 16px rgba(0,0,0,0.1)",
              border: "1px solid #e8eaed",
              overflow: "hidden",
              animation: "filterPopupIn 0.2s cubic-bezier(0.34,1.56,0.64,1)",
            }}
          >
            <style>{`
              @keyframes filterPopupIn {
                from { opacity: 0; transform: translate(-50%, -48%) scale(0.95); }
                to   { opacity: 1; transform: translate(-50%, -50%) scale(1); }
              }
            `}</style>

            {/* Header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "16px 20px",
                borderBottom: "1px solid #e8eaed",
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontWeight: 600,
                  fontSize: 14,
                  color: "#202124",
                }}
              >
                <SlidersHorizontal size={15} color="#1a73e8" />
                Advanced Filters
                {hasActiveFilters && (
                  <span
                    style={{
                      background: "#1a73e8",
                      color: "#fff",
                      fontSize: 10,
                      fontWeight: 700,
                      padding: "1px 6px",
                      borderRadius: 10,
                    }}
                  >
                    ACTIVE
                  </span>
                )}
              </div>
              <button
                onClick={onToggleFilters}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  padding: 4,
                  borderRadius: 8,
                  color: "#5f6368",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <X size={16} />
              </button>
            </div>

            {/* Body */}
            <div style={{ padding: "14px 16px 16px" }}>
              {/* Risk Bucket */}
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: "#80868b",
                  letterSpacing: 0.8,
                  marginBottom: 8,
                  textTransform: "uppercase",
                }}
              >
                Risk Bucket
              </div>
              <div
                style={{
                  display: "flex",
                  gap: 6,
                  flexWrap: "wrap",
                  marginBottom: 16,
                }}
              >
                {RISK_BUCKETS.filter((rb) => rb.id !== "").map((rb) => (
                  <button
                    key={rb.id}
                    onClick={() =>
                      onRiskBucketChange(riskBucket === rb.id ? "" : rb.id)
                    }
                    style={{
                      fontSize: 12.5,
                      padding: "5px 13px",
                      borderRadius: 14,
                      cursor: "pointer",
                      border:
                        "1px solid " +
                        (riskBucket === rb.id ? "#34a853" : "#dadce0"),
                      background:
                        riskBucket === rb.id ? "#e6f4ea" : "#f8f9fa",
                      color:
                        riskBucket === rb.id ? "#188038" : "#3c4043",
                      fontWeight: 500,
                      transition: "all 0.15s ease",
                    }}
                  >
                    {rb.label}
                  </button>
                ))}
              </div>

              {/* Quick Filters */}
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: "#80868b",
                  letterSpacing: 0.8,
                  marginBottom: 8,
                  textTransform: "uppercase",
                }}
              >
                Quick Presets
              </div>
              <div
                style={{
                  display: "flex",
                  gap: 6,
                  flexWrap: "wrap",
                  marginBottom: 16,
                }}
              >
                {QUICK_FILTERS.filter((qf) => qf.id !== "clear").map((qf) => (
                  <button
                    key={qf.id}
                    onClick={() => applyQuickFilter(qf.id)}
                    style={{
                      fontSize: 12.5,
                      padding: "5px 12px",
                      borderRadius: 14,
                      cursor: "pointer",
                      border:
                        "1px solid " +
                        (activeQuick === qf.id ? "#1a73e8" : "#dadce0"),
                      background:
                        activeQuick === qf.id ? "#e8f0fe" : "#f8f9fa",
                      color:
                        activeQuick === qf.id ? "#1a73e8" : "#3c4043",
                      fontWeight: 500,
                      transition: "all 0.15s ease",
                    }}
                  >
                    {qf.icon} {qf.label}
                  </button>
                ))}
              </div>

              {/* Sector */}
              {sectors.length > 0 && (
                <>
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      color: "#80868b",
                      letterSpacing: 0.8,
                      marginBottom: 8,
                      textTransform: "uppercase",
                    }}
                  >
                    Sector
                  </div>
                  <div
                    style={{
                      display: "flex",
                      gap: 6,
                      flexWrap: "wrap",
                      marginBottom: 16,
                    }}
                  >
                    {sectors.map((s) => {
                      const isActive = activeSector === s;
                      return (
                        <button
                          key={s}
                          onClick={() => onSectorToggle(isActive ? "" : s)}
                          style={{
                            fontSize: 12,
                            padding: "4px 11px",
                            borderRadius: 12,
                            cursor: "pointer",
                            border:
                              "1px solid " +
                              (isActive ? "#1a73e8" : "#dadce0"),
                            background: isActive ? "#1a73e8" : "#f8f9fa",
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

              {/* Score slider */}
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: "#80868b",
                  letterSpacing: 0.8,
                  marginBottom: 8,
                  textTransform: "uppercase",
                }}
              >
                Min Framework Score:{" "}
                <span style={{ color: "#1a73e8" }}>{minScore.toFixed(1)}</span>
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
                style={{
                  width: "100%",
                  accentColor: "#1a73e8",
                  cursor: "pointer",
                  marginBottom: 14,
                }}
              />

              {/* Footer actions */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  gap: 8,
                  borderTop: "1px solid #f1f3f4",
                  paddingTop: 12,
                  marginTop: 4,
                }}
              >
                <button
                  onClick={() => {
                    if (onClearAll) onClearAll();
                    else {
                      onSectorToggle("");
                      onMinScoreChange(0);
                      onQuickChange(null);
                      onRiskBucketChange("");
                    }
                  }}
                  style={{
                    fontSize: 13,
                    padding: "6px 14px",
                    borderRadius: 8,
                    cursor: "pointer",
                    border: "1px solid #e8eaed",
                    background: "#fff",
                    color: "#5f6368",
                    fontWeight: 500,
                  }}
                >
                  Clear All
                </button>
                <button
                  onClick={onToggleFilters}
                  style={{
                    fontSize: 13,
                    padding: "6px 18px",
                    borderRadius: 8,
                    cursor: "pointer",
                    border: "none",
                    background: "#1a73e8",
                    color: "#fff",
                    fontWeight: 600,
                  }}
                >
                  Apply
                </button>
              </div>
            </div>
          </div>
        </>,
        document.body
      )
    : null;

  return (
    <>
      {/* Slim quick-access bar — stays in the toolbar row */}
      <div
        style={{
          background: "#fff",
          flexShrink: 0,
          padding: "6px 24px",
          borderBottom: "1px solid #f1f3f4",
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexWrap: "nowrap",
          overflowX: "auto",
          msOverflowStyle: "none",
          scrollbarWidth: "none",
        }}
      >
        <style>{`div::-webkit-scrollbar { display: none; }`}</style>
        {/* Filter button (anchors the popup) */}
        <button
          ref={filterBtnRef}
          id="filter-popup-trigger"
          onClick={onToggleFilters}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: 12.5,
            padding: "5px 13px",
            borderRadius: 16,
            cursor: "pointer",
            border: "1px solid " + (showFilters || hasActiveFilters ? "#1a73e8" : "#e8eaed"),
            background: showFilters || hasActiveFilters ? "#e8f0fe" : "#fff",
            color: showFilters || hasActiveFilters ? "#1a73e8" : "#5f6368",
            fontWeight: 600,
            transition: "all 0.15s ease",
          }}
        >
          <SlidersHorizontal size={13} />
          Filters
          {hasActiveFilters && (
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: "#1a73e8",
                display: "inline-block",
              }}
            />
          )}
        </button>

        {/* Divider */}
        <span
          style={{ width: 1, height: 16, background: "#e8eaed", margin: "0 2px" }}
        />

        {/* Inline quick-filter pills */}
        <span
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            fontSize: 12,
            color: "#80868b",
            whiteSpace: "nowrap",
            flexShrink: 0,
          }}
        >
          <Sparkles size={12} /> Try:
        </span>
        {QUICK_FILTERS.map((qf) => (
          <button
            key={qf.id}
            onClick={() => applyQuickFilter(qf.id)}
            style={{
              fontSize: 12.5,
              padding: "5px 11px",
              borderRadius: 14,
              cursor: "pointer",
              border:
                "1px solid " +
                (activeQuick === qf.id ? "#1a73e8" : "#e8eaed"),
              background: activeQuick === qf.id ? "#e8f0fe" : "#fff",
              color: activeQuick === qf.id ? "#1a73e8" : "#3c4043",
              fontWeight: 500,
              whiteSpace: "nowrap",
              flexShrink: 0,
              transition: "all 0.15s ease",
            }}
          >
            {qf.icon} {qf.label}
          </button>
        ))}

        {/* Active filter badges */}
        {riskBucket !== "" && (
          <>
            <span style={{ width: 1, height: 16, background: "#e8eaed", margin: "0 2px" }} />
            <span
              style={{
                fontSize: 12,
                padding: "3px 10px",
                borderRadius: 12,
                background: "#e6f4ea",
                color: "#188038",
                border: "1px solid #ceead6",
                fontWeight: 600,
                display: "flex",
                alignItems: "center",
                gap: 5,
                whiteSpace: "nowrap",
                flexShrink: 0,
              }}
            >
              {RISK_BUCKETS.find((r) => r.id === riskBucket)?.label}
              <button
                onClick={() => onRiskBucketChange("")}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  padding: 0,
                  color: "#188038",
                  lineHeight: 1,
                  fontSize: 14,
                  fontWeight: 700,
                }}
              >
                ×
              </button>
            </span>
          </>
        )}
        {activeSector !== "" && (
          <span
            style={{
              fontSize: 12,
              padding: "3px 10px",
              borderRadius: 12,
              background: "#e8f0fe",
              color: "#1a73e8",
              border: "1px solid #d2e3fc",
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              gap: 5,
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            {activeSector}
            <button
              onClick={() => onSectorToggle("")}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: 0,
                color: "#1a73e8",
                lineHeight: 1,
                fontSize: 14,
                fontWeight: 700,
              }}
            >
              ×
            </button>
          </span>
        )}
        {minScore > 0 && (
          <span
            style={{
              fontSize: 12,
              padding: "3px 10px",
              borderRadius: 12,
              background: "#fce8e6",
              color: "#c5221f",
              border: "1px solid #f5c6c5",
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              gap: 5,
            }}
          >
            Score ≥ {minScore}
            <button
              onClick={() => onMinScoreChange(0)}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: 0,
                color: "#c5221f",
                lineHeight: 1,
                fontSize: 14,
                fontWeight: 700,
              }}
            >
              ×
            </button>
          </span>
        )}
      </div>

      {/* Popup portal */}
      {filterPopup}
    </>
  );
}
