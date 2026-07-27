"use client";
import React from "react";
import { StockListItem } from "@/types/stockglass";
import { ScreenerRow } from "./ScreenerRow";

interface ScreenerTableProps {
  items: StockListItem[];
  loading?: boolean;
  selectedSymbol: string;
  onSelect: (sym: string) => void;
  watchlist: Set<string>;
  onToggleWatch: (sym: string) => void;
  sortKey?: string;
  sortDir?: "asc" | "desc";
  onSort?: (key: string) => void;
  activeTab?: "all" | "list1" | "list2";
  onTabChange?: (tab: "all" | "list1" | "list2") => void;
  totalCount?: number;
}

export function ScreenerTable({
  items,
  loading,
  selectedSymbol,
  onSelect,
  watchlist,
  onToggleWatch,
  onSort,
  activeTab = "all",
  onTabChange,
  totalCount,
}: ScreenerTableProps) {
  const displayTotal = totalCount || items.length;

  const tabs = [
    { id: "all", label: "All Stocks" },
    { id: "list1", label: "List 1 · Day Setups" },
    { id: "list2", label: "List 2 · Monthly Accumulation" },
  ] as const;

  if (loading && (!items || items.length === 0)) {
    return (
      <div style={{ flex: 1, padding: "20px 24px", minWidth: 0, background: "#fff" }}>
        <div style={{ display: "flex", gap: 4, marginBottom: 16 }}>
          {tabs.map((t) => (
            <div key={t.id} style={{ padding: "10px 16px", color: "#80868b", fontSize: 14, fontWeight: 500 }}>
              {t.label}
            </div>
          ))}
        </div>
        <div style={{ padding: 40, textAlign: "center", color: "#5f6368" }}>
          <div className="w-8 h-8 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p style={{ fontSize: 14 }}>Loading screener setups...</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, padding: "20px 24px", minWidth: 0, background: "#fff", overflowY: "auto" }}>
      <div style={{ display: "flex", gap: 4, marginBottom: 4 }}>
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => onTabChange && onTabChange(t.id)}
            style={{
              padding: "10px 16px",
              background: "none",
              border: "none",
              borderBottom: activeTab === t.id ? "2px solid #1a73e8" : "2px solid transparent",
              color: activeTab === t.id ? "#1a73e8" : "#5f6368",
              fontWeight: 500,
              fontSize: 14,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div style={{ fontSize: 12, color: "#5f6368", margin: "6px 0 4px" }}>
        {items.length} of {displayTotal} stocks match your filters
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 8 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #e8eaed" }}>
            <th style={{ width: 28 }}></th>
            <th
              onClick={() => onSort && onSort("symbol")}
              style={{ textAlign: "left", padding: "8px", fontSize: 12, color: "#5f6368", fontWeight: 500, cursor: "pointer" }}
            >
              Name
            </th>
            <th style={{ textAlign: "left", padding: "8px", fontSize: 12, color: "#5f6368", fontWeight: 500 }}>Sector</th>
            <th style={{ padding: "8px", fontSize: 12, color: "#5f6368", fontWeight: 500 }}>14d</th>
            <th
              onClick={() => onSort && onSort("price")}
              style={{ textAlign: "right", padding: "8px", fontSize: 12, color: "#5f6368", fontWeight: 500, cursor: "pointer" }}
            >
              Price
            </th>
            <th
              onClick={() => onSort && onSort("pct")}
              style={{ textAlign: "right", padding: "8px", fontSize: 12, color: "#5f6368", fontWeight: 500, cursor: "pointer" }}
            >
              Change
            </th>
            <th style={{ textAlign: "right", padding: "8px", fontSize: 12, color: "#5f6368", fontWeight: 500 }}>Volume</th>
            <th
              onClick={() => onSort && onSort("score")}
              style={{ textAlign: "right", padding: "8px", fontSize: 12, color: "#5f6368", fontWeight: 500, cursor: "pointer" }}
            >
              Score
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <ScreenerRow
              key={item.symbol}
              item={item}
              watched={watchlist.has(item.symbol)}
              onToggleWatch={onToggleWatch}
              onSelect={onSelect}
              selected={selectedSymbol === item.symbol}
            />
          ))}
          {items.length === 0 && (
            <tr>
              <td colSpan={8} style={{ padding: 24, textAlign: "center", color: "#5f6368", fontSize: 14 }}>
                No stocks match these filters. Try clearing a sector or lowering the score threshold.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <div style={{ marginTop: 16, fontSize: 12, color: "#80868b" }}>
        Click any row to see why it scored the way it did. Connected to live StockGlass AI v1 factor engine.
      </div>
    </div>
  );
}
