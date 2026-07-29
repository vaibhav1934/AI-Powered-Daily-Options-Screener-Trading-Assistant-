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
  totalCount: number;
  page: number;
  totalPages: number;
  onPageChange?: (page: number) => void;
  isMobile?: boolean;
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
  page,
  totalPages,
  onPageChange,
  isMobile,
}: ScreenerTableProps) {
  const displayTotal = totalCount > 0 ? totalCount : items.length;
  const startItem = displayTotal === 0 ? 0 : (page - 1) * 10 + 1;
  const endItem = Math.min(page * 10, displayTotal);

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
    <div style={{ flex: 1, padding: "12px 24px", minWidth: 0, minHeight: 0, height: "100%", background: "#fff", overflowY: "auto", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
      <div>
        <div style={{ display: "flex", gap: 4, marginBottom: 4 }}>
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => onTabChange && onTabChange(t.id)}
              style={{
                padding: "6px 14px",
                background: "none",
                border: "none",
                borderBottom: activeTab === t.id ? "2px solid #1a73e8" : "2px solid transparent",
                color: activeTab === t.id ? "#1a73e8" : "#5f6368",
                fontWeight: 500,
                fontSize: 13,
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "6px 0 4px" }}>
          <div style={{ fontSize: 12, color: "#5f6368" }}>
            Showing <span style={{ fontWeight: 600 }}>{startItem}</span> - <span style={{ fontWeight: 600 }}>{endItem}</span> of <span style={{ fontWeight: 600 }}>{displayTotal}</span> stocks
          </div>
          {isMobile && onSort && (
            <select
              onChange={(e) => onSort(e.target.value)}
              style={{
                fontSize: 12,
                padding: "4px 8px",
                borderRadius: 6,
                border: "1px solid #e8eaed",
                background: "#f8f9fa",
                color: "#202124",
                outline: "none",
              }}
            >
              <option value="score">Sort: Score</option>
              <option value="symbol">Sort: Name</option>
              <option value="price">Sort: Price</option>
              <option value="pct">Sort: Change %</option>
            </select>
          )}
        </div>

        <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 8 }}>
          {!isMobile && (
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
          )}
          <tbody>
            {items.map((item) => (
              <ScreenerRow
                key={item.symbol}
                item={item}
                watched={watchlist.has(item.symbol)}
                onToggleWatch={onToggleWatch}
                onSelect={onSelect}
                selected={selectedSymbol === item.symbol}
                isMobile={isMobile}
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
      </div>

      <div>
        {totalPages > 1 && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 20, padding: "12px 0 4px", borderTop: "1px solid #e8eaed" }}>
            <div style={{ fontSize: 13, color: "#5f6368" }}>
              Page <span style={{ fontWeight: 600, color: "#202124" }}>{page}</span> of <span style={{ fontWeight: 600, color: "#202124" }}>{totalPages}</span>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                onClick={() => onPageChange && onPageChange(page - 1)}
                disabled={page <= 1}
                style={{
                  padding: "6px 16px",
                  border: "1px solid #dadce0",
                  borderRadius: 6,
                  background: page <= 1 ? "#f1f3f4" : "#fff",
                  color: page <= 1 ? "#9aa0a6" : "#3c4043",
                  cursor: page <= 1 ? "not-allowed" : "pointer",
                  fontWeight: 500,
                  fontSize: 13,
                  transition: "all 0.15s ease",
                }}
              >
                Previous
              </button>
              <button
                onClick={() => onPageChange && onPageChange(page + 1)}
                disabled={page >= totalPages}
                style={{
                  padding: "6px 16px",
                  border: "1px solid #dadce0",
                  borderRadius: 6,
                  background: page >= totalPages ? "#f1f3f4" : "#fff",
                  color: page >= totalPages ? "#9aa0a6" : "#3c4043",
                  cursor: page >= totalPages ? "not-allowed" : "pointer",
                  fontWeight: 500,
                  fontSize: 13,
                  transition: "all 0.15s ease",
                }}
              >
                Next
              </button>
            </div>
          </div>
        )}

        <div style={{ marginTop: 12, fontSize: 12, color: "#80868b" }}>
          Click any row to see why it scored the way it did. Connected to live StockGlass AI v1 factor engine.
        </div>
      </div>
    </div>
  );
}
