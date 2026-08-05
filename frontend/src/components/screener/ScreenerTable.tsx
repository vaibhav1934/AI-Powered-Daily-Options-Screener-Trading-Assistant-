"use client";
import React, { useEffect, useMemo, useState } from "react";
import { DualHorizonCandidate, StockListItem, ViewMode } from "@/types/stockglass";
import { ScreenerRow } from "./ScreenerRow";
import { Star } from "lucide-react";

interface ScreenerTableProps {
  items: StockListItem[];
  tacticalItems: DualHorizonCandidate[];
  longTermItems: DualHorizonCandidate[];
  loading?: boolean;
  loadingHorizon?: boolean;
  horizonError?: string | null;
  selectedSymbol: string;
  onSelect: (sym: string) => void;
  watchlist: Set<string>;
  onToggleWatch: (sym: string) => void;
  sortKey?: string;
  sortDir?: "asc" | "desc";
  onSort?: (key: string) => void;
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  totalCount: number;
  page: number;
  totalPages: number;
  onPageChange?: (page: number) => void;
  isMobile?: boolean;
  onAddPaperTrade?: (payload: { symbol: string; entryPrice: number; qty: number }) => Promise<void>;
}

export function ScreenerTable({
  items,
  tacticalItems,
  longTermItems,
  loading,
  loadingHorizon,
  horizonError,
  selectedSymbol,
  onSelect,
  watchlist,
  onToggleWatch,
  onSort,
  viewMode,
  onViewModeChange,
  totalCount,
  page,
  totalPages,
  onPageChange,
  isMobile,
  onAddPaperTrade,
}: ScreenerTableProps) {
  const PAGE_SIZE = 10;
  const [horizonPage, setHorizonPage] = useState(1);
  const [paperQty, setPaperQty] = useState("1");
  const [addingSymbol, setAddingSymbol] = useState<string | null>(null);
  const [paperMessage, setPaperMessage] = useState<string | null>(null);
  const [paperError, setPaperError] = useState<string | null>(null);

  useEffect(() => {
    setHorizonPage(1);
  }, [viewMode]);

  const tabs: Array<{ id: ViewMode; label: string }> = [
    { id: "TACTICAL_30D", label: "🔥 Top 20 Trending Stocks Today" },
    { id: "LONG_TERM", label: "🏛️ Long-Term Accumulation" },
    { id: "ALL_STOCKS", label: "All Universe" },
  ] as const;

  const horizonSource = viewMode === "TACTICAL_30D" ? tacticalItems : longTermItems;
  const sortedHorizon = useMemo(() => {
    const next = [...horizonSource];
    next.sort((a, b) => b.score - a.score);
    return next;
  }, [horizonSource]);

  const horizonTotalPages = Math.max(1, Math.ceil(sortedHorizon.length / PAGE_SIZE));
  const pagedHorizon = useMemo(() => {
    const start = (horizonPage - 1) * PAGE_SIZE;
    return sortedHorizon.slice(start, start + PAGE_SIZE);
  }, [sortedHorizon, horizonPage]);

  const isAllMode = viewMode === "ALL_STOCKS";
  const displayTotal = isAllMode ? (totalCount > 0 ? totalCount : items.length) : sortedHorizon.length;
  const currentPage = isAllMode ? page : horizonPage;
  const currentTotalPages = isAllMode ? totalPages : horizonTotalPages;
  const startItem = displayTotal === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const endItem = Math.min(currentPage * PAGE_SIZE, displayTotal);
  const parsedPaperQty = Number(paperQty);
  const canSubmitPaperQty = Number.isFinite(parsedPaperQty) && parsedPaperQty > 0;

  const showLoading = isAllMode
    ? Boolean(loading && (!items || items.length === 0))
    : Boolean(loadingHorizon && sortedHorizon.length === 0);

  const handleAddPaperTrade = async (payload: { symbol: string; entryPrice: number; qty: number }) => {
    if (!onAddPaperTrade) {
      return;
    }
    setPaperMessage(null);
    setPaperError(null);
    if (!canSubmitPaperQty) {
      setPaperError("Quantity must be a positive number.");
      return;
    }
    if (!(payload.entryPrice > 0)) {
      setPaperError(`Live price unavailable for ${payload.symbol}; cannot open paper position.`);
      return;
    }

    setAddingSymbol(payload.symbol);
    try {
      await onAddPaperTrade({
        symbol: payload.symbol,
        entryPrice: payload.entryPrice,
        qty: parsedPaperQty,
      });
      setPaperMessage(`Paper position opened: ${payload.symbol} x${parsedPaperQty} @ $${payload.entryPrice.toFixed(2)}`);
    } catch (err: any) {
      setPaperError(err?.message || `Failed to open paper position for ${payload.symbol}.`);
    } finally {
      setAddingSymbol(null);
    }
  };

  if (showLoading) {
    return (
      <div style={{ flex: 1, padding: "20px 24px", minWidth: 0, background: "#fff" }}>
        <div style={{ display: "flex", gap: 4, marginBottom: 16 }}>
          {tabs.map((t) => (
            <div
              key={t.id}
              style={{
                padding: "10px 16px",
                color: viewMode === t.id ? "#1a73e8" : "#80868b",
                borderBottom: viewMode === t.id ? "2px solid #1a73e8" : "2px solid transparent",
                fontSize: 14,
                fontWeight: 500,
              }}
            >
              {t.label}
            </div>
          ))}
        </div>
        <div style={{ padding: 40, textAlign: "center", color: "#5f6368" }}>
          <div className="w-8 h-8 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p style={{ fontSize: 14 }}>{isAllMode ? "Loading screener setups..." : "Loading horizon candidates..."}</p>
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
              onClick={() => onViewModeChange(t.id)}
              style={{
                padding: "6px 14px",
                background: "none",
                border: "none",
                borderBottom: viewMode === t.id ? "2px solid #1a73e8" : "2px solid transparent",
                color: viewMode === t.id ? "#1a73e8" : "#5f6368",
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
            Showing <span style={{ fontWeight: 600 }}>{startItem}</span> - <span style={{ fontWeight: 600 }}>{endItem}</span> of <span style={{ fontWeight: 600 }}>{displayTotal}</span>{" "}
            {isAllMode ? "stocks" : "candidates"}
          </div>
          {onAddPaperTrade && isAllMode ? (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 12, color: "#5f6368" }}>Paper Qty</span>
              <input
                value={paperQty}
                onChange={(e) => setPaperQty(e.target.value)}
                inputMode="decimal"
                placeholder="1"
                style={{
                  width: 66,
                  fontSize: 12,
                  padding: "4px 8px",
                  borderRadius: 6,
                  border: "1px solid #dadce0",
                  outline: "none",
                  boxSizing: "border-box",
                }}
              />
            </div>
          ) : null}
          {isMobile && onSort && isAllMode && (
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
          {!isMobile && isAllMode && (
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
                <th style={{ textAlign: "right", padding: "8px", fontSize: 12, color: "#5f6368", fontWeight: 500 }}>Paper</th>
              </tr>
            </thead>
          )}
          {!isMobile && !isAllMode && (
            <thead>
              {viewMode === "TACTICAL_30D" ? (
                <tr style={{ borderBottom: "1px solid #e8eaed" }}>
                  <th style={{ width: 28 }}></th>
                  <th style={{ textAlign: "left", padding: "8px", fontSize: 12, color: "#5f6368", fontWeight: 500 }}>Name</th>
                  <th style={{ textAlign: "left", padding: "8px", fontSize: 12, color: "#5f6368", fontWeight: 500 }}>Regime Gate</th>
                  <th style={{ textAlign: "left", padding: "8px", fontSize: 12, color: "#5f6368", fontWeight: 500 }}>Sizing Cap</th>
                  <th style={{ textAlign: "left", padding: "8px", fontSize: 12, color: "#5f6368", fontWeight: 500 }}>Sector</th>
                  <th style={{ textAlign: "right", padding: "8px", fontSize: 12, color: "#5f6368", fontWeight: 500 }}>Tactical Score</th>
                </tr>
              ) : (
                <tr style={{ borderBottom: "1px solid #e8eaed" }}>
                  <th style={{ width: 28 }}></th>
                  <th style={{ textAlign: "left", padding: "8px", fontSize: 12, color: "#5f6368", fontWeight: 500 }}>Name</th>
                  <th style={{ textAlign: "left", padding: "8px", fontSize: 12, color: "#5f6368", fontWeight: 500 }}>Sector</th>
                  <th style={{ textAlign: "right", padding: "8px", fontSize: 12, color: "#5f6368", fontWeight: 500 }}>Long-Term Score</th>
                </tr>
              )}
            </thead>
          )}
          <tbody>
            {isAllMode &&
              items.map((item) => (
                <ScreenerRow
                  key={item.symbol}
                  item={item}
                  watched={watchlist.has(item.symbol)}
                  onToggleWatch={onToggleWatch}
                  onSelect={onSelect}
                  selected={selectedSymbol === item.symbol}
                  paperQty={canSubmitPaperQty ? parsedPaperQty : 1}
                  adding={addingSymbol === item.symbol}
                  onAddPaperTrade={onAddPaperTrade ? handleAddPaperTrade : undefined}
                  isMobile={isMobile}
                />
              ))}

            {!isAllMode &&
              pagedHorizon.map((item) => (
                <tr
                  key={item.symbol}
                  onClick={() => onSelect(item.symbol)}
                  style={{
                    borderBottom: "1px solid #e8eaed",
                    cursor: "pointer",
                    background: selectedSymbol === item.symbol ? "#e8f0fe" : "transparent",
                    transition: "background 0.15s ease",
                  }}
                >
                  <td style={{ padding: "6px 8px", width: 28 }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onToggleWatch(item.symbol);
                      }}
                      style={{ background: "none", border: "none", cursor: "pointer", padding: 0, display: "flex", alignItems: "center" }}
                      aria-label={watchlist.has(item.symbol) ? `Remove ${item.symbol} from watchlist` : `Add ${item.symbol} to watchlist`}
                    >
                      <Star size={16} color={watchlist.has(item.symbol) ? "#f9ab00" : "#dadce0"} fill={watchlist.has(item.symbol) ? "#f9ab00" : "none"} />
                    </button>
                  </td>
                  <td style={{ padding: "6px 8px" }}>
                    <div style={{ fontWeight: 500, color: "#202124", fontSize: 14 }}>{item.symbol}</div>
                    <div style={{ fontSize: 12, color: "#5f6368" }}>{item.name}</div>
                  </td>

                  {viewMode === "TACTICAL_30D" ? (
                    <>
                      <td style={{ padding: "6px 8px" }}>
                        <span style={{ fontSize: 11, color: "#188038", background: "#e6f4ea", borderRadius: 10, padding: "3px 8px", whiteSpace: "nowrap" }}>
                          {item.regimeGate || "PASS"}
                        </span>
                      </td>
                      <td style={{ padding: "6px 8px", fontSize: 12, color: "#3c4043" }}>{item.sizingCap || "N/A"}</td>
                      <td style={{ padding: "6px 8px" }}>
                        <span style={{ fontSize: 11, color: "#5f6368", background: "#f1f3f4", borderRadius: 10, padding: "3px 8px", whiteSpace: "nowrap" }}>
                          {item.sector}
                        </span>
                      </td>
                      <td style={{ padding: "6px 8px", textAlign: "right" }}>
                        <span style={{ background: "#e8f0fe", color: "#1a73e8", fontSize: 12, fontWeight: 600, padding: "3px 8px", borderRadius: 12, fontVariantNumeric: "tabular-nums" }}>
                          {item.score.toFixed(1)}
                        </span>
                      </td>
                    </>
                  ) : (
                    <>
                      <td style={{ padding: "6px 8px" }}>
                        <span style={{ fontSize: 11, color: "#5f6368", background: "#f1f3f4", borderRadius: 10, padding: "3px 8px", whiteSpace: "nowrap" }}>
                          {item.sector}
                        </span>
                      </td>
                      <td style={{ padding: "6px 8px", textAlign: "right" }}>
                        <span style={{ background: "#e6f4ea", color: "#188038", fontSize: 12, fontWeight: 600, padding: "3px 8px", borderRadius: 12, fontVariantNumeric: "tabular-nums" }}>
                          {item.score.toFixed(1)}
                        </span>
                      </td>
                    </>
                  )}
                </tr>
              ))}

            {isAllMode && items.length === 0 && (
              <tr>
                <td colSpan={9} style={{ padding: 24, textAlign: "center", color: "#5f6368", fontSize: 14 }}>
                  No stocks match these filters. Try clearing a sector or lowering the score threshold.
                </td>
              </tr>
            )}

            {!isAllMode && pagedHorizon.length === 0 && (
              <tr>
                <td colSpan={7} style={{ padding: 24, textAlign: "center", color: "#5f6368", fontSize: 14 }}>
                  {horizonError || "No candidates in this horizon for the latest scan."}
                </td>
              </tr>
            )}
          </tbody>
        </table>

        {paperError ? (
          <div style={{ marginTop: 8, fontSize: 12, color: "#c5221f" }}>{paperError}</div>
        ) : null}
        {paperMessage ? (
          <div style={{ marginTop: 8, fontSize: 12, color: "#137333" }}>{paperMessage}</div>
        ) : null}
        {onAddPaperTrade && !isAllMode ? (
          <div style={{ marginTop: 8, fontSize: 12, color: "#5f6368" }}>
            Paper-trade add is enabled in All Universe rows where live entry price is available.
          </div>
        ) : null}
      </div>

      <div>
        {currentTotalPages > 0 && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 20, padding: "12px 0 4px", borderTop: "1px solid #e8eaed" }}>
            <div style={{ fontSize: 13, color: "#5f6368" }}>
              Page <span style={{ fontWeight: 600, color: "#202124" }}>{currentPage}</span> of <span style={{ fontWeight: 600, color: "#202124" }}>{currentTotalPages}</span>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                onClick={() => {
                  if (isAllMode) {
                    onPageChange && onPageChange(page - 1);
                  } else {
                    setHorizonPage((p) => Math.max(1, p - 1));
                  }
                }}
                disabled={currentPage <= 1}
                style={{
                  padding: "6px 16px",
                  border: "1px solid #dadce0",
                  borderRadius: 6,
                  background: currentPage <= 1 ? "#f1f3f4" : "#fff",
                  color: currentPage <= 1 ? "#9aa0a6" : "#3c4043",
                  cursor: currentPage <= 1 ? "not-allowed" : "pointer",
                  fontWeight: 500,
                  fontSize: 13,
                  transition: "all 0.15s ease",
                }}
              >
                Previous
              </button>
              <button
                onClick={() => {
                  if (isAllMode) {
                    onPageChange && onPageChange(page + 1);
                  } else {
                    setHorizonPage((p) => Math.min(horizonTotalPages, p + 1));
                  }
                }}
                disabled={currentPage >= currentTotalPages}
                style={{
                  padding: "6px 16px",
                  border: "1px solid #dadce0",
                  borderRadius: 6,
                  background: currentPage >= currentTotalPages ? "#f1f3f4" : "#fff",
                  color: currentPage >= currentTotalPages ? "#9aa0a6" : "#3c4043",
                  cursor: currentPage >= currentTotalPages ? "not-allowed" : "pointer",
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
          {isAllMode
            ? "Click any row to see why it scored the way it did. Connected to live StockGlass AI v1 factor engine."
            : "Click any candidate to open detail and AI analysis for that ticker."}
        </div>
      </div>
    </div>
  );
}
