"use client";
import React from "react";
import { IndexItem } from "@/types/stockglass";

interface IndicesStripProps {
  indices: IndexItem[];
  loading?: boolean;
}

export function IndicesStrip({ indices, loading }: IndicesStripProps) {
  if (loading && (!indices || indices.length === 0)) {
    return (
      <div style={{ display: "flex", gap: 16, padding: "16px 24px", borderBottom: "1px solid #e8eaed", overflowX: "auto", background: "#fff", flexShrink: 0 }}>
        {[1, 2, 3].map((i) => (
          <div key={i} style={{ minWidth: 160, height: 64, border: "1px solid #e8eaed", borderRadius: 8, padding: "10px 14px", background: "#f8f9fa" }} />
        ))}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", gap: 16, padding: "16px 24px", borderBottom: "1px solid #e8eaed", overflowX: "auto", background: "#fff", flexShrink: 0 }}>
      {indices.map((idx, i) => {
        const isDown = typeof idx.chg === "number" ? idx.chg < 0 : false;
        const chgStr = typeof idx.chg === "number"
          ? `${idx.chg >= 0 ? "+" : ""}${idx.chg.toFixed(2)}`
          : String(idx.chg ?? "0");
        const pctStr = typeof idx.pct === "number"
          ? `${idx.pct >= 0 ? "+" : ""}${idx.pct.toFixed(2)}%`
          : String(idx.pct ?? "");
        return (
          <div key={i} style={{ minWidth: 160, border: "1px solid #e8eaed", borderRadius: 8, padding: "10px 14px", background: "#fff" }}>
            <div style={{ fontSize: 12, color: "#5f6368" }}>{idx.name}</div>
            <div style={{ fontSize: 16, fontWeight: 500, color: "#202124", marginTop: 2 }}>{idx.value}</div>
            <div style={{ fontSize: 12, color: isDown ? "#c5221f" : "#188038", marginTop: 2 }}>
              {chgStr} ({pctStr})
            </div>
          </div>
        );
      })}
    </div>
  );
}
