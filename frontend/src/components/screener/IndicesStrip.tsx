"use client";
import React from "react";
import { IndexItem } from "@/types/stockglass";

interface IndicesStripProps {
  indices: IndexItem[];
  loading?: boolean;
  error?: string | null;
}

export function IndicesStrip({ indices, loading, error }: IndicesStripProps) {
  if (error) {
    return (
      <div style={{ display: "flex", gap: 10, padding: "8px 24px", borderBottom: "1px solid #e8eaed", overflowX: "auto", background: "#fff", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0, border: "1px solid #fce8e6", borderRadius: 6, padding: "5px 12px", background: "#fce8e6" }}>
          <div style={{ fontSize: 13, color: "#c5221f" }}>Indices not available</div>
        </div>
      </div>
    );
  }

  if (loading && (!indices || indices.length === 0)) {
    return (
      <div style={{ display: "flex", gap: 10, padding: "8px 24px", borderBottom: "1px solid #e8eaed", overflowX: "auto", background: "#fff", flexShrink: 0 }}>
        {[1, 2, 3].map((i) => (
          <div key={i} style={{ minWidth: 130, height: 40, border: "1px solid #e8eaed", borderRadius: 6, background: "#f8f9fa" }} />
        ))}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", gap: 8, padding: "8px 16px", borderBottom: "1px solid #e8eaed", overflowX: "auto", msOverflowStyle: "none", scrollbarWidth: "none", background: "#fff", flexShrink: 0 }}>
      {/* Hide webkit scrollbar via a quick style block */}
      <style>{`div::-webkit-scrollbar { display: none; }`}</style>
      {indices.map((idx, i) => {
        const isDown = typeof idx.chg === "number" ? idx.chg < 0 : false;
        const chgStr = typeof idx.chg === "number"
          ? `${idx.chg >= 0 ? "+" : ""}${idx.chg.toFixed(2)}`
          : String(idx.chg ?? "0");
        const pctStr = typeof idx.pct === "number"
          ? `${idx.pct >= 0 ? "+" : ""}${idx.pct.toFixed(2)}%`
          : String(idx.pct ?? "");
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, minWidth: "max-content", border: "1px solid #e8eaed", borderRadius: 6, padding: "4px 10px", background: "#fff" }}>
            <div style={{ fontSize: 11.5, color: "#5f6368", whiteSpace: "nowrap" }}>{idx.name}</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#202124" }}>{idx.value}</div>
            <div style={{ fontSize: 11.5, color: isDown ? "#c5221f" : "#188038", whiteSpace: "nowrap" }}>
              {chgStr} ({pctStr})
            </div>
          </div>
        );
      })}
    </div>
  );
}
