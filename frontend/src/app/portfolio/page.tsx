"use client";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Navbar } from "@/components/layout/Navbar";
import { PortfolioOverview } from "@/components/screener/PortfolioOverview";
import { PortfolioPositionsTable } from "@/components/portfolio/PortfolioPositionsTable";
import { fetchPaperPositions, fetchPortfolioOptimization, fetchPortfolioScore } from "@/lib/stockglass_api";
import { isAuthenticated } from "@/lib/auth";
import AuthOverlay from "@/components/auth/AuthOverlay";
import { PortfolioOptimizationResponse, PortfolioScoreResponse, PositionItem } from "@/types/stockglass";
import { Activity, ArrowRightLeft, CircleAlert, ShieldCheck } from "lucide-react";

const PORTFOLIO_LIVE_POLL_MS = 15000;

export default function PortfolioPage() {
  const [portfolioScore, setPortfolioScore] = useState<PortfolioScoreResponse | null>(null);
  const [portfolioOptimization, setPortfolioOptimization] = useState<PortfolioOptimizationResponse | null>(null);
  const [positions, setPositions] = useState<PositionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [authed, setAuthed] = useState(false);
  const [isMobileLayout, setIsMobileLayout] = useState<boolean>(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return window.innerWidth <= 980;
  });
  const [optimizerExpanded, setOptimizerExpanded] = useState<boolean>(() => {
    if (typeof window === "undefined") {
      return true;
    }
    return window.innerWidth > 980;
  });

  const loadPortfolioWorkspace = useCallback(async () => {
    if (!isAuthenticated()) {
      setLoading(false);
      setError("Login required");
      setPortfolioScore(null);
      setPortfolioOptimization(null);
      setPositions([]);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const [scoreRes, optimizeRes, positionsRes] = await Promise.all([
        fetchPortfolioScore(),
        fetchPortfolioOptimization("weekly"),
        fetchPaperPositions("open"),
      ]);
      setPortfolioScore(scoreRes);
      setPortfolioOptimization(optimizeRes);
      setPositions(positionsRes.results || []);
    } catch (err: any) {
      const rawMessage = err?.message || "Portfolio workspace unavailable";
      const normalized = String(rawMessage).toLowerCase();
      if (normalized.includes("failed to fetch")) {
        setError("Unable to reach portfolio API. Verify NEXT_PUBLIC_API_URL and backend availability.");
      } else {
        setError(rawMessage);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const loadPortfolioLiveSlice = useCallback(async () => {
    if (!isAuthenticated()) {
      return;
    }

    try {
      const [scoreRes, positionsRes] = await Promise.all([
        fetchPortfolioScore(),
        fetchPaperPositions("open"),
      ]);
      setPortfolioScore(scoreRes);
      setPositions(positionsRes.results || []);
    } catch {
      // Keep current UI state stable during background refresh failures.
    }
  }, []);

  useEffect(() => {
    const checkAuth = () => {
      const loggedIn = isAuthenticated();
      setAuthed(loggedIn);
    };

    checkAuth();
    window.addEventListener("stockglass_auth_changed", checkAuth);
    return () => {
      window.removeEventListener("stockglass_auth_changed", checkAuth);
    };
  }, []);

  useEffect(() => {
    if (authed) {
      loadPortfolioWorkspace();
    } else {
      setLoading(false);
      setError("Login required");
      setPortfolioScore(null);
      setPortfolioOptimization(null);
      setPositions([]);
    }
  }, [authed, loadPortfolioWorkspace]);

  useEffect(() => {
    if (!authed) {
      return;
    }

    const tick = () => {
      if (document.visibilityState === "visible") {
        void loadPortfolioLiveSlice();
      }
    };

    const intervalId = window.setInterval(tick, PORTFOLIO_LIVE_POLL_MS);
    return () => {
      window.clearInterval(intervalId);
    };
  }, [authed, loadPortfolioLiveSlice]);

  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth <= 980;
      setIsMobileLayout(mobile);
      if (!mobile) {
        setOptimizerExpanded(true);
      }
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  const bookValue = useMemo(
    () => positions.reduce((sum, pos) => sum + (pos.currentPrice ?? pos.entryPrice) * pos.qty, 0),
    [positions]
  );
  const totalUnrealized = useMemo(
    () => positions.reduce((sum, pos) => sum + (pos.unrealizedPnl ?? 0), 0),
    [positions]
  );
  const topAction = portfolioOptimization?.actions?.[0] || null;

  return (
    <div
      style={{
        fontFamily: "'Google Sans', Roboto, Arial, sans-serif",
        background: "#fff",
        minHeight: "100vh",
        color: "#202124",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Navbar showSearch={false} showPanelToggle={false} />

      {!authed ? (
        <div className="portfolio-page-shell">
          <AuthOverlay
            featureName="Portfolio Workspace"
            description="Log in to view portfolio score, open positions, and optimizer actions."
          >
            <div style={{ minHeight: 540 }} />
          </AuthOverlay>
        </div>
      ) : (

      <div className="portfolio-page-shell">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 16, marginBottom: 18, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: isMobileLayout ? 23 : 28, fontWeight: 700, color: "#202124", letterSpacing: isMobileLayout ? -0.3 : -0.7 }}>Portfolio Workspace</div>
            <div style={{ fontSize: 13, color: "#5f6368", marginTop: 6, maxWidth: 720 }}>
              Book-level health, optimizer actions, and paper-trade management separated from the tactical stock screener.
            </div>
          </div>
          <button
            onClick={() => loadPortfolioWorkspace()}
            style={{
              border: "1px solid #d2e3fc",
              background: "#e8f0fe",
              color: "#1a73e8",
              borderRadius: 12,
              padding: "10px 14px",
              fontSize: 12,
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            Refresh Portfolio
          </button>
          <div style={{ fontSize: 11, color: "#5f6368" }}>
            Live refresh every {Math.round(PORTFOLIO_LIVE_POLL_MS / 1000)}s while this tab is active.
          </div>
        </div>

        <div className="portfolio-kpi-grid" style={{ marginBottom: 18 }}>
          <div style={{ background: "#f8fbff", border: "1px solid #dce8ff", borderRadius: 16, padding: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#1a73e8", marginBottom: 8 }}><ShieldCheck size={15} /><span style={{ fontSize: 12, fontWeight: 700 }}>Composite Score</span></div>
            {loading ? (
              <>
                <div className="skeleton-pulse skeleton-line-md" style={{ width: "40%", marginBottom: 8 }} />
                <div className="skeleton-pulse skeleton-line" style={{ width: "64%" }} />
              </>
            ) : (
              <>
                <div style={{ fontSize: 28, fontWeight: 700, color: "#202124" }}>{portfolioScore?.compositeScore != null ? portfolioScore.compositeScore.toFixed(1) : "N/A"}</div>
                <div style={{ fontSize: 12, color: "#5f6368", marginTop: 4 }}>{portfolioScore?.band?.replace(/_/g, " ") || "DATA NOT AVAILABLE"}</div>
              </>
            )}
          </div>
          <div style={{ background: "#fbfbfb", border: "1px solid #eceff1", borderRadius: 16, padding: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#5f6368", marginBottom: 8 }}><Activity size={15} /><span style={{ fontSize: 12, fontWeight: 700 }}>Open Positions</span></div>
            {loading ? (
              <>
                <div className="skeleton-pulse skeleton-line-md" style={{ width: "28%", marginBottom: 8 }} />
                <div className="skeleton-pulse skeleton-line" style={{ width: "70%" }} />
              </>
            ) : (
              <>
                <div style={{ fontSize: 28, fontWeight: 700, color: "#202124" }}>{positions.length}</div>
                <div style={{ fontSize: 12, color: "#5f6368", marginTop: 4 }}>Active paper trades in optimizer scope</div>
              </>
            )}
          </div>
          <div style={{ background: "#fbfbfb", border: "1px solid #eceff1", borderRadius: 16, padding: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#5f6368", marginBottom: 8 }}><ArrowRightLeft size={15} /><span style={{ fontSize: 12, fontWeight: 700 }}>Book Value</span></div>
            {loading ? (
              <>
                <div className="skeleton-pulse skeleton-line-md" style={{ width: "58%", marginBottom: 8 }} />
                <div className="skeleton-pulse skeleton-line" style={{ width: "54%" }} />
              </>
            ) : (
              <>
                <div style={{ fontSize: 28, fontWeight: 700, color: "#202124" }}>${bookValue.toFixed(2)}</div>
                <div style={{ fontSize: 12, color: totalUnrealized >= 0 ? "#137333" : "#c5221f", marginTop: 4 }}>Unrealized {totalUnrealized >= 0 ? "+" : "-"}${Math.abs(totalUnrealized).toFixed(2)}</div>
              </>
            )}
          </div>
          <div style={{ background: "#fbfbfb", border: "1px solid #eceff1", borderRadius: 16, padding: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#5f6368", marginBottom: 8 }}><CircleAlert size={15} /><span style={{ fontSize: 12, fontWeight: 700 }}>Top Action</span></div>
            {loading ? (
              <>
                <div className="skeleton-pulse skeleton-line-md" style={{ width: "62%", marginBottom: 8 }} />
                <div className="skeleton-pulse skeleton-line" style={{ width: "90%" }} />
              </>
            ) : (
              <>
                <div style={{ fontSize: 16, fontWeight: 700, color: "#202124" }}>{topAction ? `${topAction.action}${topAction.symbol ? ` • ${topAction.symbol}` : ""}` : "No Action"}</div>
                <div style={{ fontSize: 12, color: "#5f6368", marginTop: 4 }}>{topAction?.reason || "No optimizer triggers are active for the current paper book."}</div>
              </>
            )}
          </div>
        </div>

        <PortfolioOverview
          score={portfolioScore}
          optimization={portfolioOptimization}
          loading={loading}
          error={error}
        />

        <div className="portfolio-main-grid" style={{ marginTop: 20 }}>
          <PortfolioPositionsTable positions={positions} loading={loading} onRefresh={loadPortfolioWorkspace} />

          <div style={{ background: "#fff", border: "1px solid #e8eaed", borderRadius: 18, overflow: "hidden" }}>
            <div style={{ padding: "14px 16px", borderBottom: "1px solid #e8eaed", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "#202124" }}>Optimizer Queue</div>
                <div style={{ fontSize: 12, color: "#5f6368", marginTop: 2 }}>Ranked book-level advisories with deterministic triggers.</div>
              </div>
              {isMobileLayout ? (
                <button
                  type="button"
                  className="mobile-collapsible-button"
                  onClick={() => setOptimizerExpanded((prev) => !prev)}
                  aria-expanded={optimizerExpanded}
                  aria-controls="optimizer-queue-content"
                >
                  {optimizerExpanded ? "Hide" : "Show"}
                </button>
              ) : null}
            </div>
            {(!isMobileLayout || optimizerExpanded) ? (
              <div id="optimizer-queue-content">
                {loading ? (
                  <div style={{ display: "grid", gap: 10, padding: 14 }}>
                    <div className="skeleton-pulse skeleton-block" style={{ height: 86 }} />
                    <div className="skeleton-pulse skeleton-block" style={{ height: 86 }} />
                  </div>
                ) : (portfolioOptimization?.actions || []).length === 0 ? (
                  <div style={{ padding: 24, color: "#5f6368", fontSize: 13 }}>No optimizer actions fired for the current paper book.</div>
                ) : (
                  <div style={{ display: "grid", gap: 10, padding: 14 }}>
                    {(portfolioOptimization?.actions || []).map((action) => (
                      <div key={`${action.priority}-${action.trigger}-${action.symbol || "book"}`} style={{ border: "1px solid #e8eaed", borderRadius: 14, padding: 12, background: action.priority <= 20 ? "#fff8f6" : "#fff" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                          <div style={{ fontSize: 13, fontWeight: 700, color: "#202124" }}>{action.action}{action.symbol ? ` • ${action.symbol}` : ""}</div>
                          <div style={{ fontSize: 11, color: "#1a73e8", fontWeight: 700 }}>Priority {action.priority}</div>
                        </div>
                        <div style={{ fontSize: 12, color: "#3c4043", marginTop: 6, lineHeight: 1.45 }}>{action.reason}</div>
                        <div style={{ fontSize: 11, color: "#5f6368", marginTop: 8 }}>Trigger: {action.trigger}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div style={{ padding: "12px 16px", fontSize: 12, color: "#5f6368" }}>
                Optimizer queue is collapsed for mobile. Tap Show to expand.
              </div>
            )}
          </div>
        </div>
      </div>
      )}
    </div>
  );
}
