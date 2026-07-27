"use client";
import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { IndexItem, StockListItem, StockDetail, ChatMessage } from "@/types/stockglass";
import { fetchIndices, fetchStocks, fetchStockDetail } from "@/lib/stockglass_api";
import { Navbar } from "@/components/layout/Navbar";
import { IndicesStrip } from "@/components/screener/IndicesStrip";
import { QuickFilters } from "@/components/screener/QuickFilters";
import { ScreenerTable } from "@/components/screener/ScreenerTable";
import { DetailPanel } from "@/components/screener/DetailPanel";
import { FactorModal } from "@/components/screener/FactorModal";
import { AIChatPanel } from "@/components/chat/AIChatPanel";
import AuthOverlay from "@/components/auth/AuthOverlay";

export default function StockGlassProDashboard() {
  // --- Data State ---
  const [indices, setIndices] = useState<IndexItem[]>([]);
  const [stocks, setStocks] = useState<StockListItem[]>([]);
  const [selectedDetail, setSelectedDetail] = useState<StockDetail | null>(null);

  // --- Loading & Error State ---
  const [loadingIndices, setLoadingIndices] = useState(true);
  const [loadingStocks, setLoadingStocks] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // --- UI Filter & Navigation State ---
  const [query, setQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<"all" | "list1" | "list2">("all");
  const [activeSector, setActiveSector] = useState("");
  const [riskBucket, setRiskBucket] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [activeQuick, setActiveQuick] = useState<string | null>(null);
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const selectedSymbolRef = useRef(selectedSymbol);
  useEffect(() => {
    selectedSymbolRef.current = selectedSymbol;
  }, [selectedSymbol]);
  const [watchlist, setWatchlist] = useState<Set<string>>(new Set(["NVDA", "PLTR"]));
  const [showFactors, setShowFactors] = useState(false);
  const [showFilters, setShowFilters] = useState(true);
  const [rightPanelMode, setRightPanelMode] = useState<"detail" | "ai_chat">("detail");
  const [sortKey, setSortKey] = useState("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // --- Pagination State ---
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalStocksCount, setTotalStocksCount] = useState(0);

  useEffect(() => {
    setCurrentPage(1);
  }, [activeFilter, activeSector, riskBucket, minScore, activeQuick, query]);

  // --- AI Chat State ---
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);

  // 1. Fetch Top Indices on Mount
  useEffect(() => {
    let isMounted = true;
    fetchIndices()
      .then((res) => {
        if (isMounted) {
          setIndices(res);
          setLoadingIndices(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          console.error("Indices load failed:", err);
          setLoadingIndices(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  // 2. Fetch Stock List from Backend (Reactive to filters and page)
  const loadStocks = useCallback(async () => {
    setLoadingStocks(true);
    setError(null);
    try {
      const params: any = { page: currentPage, pageSize: 10 };
      if (activeFilter !== "all") params.list = activeFilter;
      if (activeSector) params.sector = activeSector;
      if (riskBucket) params.riskBucket = riskBucket;
      if (minScore > 0) params.minScore = minScore;
      if (activeQuick === "gainers") params.direction = "gainers";
      if (activeQuick === "losers") params.direction = "losers";
      if (activeQuick === "earningsSoon") params.earningsSoon = true;
      if (activeQuick === "highConviction") params.minScore = 7;
      if (query) params.q = query;

      const res = await fetchStocks(params);
      const items = res.results || [];
      setStocks(items);
      setTotalPages(res.total_pages || 1);
      setTotalStocksCount(res.total || items.length);

      if (!selectedSymbolRef.current && items.length > 0) {
        setSelectedSymbol(items[0].symbol);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load screener stocks from API");
    } finally {
      setLoadingStocks(false);
    }
  }, [activeFilter, activeSector, riskBucket, minScore, activeQuick, query, currentPage]);

  useEffect(() => {
    loadStocks();
  }, [loadStocks]);

  // 3. Fetch Selected Stock Deep-Dive Detail
  useEffect(() => {
    if (!selectedSymbol) return;
    let isMounted = true;
    setLoadingDetail(true);
    fetchStockDetail(selectedSymbol)
      .then((res) => {
        if (isMounted) {
          setSelectedDetail(res);
          setLoadingDetail(false);
          if (res && res.symbol) {
            setStocks((prev) =>
              prev.map((s) =>
                s.symbol === res.symbol
                  ? {
                      ...s,
                      price: res.price || s.price,
                      chg: res.chg !== undefined ? res.chg : s.chg,
                      pct: res.pct !== undefined ? res.pct : s.pct,
                      sector: res.sector && res.sector !== "Unknown" && res.sector !== "US Equities" ? res.sector : s.sector,
                      name: res.name || s.name,
                    }
                  : s
              )
            );
          }
        }
      })
      .catch((err) => {
        if (isMounted) {
          console.error(`Detail load failed for ${selectedSymbol}:`, err);
          setLoadingDetail(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [selectedSymbol]);

  const sectors = useMemo(() => {
    const secSet = new Set<string>();
    stocks.forEach((s) => {
      if (s.sector) secSet.add(s.sector);
    });
    return Array.from(secSet).sort();
  }, [stocks]);

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const sortedStocks = useMemo(() => {
    const list = [...stocks];
    list.sort((a: any, b: any) => {
      const valA = a[sortKey] ?? 0;
      const valB = b[sortKey] ?? 0;
      if (valA < valB) return sortDir === "asc" ? -1 : 1;
      if (valA > valB) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return list;
  }, [stocks, sortKey, sortDir]);

  const toggleWatch = (sym: string) => {
    setWatchlist((prev) => {
      const next = new Set(prev);
      next.has(sym) ? next.delete(sym) : next.add(sym);
      return next;
    });
  };

  const handleAskAi = (prompt: string) => {
    setRightPanelMode("ai_chat");
    setChatMessages((prev) => [...prev, { role: "user", content: prompt }, { role: "assistant", content: "" }]);
  };

  const activeItem = useMemo(() => stocks.find((s) => s.symbol === selectedSymbol) || null, [stocks, selectedSymbol]);

  return (
    <div
      style={{
        fontFamily: "'Google Sans', Roboto, Arial, sans-serif",
        background: "#fff",
        height: "100vh",
        maxHeight: "100vh",
        overflow: "hidden",
        color: "#202124",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Top Navigation Bar */}
      <Navbar
        query={query}
        onQueryChange={setQuery}
        showFilters={showFilters}
        onToggleFilters={() => setShowFilters((s) => !s)}
        rightPanelMode={rightPanelMode}
        onRightPanelModeChange={setRightPanelMode}
      />

      {/* Market Proxy Strip */}
      <IndicesStrip indices={indices} loading={loadingIndices} />

      {/* Quick Filter Bar & Panel */}
      <QuickFilters
        showFilters={showFilters}
        activeSector={activeSector}
        onSectorToggle={setActiveSector}
        minScore={minScore}
        onMinScoreChange={setMinScore}
        activeQuick={activeQuick}
        onQuickChange={setActiveQuick}
        sectors={sectors}
        riskBucket={riskBucket}
        onRiskBucketChange={setRiskBucket}
        onClearAll={() => {
          setActiveSector("");
          setMinScore(0);
          setActiveQuick(null);
          setRiskBucket("");
          setQuery("");
        }}
      />

      {/* Main Split Content Area matching exact prototype layout */}
      <div style={{ display: "flex", maxWidth: 1400, margin: "0 auto", width: "100%", flex: 1, minHeight: 0, overflow: "hidden" }}>
        {error ? (
          <div style={{ flex: 1, padding: 40, textAlign: "center", color: "#c5221f" }}>
            <p style={{ fontWeight: 600, fontSize: 16 }}>⚠️ API Connection Issue</p>
            <p style={{ fontSize: 13, margin: "8px 0 16px" }}>{error}</p>
            <button
              onClick={loadStocks}
              style={{
                padding: "8px 16px",
                background: "#c5221f",
                color: "#fff",
                border: "none",
                borderRadius: 8,
                cursor: "pointer",
                fontWeight: 500,
              }}
            >
              Retry Connection
            </button>
          </div>
        ) : (
          <ScreenerTable
            items={sortedStocks}
            loading={loadingStocks}
            selectedSymbol={selectedSymbol}
            onSelect={setSelectedSymbol}
            watchlist={watchlist}
            onToggleWatch={toggleWatch}
            sortKey={sortKey}
            sortDir={sortDir}
            onSort={handleSort}
            activeTab={activeFilter}
            onTabChange={(tab) => setActiveFilter(tab)}
            totalCount={totalStocksCount}
            page={currentPage}
            totalPages={totalPages}
            onPageChange={(p) => setCurrentPage(p)}
          />
        )}

        <div style={{ width: 440, flexShrink: 0, height: "100%", overflow: "hidden" }}>
          <AuthOverlay
            featureName={rightPanelMode === "detail" ? "Setup Detail & Factor Breakdown" : "AI Trading Assistant & Chat"}
            description="Log in with your administrator or trader credentials to unlock deep-dive screener analytics, options chain execution, and interactive AI chat."
          >
            {rightPanelMode === "detail" ? (
              <DetailPanel
                symbol={selectedSymbol}
                detail={selectedDetail}
                loading={loadingDetail}
                onOpenFactors={() => setShowFactors(true)}
                onAskAi={handleAskAi}
              />
            ) : (
              <AIChatPanel
                symbol={selectedSymbol}
                item={activeItem}
                messages={chatMessages}
                onAddMessage={(msg) => setChatMessages((prev) => [...prev, msg])}
                onUpdateLastAssistantMessage={(content) => {
                  setChatMessages((prev) => {
                    const next = [...prev];
                    if (next.length > 0 && next[next.length - 1].role === "assistant") {
                      next[next.length - 1].content = content;
                    }
                    return next;
                  });
                }}
              />
            )}
          </AuthOverlay>
        </div>
      </div>

      {/* Full 50-Factor Log Modal */}
      {showFactors && (
        <FactorModal sym={selectedSymbol} onClose={() => setShowFactors(false)} />
      )}
    </div>
  );
}
