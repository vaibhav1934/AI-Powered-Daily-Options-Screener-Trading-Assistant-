"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { 
  TrendingUp, 
  TrendingDown, 
  ExternalLink, 
  ChevronUp, 
  ChevronDown, 
  Clock, 
  Sparkles, 
  Newspaper,
  X
} from "lucide-react";
import { NewsItem } from "@/types/stockglass";

interface NewsSwipeDigestProps {
  symbol: string;
  companyName?: string;
  news: NewsItem[];
  pctChange?: number;
  onClose?: () => void;
  isModal?: boolean;
}

function formatRelativeTime(dateStr: string): string {
  if (!dateStr) return "Recent";
  try {
    const pub = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - pub.getTime();
    if (isNaN(diffMs)) return "Recent";
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return "Just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHrs = Math.floor(diffMin / 60);
    if (diffHrs < 24) return `${diffHrs}h ago`;
    const diffDays = Math.floor(diffHrs / 24);
    return `${diffDays}d ago`;
  } catch {
    return "Recent";
  }
}

function deriveSentiment(headline: string, summary: string = "", pctChange: number = 0): {
  sentiment: "bullish" | "bearish" | "neutral";
  label: string;
} {
  const text = `${headline} ${summary}`.toLowerCase();
  const bullishKeywords = ["beat", "surge", "gain", "upgrade", "outperform", "rally", "growth", "record", "buy", "bull", "soar", "jump"];
  const bearishKeywords = ["miss", "drop", "downgrade", "underperform", "fall", "slump", "loss", "plunge", "decline", "cut", "bear", "caution", "risk"];

  let bullScore = bullishKeywords.filter((k) => text.includes(k)).length;
  let bearScore = bearishKeywords.filter((k) => text.includes(k)).length;

  if (pctChange >= 1.5) bullScore += 1;
  if (pctChange <= -1.5) bearScore += 1;

  if (bullScore > bearScore) {
    return { sentiment: "bullish", label: "Positive Catalyst" };
  } else if (bearScore > bullScore) {
    return { sentiment: "bearish", label: "Negative / Risk Tone" };
  }
  return { sentiment: "neutral", label: "Market Commentary" };
}

export function NewsSwipeDigest({
  symbol,
  companyName,
  news,
  pctChange = 0,
  onClose,
  isModal = false,
}: NewsSwipeDigestProps) {
  const [index, setIndex] = useState(0);
  const [dragOffset, setDragOffset] = useState(0);
  const startY = useRef<number | null>(null);
  const isDragging = useRef(false);

  const items = news && news.length > 0 ? news : [];

  const handleNext = useCallback(() => {
    if (index < items.length - 1) {
      setIndex((i) => i + 1);
    }
  }, [index, items.length]);

  const handlePrev = useCallback(() => {
    if (index > 0) {
      setIndex((i) => i - 1);
    }
  }, [index]);

  // Keyboard navigation (Arrow keys)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown" || e.key === "ArrowRight") {
        handleNext();
      } else if (e.key === "ArrowUp" || e.key === "ArrowLeft") {
        handlePrev();
      } else if (e.key === "Escape" && onClose) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleNext, handlePrev, onClose]);

  // Touch & Mouse Drag Handlers
  const handleTouchStart = (e: React.TouchEvent) => {
    startY.current = e.touches[0].clientY;
    isDragging.current = true;
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    if (!isDragging.current || startY.current === null) return;
    const diff = startY.current - e.touches[0].clientY;
    setDragOffset(diff);
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (!isDragging.current || startY.current === null) return;
    const diff = startY.current - e.changedTouches[0].clientY;
    if (diff > 45 && index < items.length - 1) {
      handleNext();
    } else if (diff < -45 && index > 0) {
      handlePrev();
    }
    isDragging.current = false;
    startY.current = null;
    setDragOffset(0);
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    startY.current = e.clientY;
    isDragging.current = true;
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging.current || startY.current === null) return;
    const diff = startY.current - e.clientY;
    setDragOffset(diff);
  };

  const handleMouseUp = (e: React.MouseEvent) => {
    if (!isDragging.current || startY.current === null) return;
    const diff = startY.current - e.clientY;
    if (diff > 45 && index < items.length - 1) {
      handleNext();
    } else if (diff < -45 && index > 0) {
      handlePrev();
    }
    isDragging.current = false;
    startY.current = null;
    setDragOffset(0);
  };

  if (items.length === 0) {
    return (
      <div
        style={{
          padding: 24,
          textAlign: "center",
          color: "#5f6368",
          background: "#f8f9fa",
          borderRadius: 14,
          border: "1px solid #e8eaed",
        }}
      >
        <Newspaper size={28} color="#9aa0a6" style={{ margin: "0 auto 8px" }} />
        <div style={{ fontSize: 13, fontWeight: 600, color: "#202124" }}>No Live News Dispatches</div>
        <div style={{ fontSize: 11, color: "#80868b", marginTop: 4 }}>
          No market catalyst articles currently available for {symbol}.
        </div>
      </div>
    );
  }

  const currentItem = items[index];
  const sentimentMeta = deriveSentiment(currentItem.headline, currentItem.summary || "", pctChange);
  const isBull = sentimentMeta.sentiment === "bullish";
  const isBear = sentimentMeta.sentiment === "bearish";

  // Clean and limit summary text to ~60 words
  const rawSummary = currentItem.summary || currentItem.headline;
  const words = rawSummary.trim().split(/\s+/);
  const cleanSummary = words.length > 60 ? words.slice(0, 60).join(" ") + "..." : rawSummary;

  return (
    <div
      style={{
        width: "100%",
        display: "flex",
        flexDirection: "column",
        height: isModal ? 520 : 380,
        background: "linear-gradient(180deg, #ffffff 0%, #fbfcff 100%)",
        borderRadius: 16,
        border: "1px solid #e8eaed",
        boxShadow: "0 4px 16px rgba(0,0,0,0.06)",
        overflow: "hidden",
        position: "relative",
      }}
    >
      {/* Top Header Bar */}
      <div
        style={{
          padding: "10px 16px",
          borderBottom: "1px solid #f1f3f4",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "#fff",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              background: "#e8f0fe",
              color: "#1a73e8",
              fontWeight: 700,
              fontSize: 11,
              padding: "2px 8px",
              borderRadius: 6,
            }}
          >
            {symbol}
          </div>
          <span style={{ fontSize: 12, fontWeight: 600, color: "#202124" }}>
            Catalyst Digest
          </span>
          <span style={{ fontSize: 11, color: "#80868b" }}>
            ({index + 1}/{items.length})
          </span>
        </div>

        {/* Progress Pill Bar */}
        <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
          {items.map((_, i) => (
            <button
              key={i}
              onClick={() => setIndex(i)}
              style={{
                height: 4,
                width: i === index ? 20 : 6,
                borderRadius: 999,
                background: i === index ? "#1a73e8" : "#dadce0",
                border: "none",
                padding: 0,
                cursor: "pointer",
                transition: "all 0.2s ease",
              }}
              title={`Jump to story ${i + 1}`}
            />
          ))}
          {onClose && (
            <button
              onClick={onClose}
              style={{
                background: "none",
                border: "none",
                color: "#5f6368",
                cursor: "pointer",
                padding: "2px 4px",
                marginLeft: 6,
              }}
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Swipeable Card Area */}
      <div
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        style={{
          flex: 1,
          padding: "16px 20px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          userSelect: "none",
          cursor: "grab",
          touchAction: "none",
          transform: `translateY(${-dragOffset * 0.15}px)`,
          transition: isDragging.current ? "none" : "transform 0.25s ease",
        }}
      >
        <div>
          {/* Sentiment Pill */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                fontSize: 11,
                fontWeight: 700,
                padding: "3px 8px",
                borderRadius: 999,
                background: isBull ? "#e6f4ea" : isBear ? "#fce8e6" : "#f1f3f4",
                color: isBull ? "#137333" : isBear ? "#c5221f" : "#5f6368",
                border: `1px solid ${isBull ? "#ceead6" : isBear ? "#fad2cf" : "#dadce0"}`,
              }}
            >
              {isBull ? <TrendingUp size={12} /> : isBear ? <TrendingDown size={12} /> : <Sparkles size={12} />}
              {sentimentMeta.label}
            </span>

            <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "#80868b" }}>
              <Clock size={12} />
              {formatRelativeTime(currentItem.publishedAt)}
            </span>
          </div>

          {/* Headline */}
          <h3
            style={{
              fontSize: isModal ? 19 : 15.5,
              fontWeight: 700,
              color: "#202124",
              lineHeight: 1.35,
              margin: "0 0 10px 0",
              fontFamily: "'Google Sans', Roboto, sans-serif",
            }}
          >
            {currentItem.headline}
          </h3>

          {/* Executive Summary Takeaway */}
          <p
            style={{
              fontSize: 13,
              color: "#3c4043",
              lineHeight: 1.5,
              margin: 0,
            }}
          >
            {cleanSummary}
          </p>
        </div>

        {/* Bottom Source & Navigation Strip */}
        <div style={{ marginTop: 14 }}>
          <a
            href={currentItem.url && currentItem.url !== "#" ? currentItem.url : undefined}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => {
              if (!currentItem.url || currentItem.url === "#") e.preventDefault();
            }}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              background: "#202124",
              color: "#fff",
              borderRadius: 12,
              padding: "8px 14px",
              textDecoration: "none",
              transition: "opacity 0.15s ease",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Newspaper size={14} color="#8ab4f8" />
              <span style={{ fontSize: 12, fontWeight: 600 }}>{currentItem.source || "Market Wire"}</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "#dadce0" }}>
              <span>Read Full Article</span>
              <ExternalLink size={12} color="#fff" />
            </div>
          </a>
        </div>
      </div>

      {/* Vertical Navigation Chevrons */}
      <div
        style={{
          borderTop: "1px solid #f1f3f4",
          padding: "6px 14px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "#fafafa",
        }}
      >
        <span style={{ fontSize: 10.5, color: "#80868b" }}>
          Swipe up / down or use arrow keys
        </span>

        <div style={{ display: "flex", gap: 4 }}>
          <button
            onClick={handlePrev}
            disabled={index === 0}
            style={{
              background: "#fff",
              border: "1px solid #dadce0",
              borderRadius: 6,
              padding: "3px 8px",
              cursor: index === 0 ? "not-allowed" : "pointer",
              opacity: index === 0 ? 0.35 : 1,
              display: "flex",
              alignItems: "center",
              color: "#3c4043",
            }}
            title="Previous Story (↑)"
          >
            <ChevronUp size={14} />
          </button>
          <button
            onClick={handleNext}
            disabled={index === items.length - 1}
            style={{
              background: "#fff",
              border: "1px solid #dadce0",
              borderRadius: 6,
              padding: "3px 8px",
              cursor: index === items.length - 1 ? "not-allowed" : "pointer",
              opacity: index === items.length - 1 ? 0.35 : 1,
              display: "flex",
              alignItems: "center",
              color: "#3c4043",
            }}
            title="Next Story (↓)"
          >
            <ChevronDown size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
