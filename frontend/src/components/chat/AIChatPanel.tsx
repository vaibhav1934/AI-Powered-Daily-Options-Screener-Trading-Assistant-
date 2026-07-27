"use client";
import React, { useState, useRef, useEffect } from "react";
import { ChatMessage, StockListItem } from "@/types/stockglass";
import { streamChat } from "@/lib/sse";
import { Activity, MessageSquare, Sparkles, Send } from "lucide-react";

interface AIChatPanelProps {
  symbol: string;
  item: StockListItem | null;
  messages: ChatMessage[];
  onAddMessage: (msg: ChatMessage) => void;
  onUpdateLastAssistantMessage: (content: string) => void;
}

const QUICK_PROMPTS = [
  { label: "Explain conviction score", prompt: "Explain the 50-factor conviction score and standing rules for this setup." },
  { label: "F41 Bear Case check", prompt: "Analyze the F41 bear case first rule and downside risks for this setup." },
  { label: "Filter by Low Risk", prompt: "How does this ticker align with low risk options strategy criteria?" },
];

export function AIChatPanel({
  symbol,
  item,
  messages,
  onAddMessage,
  onUpdateLastAssistantMessage,
}: AIChatPanelProps) {
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const conversationId = useRef("");

  useEffect(() => {
    if (!conversationId.current) {
      conversationId.current = `conv-${Date.now()}`;
    }
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  const handleSend = async (textToSend: string) => {
    if (!textToSend.trim() || isStreaming) return;

    const userMsg: ChatMessage = { role: "user", content: textToSend };
    onAddMessage(userMsg);
    setInput("");
    setIsStreaming(true);

    const placeholderAssistant: ChatMessage = { role: "assistant", content: "" };
    onAddMessage(placeholderAssistant);

    let accumulated = "";
    try {
      const stream = streamChat(
        `[Context: Selected Ticker ${symbol || "Market"}, Price: $${item?.price || "N/A"}, Score: ${item?.convictionScore || "N/A"}]

User Query: ${textToSend}`,
        conversationId.current || "default-conv"
      );

      for await (const chunk of stream) {
        if (chunk.type === "chunk") {
          accumulated += chunk.content;
          onUpdateLastAssistantMessage(accumulated);
        } else if (chunk.type === "tool_call") {
          accumulated += `\n*[Executing Tool: ${chunk.name}...]*\n`;
          onUpdateLastAssistantMessage(accumulated);
        }
      }
    } catch (err: any) {
      if (!accumulated) {
        onUpdateLastAssistantMessage(
          `❌ **Live AI Engine Error:** Unable to reach backend chat server (${err.message || "Connection failed"}). Ensure uvicorn is running on port 8001.`
        );
      } else {
        onUpdateLastAssistantMessage(accumulated + `\n\n*[Stream interrupted: ${err.message}]*`);
      }
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div style={{ borderLeft: "1px solid #e8eaed", width: 360, flexShrink: 0, background: "#fff", display: "flex", flexDirection: "column", height: "100%", fontFamily: "'Google Sans', Roboto, Arial, sans-serif", color: "#202124" }}>
      {/* Header */}
      <div style={{ padding: "16px 20px", borderBottom: "1px solid #e8eaed", display: "flex", alignItems: "center", justifyContent: "space-between", background: "#fff" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <MessageSquare size={18} color="#1a73e8" />
          <span style={{ fontSize: 16, fontWeight: 500 }}>AI Assistant</span>
          <span style={{ fontSize: 10, background: "#e6f4ea", color: "#188038", padding: "2px 6px", borderRadius: 10, fontWeight: 600 }}>LIVE 50-FACTOR</span>
        </div>
        <div style={{ fontSize: 12, color: "#5f6368" }}>
          Active: <strong style={{ color: "#202124" }}>{symbol || "Market"}</strong>
        </div>
      </div>

      {/* Chat History */}
      <div style={{ flex: 1, overflowY: "auto", padding: "20px", display: "flex", flexDirection: "column", gap: 16 }}>
        {messages.length === 0 ? (
          <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
            <div style={{ width: 28, height: 28, borderRadius: "50%", background: "#1a73e8", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <Activity size={14} />
            </div>
            <div style={{ background: "#f8f9fa", border: "1px solid #e8eaed", padding: 14, borderRadius: 12, fontSize: 13, color: "#3c4043", lineHeight: 1.5 }}>
              <p style={{ margin: 0 }}>Good day. The 50-factor framework is live and monitoring {symbol || "all options setups"}.</p>
              {item && (
                <div style={{ marginTop: 8, padding: 8, background: "#fff", borderRadius: 8, border: "1px solid #e8eaed", fontSize: 12, color: "#5f6368" }}>
                  <strong style={{ color: "#202124" }}>{item.symbol}</strong> · Score: {(item.score ?? 0).toFixed(1)}<br />
                  Price: ${item.price.toFixed(2)} ({item.chg >= 0 ? "+" : ""}{(item.chg ?? 0).toFixed(2)})
                </div>
              )}
              <p style={{ margin: "8px 0 0" }}>How can I help you analyze today&apos;s setups or codified rules?</p>
            </div>
          </div>
        ) : null}

        {messages.map((msg, i) => {
          const isUser = msg.role === "user";
          return (
            <div key={i} style={{ display: "flex", gap: 10, flexDirection: isUser ? "row-reverse" : "row", alignItems: "flex-start" }}>
              {!isUser && (
                <div style={{ width: 28, height: 28, borderRadius: "50%", background: "#1a73e8", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <Activity size={14} />
                </div>
              )}
              <div
                style={{
                  padding: "10px 14px",
                  borderRadius: 14,
                  fontSize: 13,
                  lineHeight: 1.5,
                  maxWidth: "85%",
                  whiteSpace: "pre-wrap",
                  background: isUser ? "#e8f0fe" : "#f8f9fa",
                  color: isUser ? "#1a73e8" : "#202124",
                  border: isUser ? "1px solid #d2e3fc" : "1px solid #e8eaed",
                  fontWeight: isUser ? 500 : 400,
                }}
              >
                {msg.content || (isStreaming && i === messages.length - 1 ? (
                  <span style={{ color: "#5f6368", fontStyle: "italic" }}>Computing factors...</span>
                ) : null)}
              </div>
            </div>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Chat Input */}
      <div style={{ padding: "14px 16px", borderTop: "1px solid #e8eaed", background: "#fff" }}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend(input);
          }}
          style={{ position: "relative", display: "flex", alignItems: "center" }}
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isStreaming}
            placeholder="Ask about a ticker or rule..."
            style={{
              width: "100%",
              padding: "10px 38px 10px 14px",
              borderRadius: 20,
              border: "1px solid #e8eaed",
              background: "#f1f3f4",
              fontSize: 13,
              outline: "none",
              color: "#202124",
            }}
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            style={{
              position: "absolute",
              right: 8,
              background: "none",
              border: "none",
              color: "#1a73e8",
              cursor: "pointer",
              padding: 4,
              opacity: !input.trim() || isStreaming ? 0.4 : 1,
            }}
          >
            <Send size={16} />
          </button>
        </form>

        <div style={{ marginTop: 10, display: "flex", gap: 6, overflowX: "auto", paddingBottom: 2 }}>
          {QUICK_PROMPTS.map((qp, i) => (
            <button
              key={i}
              type="button"
              onClick={() => handleSend(qp.prompt)}
              disabled={isStreaming}
              style={{
                whiteSpace: "nowrap",
                padding: "4px 10px",
                background: "#fff",
                border: "1px solid #e8eaed",
                borderRadius: 14,
                fontSize: 11.5,
                color: "#5f6368",
                cursor: "pointer",
              }}
            >
              {qp.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
