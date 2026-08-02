"use client";
import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search, Bell, Sparkles, BarChart2, Lock, LogOut, User as UserIcon, BriefcaseBusiness } from "lucide-react";
import { isAuthenticated, getStoredUser, logout, UserProfile } from "@/lib/auth";
import LoginModal from "@/components/auth/LoginModal";

interface NavbarProps {
  query?: string;
  onQueryChange?: (q: string) => void;
  rightPanelMode?: "detail" | "ai_chat";
  onRightPanelModeChange?: (mode: "detail" | "ai_chat") => void;
  isMobile?: boolean;
  showSearch?: boolean;
  showPanelToggle?: boolean;
}

export function Navbar({
  query = "",
  onQueryChange,
  rightPanelMode = "detail",
  onRightPanelModeChange,
  isMobile,
  showSearch = true,
  showPanelToggle = true,
}: NavbarProps) {
  const [authed, setAuthed] = useState(false);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const pathname = usePathname();

  const checkAuth = () => {
    const isAuth = isAuthenticated();
    setAuthed(isAuth);
    if (isAuth) {
      setUser(getStoredUser());
    } else {
      setUser(null);
    }
  };

  useEffect(() => {
    checkAuth();
    const handleAuthChange = () => checkAuth();
    window.addEventListener("stockglass_auth_changed", handleAuthChange);
    return () => {
      window.removeEventListener("stockglass_auth_changed", handleAuthChange);
    };
  }, []);

  const handleLogout = () => {
    logout();
  };

  return (
    <>
      <div className="navbar-shell" style={{ borderBottom: "1px solid #e8eaed", padding: isMobile ? "8px 16px" : "8px 24px", gap: isMobile ? 12 : 24, background: "#fff", flexShrink: 0 }}>
        <div style={{ fontSize: isMobile ? 18 : 22, fontWeight: 400, color: "#5f6368", letterSpacing: -0.5, display: "flex", alignItems: "center", gap: 4 }}>
          <span><span style={{ color: "#1a73e8", fontWeight: 500 }}>Stock</span>{isMobile ? "" : "Glass AI"}</span>
          <span style={{ fontSize: 10, background: "#e8f0fe", color: "#1a73e8", padding: "2px 6px", borderRadius: 10, fontWeight: 600, marginLeft: 6 }}>PRO</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: isMobile ? 0 : 220, flexWrap: "wrap" }}>
          <Link
            href="/"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 12px",
              borderRadius: 999,
              background: pathname === "/" ? "#e8f0fe" : "transparent",
              color: pathname === "/" ? "#1a73e8" : "#5f6368",
              fontSize: 13,
              fontWeight: 700,
              textDecoration: "none",
              border: pathname === "/" ? "1px solid #d2e3fc" : "1px solid transparent",
            }}
          >
            <BarChart2 size={14} /> Screener
          </Link>
          <Link
            href="/portfolio"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 12px",
              borderRadius: 999,
              background: pathname === "/portfolio" ? "#e8f0fe" : "transparent",
              color: pathname === "/portfolio" ? "#1a73e8" : "#5f6368",
              fontSize: 13,
              fontWeight: 700,
              textDecoration: "none",
              border: pathname === "/portfolio" ? "1px solid #d2e3fc" : "1px solid transparent",
            }}
          >
            <BriefcaseBusiness size={14} /> Portfolio
          </Link>
        </div>

        {showSearch ? (
          <div style={{ flex: 1, minWidth: isMobile ? "100%" : 240, maxWidth: 480, position: "relative" }}>
            <Search size={16} color="#5f6368" style={{ position: "absolute", left: 12, top: 8 }} />
            <input
              value={query}
              onChange={(e) => onQueryChange?.(e.target.value)}
              placeholder={isMobile ? "Search..." : "Search stocks in your lists..."}
              style={{
                width: "100%",
                padding: "6px 12px 6px 36px",
                borderRadius: 24,
                border: "1px solid #e8eaed",
                background: "#f1f3f4",
                fontSize: 14,
                outline: "none",
                boxSizing: "border-box",
                color: "#202124",
              }}
            />
          </div>
        ) : (
          <div style={{ flex: 1, minWidth: 24 }} />
        )}

        <div style={{ display: "flex", alignItems: "center", gap: isMobile ? 8 : 12, marginLeft: "auto", flexWrap: "wrap", justifyContent: "flex-end" }}>
          {!isMobile && showPanelToggle && onRightPanelModeChange && (
            <button
              onClick={() => onRightPanelModeChange(rightPanelMode === "detail" ? "ai_chat" : "detail")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                fontSize: 13,
                color: rightPanelMode === "ai_chat" ? "#fff" : "#1a73e8",
                background: rightPanelMode === "ai_chat" ? "#1a73e8" : "#e8f0fe",
                border: "1px solid " + (rightPanelMode === "ai_chat" ? "#1a73e8" : "#d2e3fc"),
                borderRadius: 20,
                padding: "6px 14px",
                cursor: "pointer",
                fontWeight: 500,
                transition: "all 0.15s ease",
              }}
            >
              {rightPanelMode === "detail" ? <Sparkles size={14} /> : <BarChart2 size={14} />}
              {rightPanelMode === "detail" ? "AI Assistant" : "Setup Detail"}
            </button>
          )}

          {authed ? (
            <div style={{ display: "flex", alignItems: "center", gap: 8, background: "#f8f9fa", padding: "4px 12px", borderRadius: 20, border: "1px solid #e8eaed" }}>
              <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: "#34a853" }} title="Authenticated Institutional Access" />
              {!isMobile && <span style={{ fontSize: 13, fontWeight: 600, color: "#202124" }}>{user?.username || "Trader"}</span>}
              <button
                onClick={handleLogout}
                title="Log out of institutional account"
                style={{ background: "none", border: "none", cursor: "pointer", padding: 2, display: "flex", alignItems: "center", color: "#5f6368" }}
              >
                <LogOut size={14} />
              </button>
            </div>
          ) : (
            <button
              onClick={() => setIsLoginModalOpen(true)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                fontSize: 13,
                color: "#fff",
                background: "linear-gradient(135deg, #1a73e8, #0d47a1)",
                border: "none",
                borderRadius: 20,
                padding: isMobile ? "6px 10px" : "6px 16px",
                cursor: "pointer",
                fontWeight: 600,
                boxShadow: "0 2px 6px rgba(26, 115, 232, 0.3)",
                transition: "all 0.15s ease",
              }}
            >
              <Lock size={13} /> {!isMobile && "Institutional Login"}
            </button>
          )}

          {!isMobile && <Bell size={18} color="#5f6368" style={{ cursor: "pointer", marginLeft: 4 }} />}


          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: "50%",
              background: authed ? "#0d652d" : "#5f6368",
              color: "#fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 13,
              fontWeight: 600,
              userSelect: "none",
            }}
            title={authed ? `Logged in as ${user?.username}` : "Not logged in"}
          >
            {authed && user?.username ? user.username.slice(0, 2).toUpperCase() : <UserIcon size={16} />}
          </div>
        </div>
      </div>

      <LoginModal
        isOpen={isLoginModalOpen}
        onClose={() => setIsLoginModalOpen(false)}
        onSuccess={() => {
          checkAuth();
        }}
      />
    </>
  );
}
