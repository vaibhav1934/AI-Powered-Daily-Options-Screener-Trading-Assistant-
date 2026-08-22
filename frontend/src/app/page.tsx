"use client";
import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { IndexItem, StockListItem, StockDetail, ChatMessage, DualHorizonResponse, PortfolioOptimizationResponse, PortfolioScoreResponse, ViewMode } from "@/types/stockglass";
import { Sparkles, X, BarChart2 } from "lucide-react";
import { createPaperPosition, fetchIndices, fetchStocks, fetchStockDetail, fetchDualHorizonLists, fetchPortfolioOptimization, fetchPortfolioScore, fetchStockFactorAudit } from "@/lib/stockglass_api";
import { DOWNLOAD_AUDIT_OUTPUT } from "@/lib/config";
import { Navbar } from "@/components/layout/Navbar";
import { IndicesStrip } from "@/components/screener/IndicesStrip";
import { PortfolioSummaryStrip } from "@/components/screener/PortfolioSummaryStrip";
import { QuickFilters } from "@/components/screener/QuickFilters";
import { ScreenerTable } from "@/components/screener/ScreenerTable";
import { DetailPanel } from "@/components/screener/DetailPanel";
import { FactorModal } from "@/components/screener/FactorModal";
import { AIChatPanel } from "@/components/chat/AIChatPanel";
import AuthOverlay from "@/components/auth/AuthOverlay";
import { isAuthenticated } from "@/lib/auth";

export default function StockGlassProDashboard() {
  const downloadAuditJson = useCallback((symbol: string, payload: unknown) => {
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const fileName = `${symbol}_factor_audit_${timestamp}.json`;
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }, []);

  // --- Data State ---
  const [indices, setIndices] = useState<IndexItem[]>([]);
  const [stocks, setStocks] = useState<StockListItem[]>([]);
  const [selectedDetail, setSelectedDetail] = useState<StockDetail | null>(null);
  const [dualHorizon, setDualHorizon] = useState<DualHorizonResponse | null>(null);
  const [portfolioScore, setPortfolioScore] = useState<PortfolioScoreResponse | null>(null);
  const [portfolioOptimization, setPortfolioOptimization] = useState<PortfolioOptimizationResponse | null>(null);

  // --- Loading & Error State ---
  const [loadingIndices, setLoadingIndices] = useState(true);
  const [loadingStocks, setLoadingStocks] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [loadingDualHorizon, setLoadingDualHorizon] = useState(true);
  const [loadingPortfolio, setLoadingPortfolio] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [indicesError, setIndicesError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [dualHorizonError, setDualHorizonError] = useState<string | null>(null);
  const [portfolioError, setPortfolioError] = useState<string | null>(null);

  // --- UI Filter & Navigation State ---
  const [query, setQuery] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("ALL_STOCKS");
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
  const [showFilters, setShowFilters] = useState(false);
  const [rightPanelMode, setRightPanelMode] = useState<"detail" | "ai_chat">("detail");
  const [sortKey, setSortKey] = useState("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // --- Pagination State ---
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalStocksCount, setTotalStocksCount] = useState(0);

  const pageCacheRef = useRef<Record<string, { items: StockListItem[]; totalPages: number; totalCount: number }>>({});
  const getCacheKey = useCallback(
    (page: number) => JSON.stringify({ viewMode, activeSector, riskBucket, minScore, activeQuick, query, page }),
    [viewMode, activeSector, riskBucket, minScore, activeQuick, query]
  );

  useEffect(() => {
    setCurrentPage(1);
  }, [viewMode, activeSector, riskBucket, minScore, activeQuick, query]);

  // --- AI Chat State ---
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);

  // --- Mobile State ---
  const [isMobile, setIsMobile] = useState(false);
  const [showMobilePanel, setShowMobilePanel] = useState(false);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 850);
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // 1. Fetch Top Indices on Mount
  useEffect(() => {
    let isMounted = true;
    setIndicesError(null);
    fetchIndices()
      .then((res) => {
        if (isMounted) {
          setIndices(res);
          setLoadingIndices(false);
        }
      })
      .catch((err: any) => {
        if (isMounted) {
          console.warn("Indices load failed");
          setIndicesError(err?.message || "Not available");
          setLoadingIndices(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  // 1B. Fetch Dual-Horizon Lists on Mount
  useEffect(() => {
    let isMounted = true;
    setDualHorizonError(null);
    setLoadingDualHorizon(true);
    fetchDualHorizonLists()
      .then((res) => {
        if (isMounted) {
          setDualHorizon(res);
          setLoadingDualHorizon(false);
        }
      })
      .catch((err: any) => {
        if (isMounted) {
          setDualHorizonError(err?.message || "Dual-horizon list unavailable");
          setLoadingDualHorizon(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // 1C. Fetch portfolio score + optimization on mount
  const loadPortfolio = useCallback(async () => {
    if (!isAuthenticated()) {
      setPortfolioScore(null);
      setPortfolioOptimization(null);
      setPortfolioError("Login required for portfolio analytics");
      setLoadingPortfolio(false);
      return;
    }
    setPortfolioError(null);
    setLoadingPortfolio(true);
    try {
      const [scoreRes, optRes] = await Promise.all([
        fetchPortfolioScore(),
        fetchPortfolioOptimization("weekly"),
      ]);
      setPortfolioScore(scoreRes);
      setPortfolioOptimization(optRes);
    } catch (err: any) {
      const rawMessage = err?.message || "Portfolio analytics unavailable";
      const normalized = String(rawMessage).toLowerCase();
      if (normalized.includes("failed to fetch")) {
        setPortfolioError("Unable to reach portfolio API. Verify NEXT_PUBLIC_API_URL and backend availability.");
      } else {
        setPortfolioError(rawMessage);
      }
    } finally {
      setLoadingPortfolio(false);
    }
  }, []);

  const handleAddPaperTradeFromScreener = useCallback(
    async (payload: { symbol: string; entryPrice: number; qty: number }) => {
      if (!isAuthenticated()) {
        throw new Error("Login required to open paper positions.");
      }
      await createPaperPosition(payload);
      await loadPortfolio();
    },
    [loadPortfolio]
  );

  useEffect(() => {
    loadPortfolio();
  }, [loadPortfolio]);

  // 2. Fetch Stock List from Backend (Reactive to filters and page)
  const loadStocks = useCallback(async () => {
    const cacheKey = getCacheKey(currentPage);
    if (pageCacheRef.current[cacheKey]) {
      setStocks(pageCacheRef.current[cacheKey].items);
      setTotalPages(pageCacheRef.current[cacheKey].totalPages);
      setTotalStocksCount(pageCacheRef.current[cacheKey].totalCount);
      setLoadingStocks(false);
      return;
    }

    setLoadingStocks(true);
    setError(null);
    try {
      const params: any = { page: currentPage, pageSize: 10 };
      if (activeSector) params.sector = activeSector;
      if (riskBucket) params.riskBucket = riskBucket;
      if (minScore > 0) params.minScore = minScore;
      if (viewMode === "EARNINGS_TODAY") params.earningsSoon = true;
      if (activeQuick === "gainers") params.direction = "gainers";
      if (activeQuick === "losers") params.direction = "losers";
      if (activeQuick === "earningsSoon") params.earningsSoon = true;
      if (activeQuick === "highConviction") params.minScore = 7;
      if (query) params.q = query;

      const res = await fetchStocks(params);
      const items = res.results || [];
      const tp = res.total_pages || 1;
      const tc = res.total || items.length;

      pageCacheRef.current[cacheKey] = { items, totalPages: tp, totalCount: tc };
      setStocks(items);
      setTotalPages(tp);
      setTotalStocksCount(tc);

      if (!selectedSymbolRef.current && items.length > 0) {
        setSelectedSymbol(items[0].symbol);
      }

      // Silent background prefetch for next page to ensure 0ms transition
      if (currentPage < tp) {
        const nextKey = getCacheKey(currentPage + 1);
        if (!pageCacheRef.current[nextKey]) {
          const nextParams = { ...params, page: currentPage + 1 };
          fetchStocks(nextParams)
            .then((nextRes) => {
              pageCacheRef.current[nextKey] = {
                items: nextRes.results || [],
                totalPages: nextRes.total_pages || tp,
                totalCount: nextRes.total || tc,
              };
            })
            .catch(() => {});
        }
      }
    } catch (err: any) {
      setError(err.message || "Failed to load screener stocks from API");
    } finally {
      setLoadingStocks(false);
    }
  }, [viewMode, activeSector, riskBucket, minScore, activeQuick, query, currentPage, getCacheKey]);

  useEffect(() => {
    loadStocks();
  }, [loadStocks]);

  useEffect(() => {
    if (viewMode === "TACTICAL_30D") {
      const first = dualHorizon?.tactical?.[0]?.symbol;
      if (first) {
        setSelectedSymbol(first);
      }
      return;
    }

    if (viewMode === "LONG_TERM") {
      const first = dualHorizon?.longTerm?.[0]?.symbol;
      if (first) {
        setSelectedSymbol(first);
      }
      return;
    }

    if (viewMode === "ALL_STOCKS" && stocks.length > 0 && !selectedSymbolRef.current) {
      setSelectedSymbol(stocks[0].symbol);
    }
  }, [viewMode, dualHorizon, stocks]);

  // 3. Fetch Selected Stock Deep-Dive Detail
  useEffect(() => {
    if (!selectedSymbol) return;
    let isMounted = true;
    setLoadingDetail(true);
    setDetailError(null);
    fetchStockDetail(selectedSymbol)
      .then((res) => {
        if (isMounted) {
          setSelectedDetail(res);
          setLoadingDetail(false);
          if (DOWNLOAD_AUDIT_OUTPUT) {
            void fetchStockFactorAudit(selectedSymbol)
              .then((auditPayload) => {
                if (!isMounted) return;
                downloadAuditJson(selectedSymbol, auditPayload);
              })
              .catch((auditErr: any) => {
                const auditMsg = auditErr?.message || "Failed to generate factor audit JSON";
                console.warn(`Factor audit generation failed for ${selectedSymbol}: ${auditMsg}`);
              });
          }
          if (res && res.symbol) {
            setStocks((prev) =>
              prev.map((s) =>
                s.symbol === res.symbol
                  ? {
                      ...s,
                      price: res.price || s.price,
                      chg: res.chg !== undefined ? res.chg : s.chg,
                      pct: res.pct !== undefined ? res.pct : s.pct,
                      volume: res.volume || s.volume,
                      score: res.score !== undefined ? res.score : s.score,
                      sector: res.sector && res.sector !== "Unknown" && res.sector !== "US Equities" ? res.sector : s.sector,
                      name: res.name || s.name,
                    }
                  : s
              )
            );
          }
        }
      })
      .catch((err: any) => {
        if (isMounted) {
          const msg = err?.message || "Detail not available";
          console.warn(`Detail load failed for ${selectedSymbol}: ${msg}`);
          setDetailError(msg);
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
    if (isMobile) {
      setShowMobilePanel(true);
    }
  };

  const handleSelectSymbol = (sym: string) => {
    setSelectedSymbol(sym);
    if (isMobile) {
      setShowMobilePanel(true);
    }
  };

  const activeItem = useMemo(() => stocks.find((s) => s.symbol === selectedSymbol) || null, [stocks, selectedSymbol]);

  const renderRightPanel = () => (
    <AuthOverlay
      featureName={rightPanelMode === "detail" ? "Setup Detail & Factor Breakdown" : "AI Trading Assistant & Chat"}
      description="Log in with your administrator or trader credentials to unlock deep-dive screener analytics, options chain execution, and interactive AI chat."
    >
      {rightPanelMode === "detail" ? (
        <DetailPanel
          symbol={selectedSymbol}
          detail={selectedDetail}
          loading={loadingDetail}
          error={detailError}
          onOpenFactors={() => setShowFactors(true)}
          onAskAi={handleAskAi}
          onAddPaperTrade={handleAddPaperTradeFromScreener}
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
  );

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
        rightPanelMode={rightPanelMode}
        onRightPanelModeChange={setRightPanelMode}
        isMobile={isMobile}
      />

      {/* Market Proxy Strip */}
      <IndicesStrip indices={indices} loading={loadingIndices} error={indicesError} />

      <PortfolioSummaryStrip
        score={portfolioScore}
        optimization={portfolioOptimization}
        loading={loadingPortfolio}
        error={portfolioError}
      />

      {/* Quick Filter Bar & Panel */}
      {viewMode === "ALL_STOCKS" ? (
        <QuickFilters
          showFilters={showFilters}
          onToggleFilters={() => setShowFilters((s) => !s)}
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
      ) : (
        <div style={{ maxWidth: 1400, margin: "6px auto 0", width: "100%", padding: "0 24px", color: "#5f6368", fontSize: 12 }}>
          Showing horizon-specific candidates from the latest scan snapshot.
        </div>
      )}

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
            tacticalItems={dualHorizon?.tactical ?? []}
            longTermItems={dualHorizon?.longTerm ?? []}
            loading={loadingStocks}
            loadingHorizon={loadingDualHorizon}
            horizonError={dualHorizonError}
            selectedSymbol={selectedSymbol}
            onSelect={handleSelectSymbol}
            watchlist={watchlist}
            onToggleWatch={toggleWatch}
            sortKey={sortKey}
            sortDir={sortDir}
            onSort={handleSort}
            viewMode={viewMode}
            onViewModeChange={setViewMode}
            totalCount={totalStocksCount}
            page={currentPage}
            totalPages={totalPages}
            onPageChange={(p) => setCurrentPage(p)}
            isMobile={isMobile}
            onAddPaperTrade={handleAddPaperTradeFromScreener}
          />
        )}

        {!isMobile && (
          <div style={{ width: rightPanelMode === "detail" ? 380 : 440, flexShrink: 0, height: "100%", overflow: "hidden", display: "flex", flexDirection: "column", transition: "width 0.2s ease" }}>
            {renderRightPanel()}
          </div>
        )}
      </div>

      {/* Mobile Bottom Sheet / Modal */}
      {isMobile && showMobilePanel && (
        <div style={{ position: "fixed", inset: 0, zIndex: 1000, display: "flex", flexDirection: "column", justifyContent: "flex-end" }}>
          {/* Backdrop */}
          <div 
            style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.4)" }} 
            onClick={() => setShowMobilePanel(false)}
          />
          {/* Panel */}
          <div style={{ 
            position: "relative", 
            background: "#fff", 
            width: "100%", 
            height: "85vh", 
            borderTopLeftRadius: 20, 
            borderTopRightRadius: 20, 
            display: "flex", 
            flexDirection: "column",
            overflow: "hidden",
            boxShadow: "0 -4px 16px rgba(0,0,0,0.1)",
            animation: "slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1)"
          }}>
            <style>{`
              @keyframes slideUp {
                from { transform: translateY(100%); }
                to { transform: translateY(0); }
              }
            `}</style>
            
            {/* Header / Handle */}
            <div style={{ padding: "12px 16px", borderBottom: "1px solid #e8eaed", display: "flex", alignItems: "center", justifyContent: "space-between", background: "#f8f9fa" }}>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={() => setRightPanelMode("detail")}
                  style={{
                    padding: "6px 12px",
                    borderRadius: 16,
                    border: "none",
                    background: rightPanelMode === "detail" ? "#e8f0fe" : "transparent",
                    color: rightPanelMode === "detail" ? "#1a73e8" : "#5f6368",
                    fontSize: 13,
                    fontWeight: 600,
                    display: "flex",
                    alignItems: "center",
                    gap: 6
                  }}
                >
                  <BarChart2 size={14} /> Setup
                </button>
                <button
                  onClick={() => setRightPanelMode("ai_chat")}
                  style={{
                    padding: "6px 12px",
                    borderRadius: 16,
                    border: "none",
                    background: rightPanelMode === "ai_chat" ? "#1a73e8" : "transparent",
                    color: rightPanelMode === "ai_chat" ? "#fff" : "#5f6368",
                    fontSize: 13,
                    fontWeight: 600,
                    display: "flex",
                    alignItems: "center",
                    gap: 6
                  }}
                >
                  <Sparkles size={14} /> AI
                </button>
              </div>
              <button 
                onClick={() => setShowMobilePanel(false)}
                style={{ background: "none", border: "none", padding: 8, color: "#5f6368" }}
              >
                <X size={20} />
              </button>
            </div>
            
            {/* Content Container */}
            <div style={{ flex: 1, minHeight: 0, position: "relative" }}>
              {renderRightPanel()}
            </div>
          </div>
        </div>
      )}

      {/* Persistent Compliance & Publisher Exemption Footer Banner */}
      <footer style={{ borderTop: "1px solid #e8eaed", background: "#f8f9fa", padding: "6px 20px", fontSize: 11, color: "#5f6368", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
        <span>
          <strong>Disclaimer:</strong> For educational, market research, and informational purposes only. Not investment, tax, or legal advice. No personalized recommendations.
        </span>
        <span style={{ fontSize: 10, color: "#80868b" }}>
          Live Market Feeds: Polygon.io • SEC EDGAR • Finnhub
        </span>
      </footer>

      {/* Full 50-Factor Log Modal */}
      {showFactors && (
        <FactorModal sym={selectedSymbol} onClose={() => setShowFactors(false)} />
      )}
    </div>
  );
}
