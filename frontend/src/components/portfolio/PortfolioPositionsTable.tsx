"use client";
import React, { useState } from "react";
import { PositionItem } from "@/types/stockglass";
import { closePaperPosition } from "@/lib/stockglass_api";
import { ArrowDownRight, ArrowUpRight, Loader2, XCircle } from "lucide-react";

interface PortfolioPositionsTableProps {
  positions: PositionItem[];
  loading: boolean;
  onRefresh?: () => Promise<void> | void;
}

export function PortfolioPositionsTable({ positions, loading, onRefresh }: PortfolioPositionsTableProps) {
  const [closingId, setClosingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleClose = async (positionId: string) => {
    setError(null);
    setClosingId(positionId);
    try {
      await closePaperPosition(positionId);
      await onRefresh?.();
    } catch (err: any) {
      setError(err?.message || "Failed to close position.");
    } finally {
      setClosingId(null);
    }
  };

  return (
    <div style={{ background: "#fff", border: "1px solid #e8eaed", borderRadius: 18, overflow: "hidden" }}>
      <div style={{ padding: "14px 16px", borderBottom: "1px solid #e8eaed", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#202124" }}>Open Paper Positions</div>
          <div style={{ fontSize: 12, color: "#5f6368", marginTop: 2 }}>Live paper book used by portfolio scoring and optimizer.</div>
        </div>
        <div style={{ fontSize: 12, fontWeight: 700, color: "#1a73e8" }}>{positions.length} open</div>
      </div>

      {error ? <div style={{ padding: "10px 16px", color: "#c5221f", fontSize: 12, borderBottom: "1px solid #f6d5d0" }}>{error}</div> : null}

      {loading ? (
        <div style={{ padding: 24, color: "#5f6368", fontSize: 13 }}>Loading positions...</div>
      ) : positions.length === 0 ? (
        <div style={{ padding: 24, color: "#5f6368", fontSize: 13 }}>No open paper positions yet. Add one from the portfolio workspace form above.</div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "#f8f9fa", borderBottom: "1px solid #e8eaed" }}>
                <th style={{ textAlign: "left", padding: "10px 16px", fontSize: 12, color: "#5f6368" }}>Symbol</th>
                <th style={{ textAlign: "right", padding: "10px 16px", fontSize: 12, color: "#5f6368" }}>Qty</th>
                <th style={{ textAlign: "right", padding: "10px 16px", fontSize: 12, color: "#5f6368" }}>Entry</th>
                <th style={{ textAlign: "right", padding: "10px 16px", fontSize: 12, color: "#5f6368" }}>Current</th>
                <th style={{ textAlign: "right", padding: "10px 16px", fontSize: 12, color: "#5f6368" }}>Unrealized P&L</th>
                <th style={{ textAlign: "right", padding: "10px 16px", fontSize: 12, color: "#5f6368" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((position) => {
                const pnl = position.unrealizedPnl ?? 0;
                const isUp = pnl >= 0;
                return (
                  <tr key={position.id} style={{ borderBottom: "1px solid #f1f3f4" }}>
                    <td style={{ padding: "12px 16px" }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: "#202124" }}>{position.symbol}</div>
                      <div style={{ fontSize: 11, color: "#5f6368" }}>{position.id}</div>
                    </td>
                    <td style={{ padding: "12px 16px", textAlign: "right", fontSize: 13, color: "#202124" }}>{position.qty}</td>
                    <td style={{ padding: "12px 16px", textAlign: "right", fontSize: 13, color: "#202124" }}>${position.entryPrice.toFixed(2)}</td>
                    <td style={{ padding: "12px 16px", textAlign: "right", fontSize: 13, color: "#202124" }}>${(position.currentPrice ?? position.entryPrice).toFixed(2)}</td>
                    <td style={{ padding: "12px 16px", textAlign: "right" }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color: isUp ? "#137333" : "#c5221f", fontSize: 12, fontWeight: 700 }}>
                        {isUp ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                        ${Math.abs(pnl).toFixed(2)}
                      </span>
                    </td>
                    <td style={{ padding: "12px 16px", textAlign: "right" }}>
                      <button
                        onClick={() => handleClose(position.id)}
                        disabled={closingId === position.id}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          border: "1px solid #fad2cf",
                          background: closingId === position.id ? "#f1f3f4" : "#fff",
                          color: closingId === position.id ? "#5f6368" : "#c5221f",
                          borderRadius: 10,
                          padding: "7px 10px",
                          fontSize: 12,
                          fontWeight: 700,
                          cursor: closingId === position.id ? "not-allowed" : "pointer",
                        }}
                      >
                        {closingId === position.id ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} />}
                        {closingId === position.id ? "Closing..." : "Close"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
