"use client";
import React, { useEffect, useState } from "react";
import { FactorBreakdownItem, FullFactorBreakdown } from "@/types/stockglass";
import { fetchStockFactors } from "@/lib/stockglass_api";
import { Info, X } from "lucide-react";

const statusColor: Record<string, string> = { pass: "#188038", neutral: "#b06000", fail: "#c5221f" };

interface FactorModalProps {
  sym: string;
  onClose: () => void;
}

export function FactorModal({ sym, onClose }: FactorModalProps) {
  const [data, setData] = useState<FullFactorBreakdown | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFactor, setSelectedFactor] = useState<FactorBreakdownItem | null>(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);
    setSelectedFactor(null);
    fetchStockFactors(sym)
      .then((res) => {
        if (isMounted) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || "Failed to load factor breakdown");
          setLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [sym]);

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.4)",
        zIndex: 50,
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        padding: "40px 16px",
        overflowY: "auto",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "#fff",
          borderRadius: 12,
          maxWidth: 640,
          width: "100%",
          padding: 24,
          boxShadow: "0 8px 28px rgba(0,0,0,0.28)",
          color: "#202124",
          fontFamily: "'Google Sans', Roboto, Arial, sans-serif",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
          <h2 style={{ fontSize: 18, fontWeight: 500, margin: 0 }}>{sym} — Full 50-factor breakdown</h2>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", padding: 4 }} aria-label="Close">
            <X size={20} color="#5f6368" />
          </button>
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: "center", color: "#5f6368" }}>
            <div className="w-8 h-8 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p style={{ fontSize: 14 }}>Computing 50-factor framework log...</p>
          </div>
        ) : error ? (
          <div style={{ padding: 20, color: "#c5221f", background: "#fce8e6", borderRadius: 8, margin: "16px 0" }}>
            {error}
          </div>
        ) : data ? (
          <>
            <div style={{ fontSize: 13, color: "#5f6368", marginBottom: 16 }}>
              {data.summary.pass} passed · {data.summary.fail} failed · {data.summary.neutral} neutral, across 10 scanning layers
            </div>
            {data.layers.map((layerGroup) => (
              <div key={layerGroup.layer} style={{ marginBottom: 14 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#202124", textTransform: "uppercase", letterSpacing: 0.3, marginBottom: 6 }}>
                  {layerGroup.layer} <span style={{ fontWeight: 400, color: "#80868b", fontSize: 11 }}>({layerGroup.range})</span>
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {layerGroup.factors.map((f) => {
                    const color = statusColor[f.status] || "#5f6368";
                    const hoverLines = [
                      `${f.code}: ${f.detail}`,
                      f.evaluationStatus ? `Runtime status: ${f.evaluationStatus}` : null,
                      typeof f.stubbed === "boolean" ? `Stubbed: ${f.stubbed ? "yes" : "no"}` : null,
                      f.reason ? `Reason: ${f.reason}` : null,
                      f.sourceTier ? `Source tier: ${f.sourceTier}` : null,
                    ].filter(Boolean);
                    return (
                      <div
                        key={f.code}
                        title={hoverLines.join("\n")}
                        style={{
                          fontSize: 12,
                          padding: "4px 8px",
                          borderRadius: 6,
                          background: `${color}14`,
                          color: color,
                          fontWeight: 500,
                          border: `1px solid ${color}33`,
                          cursor: "help",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                        }}
                      >
                        {f.code}
                        <button
                          type="button"
                          aria-label={`Show ${f.code} runtime details`}
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedFactor(f);
                          }}
                          style={{
                            width: 16,
                            height: 16,
                            borderRadius: 999,
                            border: `1px solid ${color}66`,
                            background: "transparent",
                            color,
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            padding: 0,
                            cursor: "pointer",
                          }}
                          title={`Show ${f.code} details`}
                        >
                          <Info size={10} />
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
            {selectedFactor ? (
              <div
                style={{
                  marginTop: 10,
                  border: "1px solid #e8eaed",
                  borderRadius: 10,
                  padding: 10,
                  background: "#f8f9fa",
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 700, color: "#202124", marginBottom: 4 }}>
                  {selectedFactor.code} Runtime Details
                </div>
                <div style={{ fontSize: 12, color: "#3c4043", lineHeight: 1.45 }}>
                  {selectedFactor.detail}
                </div>
                <div style={{ fontSize: 11, color: "#5f6368", marginTop: 8, lineHeight: 1.5 }}>
                  {selectedFactor.evaluationStatus ? `Runtime status: ${selectedFactor.evaluationStatus}` : "Runtime status: not provided"}
                  {typeof selectedFactor.stubbed === "boolean" ? ` | Stubbed: ${selectedFactor.stubbed ? "yes" : "no"}` : ""}
                  {selectedFactor.reason ? ` | Reason: ${selectedFactor.reason}` : ""}
                  {selectedFactor.sourceTier ? ` | Source tier: ${selectedFactor.sourceTier}` : ""}
                </div>
              </div>
            ) : null}
            <div style={{ fontSize: 12, color: "#80868b", marginTop: 12, borderTop: "1px solid #e8eaed", paddingTop: 12 }}>
              Hover any factor code for its live evaluation rule. Named rules (F40–F50) come from your codified error-correction log; F1–F39 are the standing technical/fundamental/macro layer checks.
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
