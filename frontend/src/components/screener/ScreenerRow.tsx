"use client";
import React from "react";
import { StockListItem } from "@/types/stockglass";
import { LineChart, Line, ResponsiveContainer } from "recharts";
import { Star, ChevronUp, ChevronDown } from "lucide-react";

export function scoreColor(s: number) {
  if (s >= 7) return { bg: "#e6f4ea", fg: "#188038", border: "#ceead6" };
  if (s >= 5) return { bg: "#fef7e0", fg: "#b06000", border: "#fce8b2" };
  return { bg: "#fce8e6", fg: "#c5221f", border: "#fad2cf" };
}

interface ScreenerRowProps {
  item: StockListItem;
  selected: boolean;
  onSelect: (symbol: string) => void;
  watched: boolean;
  onToggleWatch: (symbol: string) => void;
  isMobile?: boolean;
}

export function ScreenerRow({
  item,
  selected,
  onSelect,
  watched,
  onToggleWatch,
  isMobile,
}: ScreenerRowProps) {
  // Use real API fields: chg (dollar change), pct (percent), score (conviction)
  const up = item.chg >= 0;
  const sc = scoreColor(item.score);

  const sparkData = item.sparkline && item.sparkline.length > 0
    ? item.sparkline.map((v, i) => ({ i, v }))
    : [{ i: 0, v: item.price }, { i: 1, v: item.price }];

  if (isMobile) {
    return (
      <tr
        onClick={() => onSelect(item.symbol)}
        style={{
          borderBottom: "1px solid #e8eaed",
          cursor: "pointer",
          background: selected ? "#e8f0fe" : "transparent",
          transition: "background 0.15s ease",
        }}
      >
        <td colSpan={8} style={{ padding: "12px 16px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            {/* Left side: Star, Symbol, Name, Score */}
            <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleWatch(item.symbol);
                }}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  padding: "2px 0 0 0",
                  display: "flex",
                }}
              >
                <Star size={18} color={watched ? "#f9ab00" : "#dadce0"} fill={watched ? "#f9ab00" : "none"} />
              </button>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontWeight: 600, color: "#202124", fontSize: 15, letterSpacing: 0.3 }}>
                    {item.symbol}
                  </span>
                  <span
                    style={{
                      background: sc.bg,
                      color: sc.fg,
                      fontSize: 11,
                      fontWeight: 700,
                      padding: "2px 6px",
                      borderRadius: 6,
                      border: `1px solid ${sc.border}`,
                    }}
                  >
                    ★ {item.score.toFixed(1)}
                  </span>
                  {item.earningsSoon && (
                    <span style={{ fontSize: 10, background: "#fef7e0", color: "#b06000", borderRadius: 6, padding: "2px 6px" }}>
                      ⚡ Earn
                    </span>
                  )}
                </div>
                <span style={{ fontSize: 13, color: "#5f6368", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 160 }}>
                  {item.name}
                </span>
              </div>
            </div>

            {/* Right side: Price & Change */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
              <span style={{ fontSize: 15, color: "#202124", fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
                ${item.price > 0 ? item.price.toFixed(2) : "N/A"}
              </span>
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: up ? "#188038" : "#c5221f",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {up ? "+" : ""}{item.chg.toFixed(2)} ({item.pct > 0 ? "+" : ""}{item.pct.toFixed(2)}%)
              </span>
            </div>
          </div>
        </td>
      </tr>
    );
  }

  return (
    <tr
      onClick={() => onSelect(item.symbol)}
      style={{
        borderBottom: "1px solid #e8eaed",
        cursor: "pointer",
        background: selected ? "#e8f0fe" : "transparent",
        transition: "background 0.15s ease",
      }}
    >
      <td style={{ padding: "6px 8px", width: 28 }}>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleWatch(item.symbol);
          }}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            padding: 0,
            display: "flex",
            alignItems: "center",
          }}
          aria-label={watched ? `Remove ${item.symbol} from watchlist` : `Add ${item.symbol} to watchlist`}
        >
          <Star size={16} color={watched ? "#f9ab00" : "#dadce0"} fill={watched ? "#f9ab00" : "none"} />
        </button>
      </td>
      <td style={{ padding: "6px 8px" }}>
        <div style={{ fontWeight: 500, color: "#202124", fontSize: 14 }}>
          {item.symbol}
          {item.earningsSoon && (
            <span style={{ marginLeft: 4, fontSize: 10, background: "#fef7e0", color: "#b06000", borderRadius: 6, padding: "1px 5px", verticalAlign: "middle" }}>
              ⚡ Earnings
            </span>
          )}
        </div>
        <div style={{ fontSize: 12, color: "#5f6368" }}>{item.name}</div>
      </td>
      {!isMobile && (
        <td style={{ padding: "6px 8px" }}>
          <span style={{ fontSize: 11, color: "#5f6368", background: "#f1f3f4", borderRadius: 10, padding: "3px 8px", whiteSpace: "nowrap" }}>
            {item.sector}
          </span>
        </td>
      )}
      {!isMobile && (
        <td style={{ padding: "6px 8px", width: 90 }}>
          <ResponsiveContainer width="100%" height={32}>
            <LineChart data={sparkData}>
              <Line type="monotone" dataKey="v" stroke={up ? "#188038" : "#c5221f"} strokeWidth={1.75} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </td>
      )}
      <td style={{ padding: "6px 8px", textAlign: "right", fontSize: 14, color: "#202124", fontVariantNumeric: "tabular-nums", fontWeight: 500 }}>
        ${item.price > 0 ? item.price.toFixed(2) : "N/A"}
      </td>
      <td style={{ padding: "6px 8px", textAlign: "right", width: 130 }}>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 2,
            fontSize: 13,
            fontWeight: 500,
            color: up ? "#188038" : "#c5221f",
            background: up ? "#e6f4ea" : "#fce8e6",
            borderRadius: 4,
            padding: "3px 6px",
            fontVariantNumeric: "tabular-nums",
            whiteSpace: "nowrap",
          }}
        >
          {up ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          {Math.abs(item.chg).toFixed(2)} ({Math.abs(item.pct).toFixed(2)}%)
        </span>
      </td>
      {!isMobile && (
        <td style={{ padding: "6px 8px", textAlign: "right", fontSize: 13, color: "#5f6368", fontVariantNumeric: "tabular-nums" }}>
          {item.volume}
        </td>
      )}
      <td style={{ padding: "6px 8px", textAlign: "right", width: 70 }}>
        <span
          style={{
            background: sc.bg,
            color: sc.fg,
            fontSize: 12,
            fontWeight: 600,
            padding: "3px 8px",
            borderRadius: 12,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {item.score.toFixed(1)}
        </span>
      </td>
    </tr>
  );
}
