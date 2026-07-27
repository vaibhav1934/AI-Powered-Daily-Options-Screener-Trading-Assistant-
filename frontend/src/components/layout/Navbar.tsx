"use client";
import React from "react";
import { Search, Bell, SlidersHorizontal, Sparkles, MessageSquare, BarChart2 } from "lucide-react";

interface NavbarProps {
  query: string;
  onQueryChange: (q: string) => void;
  showFilters: boolean;
  onToggleFilters: () => void;
  rightPanelMode: "detail" | "ai_chat";
  onRightPanelModeChange: (mode: "detail" | "ai_chat") => void;
}

export function Navbar({
  query,
  onQueryChange,
  showFilters,
  onToggleFilters,
  rightPanelMode,
  onRightPanelModeChange,
}: NavbarProps) {
  return (
    <div style={{ borderBottom: "1px solid #e8eaed", padding: "12px 24px", display: "flex", alignItems: "center", gap: 24, background: "#fff", flexShrink: 0 }}>
      <div style={{ fontSize: 22, fontWeight: 400, color: "#5f6368", letterSpacing: -0.5, display: "flex", alignItems: "center", gap: 4 }}>
        <span><span style={{ color: "#1a73e8", fontWeight: 500 }}>Stock</span>Glass AI</span>
        <span style={{ fontSize: 11, background: "#e8f0fe", color: "#1a73e8", padding: "2px 6px", borderRadius: 10, fontWeight: 600, marginLeft: 6 }}>PRO</span>
      </div>

      <div style={{ flex: 1, maxWidth: 480, position: "relative" }}>
        <Search size={16} color="#5f6368" style={{ position: "absolute", left: 12, top: 10 }} />
        <input
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Search stocks in your lists..."
          style={{
            width: "100%",
            padding: "8px 12px 8px 36px",
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

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginLeft: "auto" }}>
        <button
          onClick={onToggleFilters}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: 13,
            color: showFilters ? "#1a73e8" : "#5f6368",
            background: showFilters ? "#e8f0fe" : "none",
            border: "1px solid " + (showFilters ? "#d2e3fc" : "#e8eaed"),
            borderRadius: 20,
            padding: "6px 14px",
            cursor: "pointer",
            fontWeight: 500,
            transition: "all 0.15s ease",
          }}
        >
          <SlidersHorizontal size={14} /> Filters
        </button>

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

        <Bell size={18} color="#5f6368" style={{ cursor: "pointer" }} />

        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: "50%",
            background: "#1a73e8",
            color: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 13,
            fontWeight: 600,
            userSelect: "none",
          }}
        >
          AT
        </div>
      </div>
    </div>
  );
}
