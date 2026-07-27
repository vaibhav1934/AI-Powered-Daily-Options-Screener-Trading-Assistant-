"use client";
import React from "react";
import { StockDetail } from "@/types/stockglass";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { scoreColor } from "./ScreenerRow";
import { ExternalLink, Info, Newspaper, Sparkles } from "lucide-react";

const reasonColor: Record<string, string> = { bull: "#188038", bear: "#c5221f", neutral: "#5f6368" };

interface DetailPanelProps {
  symbol: string;
  detail: StockDetail | null;
  loading: boolean;
  onOpenFactors: () => void;
  onAskAi?: (prompt: string) => void;
}

export function DetailPanel({
  symbol,
  detail,
  loading,
  onOpenFactors,
  onAskAi,
}: DetailPanelProps) {
  if (!symbol) {
    return (
      <div style={{ borderLeft: "1px solid #e8eaed", padding: 40, width: 340, flexShrink: 0, background: "#fff", textAlign: "center", color: "#5f6368" }}>
        <p style={{ fontSize: 16, fontWeight: 500, color: "#202124" }}>Select a Setup</p>
        <p style={{ fontSize: 13, marginTop: 4 }}>Click any row on the left to see why it scored the way it did.</p>
      </div>
    );
  }

  if (loading || !detail) {
    return (
      <div style={{ borderLeft: "1px solid #e8eaed", padding: 20, width: 340, flexShrink: 0, background: "#fff" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <div className="h-6 w-24 bg-slate-100 rounded animate-pulse" />
          <div className="h-6 w-12 bg-slate-100 rounded animate-pulse" />
        </div>
        <div className="h-8 w-32 bg-slate-100 rounded animate-pulse mt-4" />
        <div className="h-20 w-full bg-slate-100 rounded animate-pulse mt-6" />
        <div className="h-32 w-full bg-slate-100 rounded animate-pulse mt-6" />
      </div>
    );
  }

  const sc = scoreColor(detail.score);
  const isPos = detail.chg >= 0;
  const support = detail.levels?.support ?? 0;
  const resistance = detail.levels?.resistance ?? 0;

  const layerData = detail.layerScores && detail.layerScores.length > 0
    ? detail.layerScores.map((l) => ({
        layer: l.layer ? String(l.layer).split("/")[0].split(" ")[0] : "?",
        val: l.value ?? 0,
      }))
    : [];

  return (
    <div style={{ borderLeft: "1px solid #e8eaed", padding: 20, width: 340, flexShrink: 0, background: "#fff", overflowY: "auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 500, color: "#202124" }}>{detail.symbol}</div>
          <div style={{ fontSize: 13, color: "#5f6368" }}>{detail.name}</div>
        </div>
        <span style={{ background: sc.bg, color: sc.fg, fontSize: 13, fontWeight: 700, padding: "4px 10px", borderRadius: 14 }}>
          {detail.score.toFixed(1)}
        </span>
      </div>

      <div style={{ fontSize: 26, fontWeight: 500, marginTop: 10, color: "#202124" }}>
        ${detail.price.toFixed(2)}
      </div>

      <div style={{ fontSize: 13, color: isPos ? "#188038" : "#c5221f", marginBottom: 12 }}>
        {isPos ? "+" : ""}{detail.chg.toFixed(2)} ({detail.pct.toFixed(2)}%)
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#5f6368", background: "#f8f9fa", borderRadius: 8, padding: "10px 12px", marginBottom: 16 }}>
        <div>
          Support<br />
          <span style={{ color: "#202124", fontWeight: 600, fontSize: 13 }}>${support.toFixed(2)}</span>
        </div>
        <div style={{ textAlign: "right" }}>
          Resistance<br />
          <span style={{ color: "#202124", fontWeight: 600, fontSize: 13 }}>${resistance.toFixed(2)}</span>
        </div>
      </div>

      <div style={{ fontSize: 12, fontWeight: 600, color: "#202124", marginBottom: 6 }}>Layer scores</div>
      <ResponsiveContainer width="100%" height={110}>
        <BarChart data={layerData} margin={{ top: 0, right: 0, left: -24, bottom: 0 }}>
          <XAxis dataKey="layer" tick={{ fontSize: 9, fill: "#80868b" }} interval={0} angle={-35} textAnchor="end" height={40} />
          <YAxis hide domain={[0, 10]} />
          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e8eaed", background: "#fff" }} />
          <Bar dataKey="val" radius={[3, 3, 0, 0]}>
            {layerData.map((d, i) => (
              <Cell key={i} fill={d.val >= 7 ? "#188038" : d.val >= 5 ? "#f9ab00" : "#c5221f"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <button
        onClick={onOpenFactors}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 13,
          color: "#1a73e8",
          background: "none",
          border: "none",
          cursor: "pointer",
          padding: "10px 0",
          fontWeight: 500,
        }}
      >
        <Info size={14} /> View full 50-factor breakdown <ExternalLink size={12} />
      </button>

      <div style={{ fontSize: 12, fontWeight: 600, color: "#202124", margin: "10px 0 8px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span>Why this score</span>
        {onAskAi && (
          <button
            onClick={() => onAskAi(`Explain the 50-factor conviction score and bear case for ${detail.symbol}`)}
            style={{ background: "none", border: "none", color: "#1a73e8", fontSize: 11, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}
          >
            <Sparkles size={12} /> Ask AI
          </button>
        )}
      </div>
      {detail.reasons && detail.reasons.length > 0 ? (
        detail.reasons.map((r: any, i: number) => {
          const text = typeof r === "string" ? r : r.text;
          const type = typeof r === "object" && r.type ? r.type : "neutral";
          const code = typeof r === "object" && r.factor ? r.factor : (r as any).code || (type === "bear" ? "F41" : "F44");
          return (
            <div key={i} style={{ display: "flex", gap: 8, marginBottom: 10, alignItems: "flex-start" }}>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: "#fff",
                  background: reasonColor[type] || "#5f6368",
                  borderRadius: 4,
                  padding: "2px 6px",
                  flexShrink: 0,
                  marginTop: 1,
                }}
              >
                {code}
              </span>
              <span style={{ fontSize: 12.5, color: "#3c4043", lineHeight: 1.45 }}>{text}</span>
            </div>
          );
        })
      ) : (
        <div style={{ fontSize: 12, color: "#80868b", fontStyle: "italic", marginBottom: 10 }}>
          No specific vetoes or warnings triggered for this setup.
        </div>
      )}

      <div style={{ fontSize: 12, fontWeight: 600, color: "#202124", margin: "14px 0 8px", display: "flex", alignItems: "center", gap: 6 }}>
        <Newspaper size={13} /> News feeding this score
      </div>
      {detail.news && detail.news.length > 0 ? (
        detail.news.map((n, i) => {
          const title = n.headline;
          const source = n.source || "News";
          const time = n.publishedAt ? new Date(n.publishedAt).toLocaleDateString() : "Today";
          const url = n.url || "#";
          return (
            <div key={i} style={{ marginBottom: 10, paddingBottom: 10, borderBottom: i < detail.news.length - 1 ? "1px solid #f1f3f4" : "none" }}>
              <a href={url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none", color: "inherit" }}>
                <div style={{ fontSize: 12.5, color: "#202124", lineHeight: 1.4, fontWeight: 500 }}>{title}</div>
                <div style={{ fontSize: 11, color: "#80868b", marginTop: 2 }}>
                  {source} · {time}
                </div>
              </a>
            </div>
          );
        })
      ) : (
        <div style={{ fontSize: 12, color: "#80868b", fontStyle: "italic" }}>
          No recent news catalysts found.
        </div>
      )}
    </div>
  );
}
