// src/components/auth/LoginModal.tsx
// Login modal for StockGlass AI
"use client";

import React, { useState } from "react";
import { loginUser, registerUser, UserProfile } from "@/lib/auth";
import { Lock, AlertCircle, Loader2 } from "lucide-react";

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (user: UserProfile) => void;
}

export default function LoginModal({ isOpen, onClose, onSuccess }: LoginModalProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;
  const isRegister = mode === "register";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError("Please enter both username and password.");
      return;
    }
    if (mode === "register") {
      if (password.length < 8) {
        setError("Password must be at least 8 characters long.");
        return;
      }
      if (password !== confirmPassword) {
        setError("Passwords do not match.");
        return;
      }
    }

    setLoading(true);
    setError(null);

    try {
      const user = mode === "login"
        ? await loginUser(username.trim(), password)
        : await registerUser(username.trim(), password);
      onSuccess(user);
      onClose();
    } catch (err: any) {
      setError(err.message || (mode === "login" ? "Login failed. Please check your credentials." : "Registration failed. Please try again."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="auth-modal-overlay"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
        background: "rgba(32, 33, 36, 0.45)",
        backdropFilter: "blur(6px)",
      }}
      onClick={onClose}
    >
      <div
        className="auth-modal-card"
        style={{
          position: "relative",
          width: "100%",
          maxWidth: 420,
          background: "#ffffff",
          borderRadius: 16,
          boxShadow: "0 24px 48px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(26, 115, 232, 0.12)",
          border: "1px solid #e8eaed",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="auth-modal-scroll" style={{ width: "100%", boxSizing: "border-box" }}>
        {/* Brand Icon Header */}
        <div
          style={{
            width: 52,
            height: 52,
            borderRadius: 14,
            background: "#e8f0fe",
            border: "1px solid #d2e3fc",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            marginBottom: 16,
            color: "#1a73e8",
            boxShadow: "0 4px 12px rgba(26, 115, 232, 0.12)",
          }}
        >
          <Lock size={24} strokeWidth={2.2} />
        </div>

        <h2 style={{ fontSize: 20, fontWeight: 700, color: "#202124", margin: 0, letterSpacing: -0.3 }}>
          {mode === "login" ? "Welcome Back" : "Create Your Account"}
        </h2>
        <p style={{ fontSize: 13, color: "#5f6368", textAlign: "center", margin: "6px 0 24px", lineHeight: 1.4 }}>
          {mode === "login"
            ? "Sign in to access your screener and portfolio workspace."
            : "Create an account to start using StockGlass AI."}
        </p>

        <div style={{ width: "100%", display: "flex", gap: 8, marginBottom: 20, background: "#f1f3f4", padding: 4, borderRadius: 12 }}>
          <button
            type="button"
            onClick={() => { setMode("login"); setError(null); }}
            style={{ flex: 1, padding: "8px 12px", borderRadius: 10, border: "none", background: mode === "login" ? "#fff" : "transparent", color: mode === "login" ? "#1a73e8" : "#5f6368", fontSize: 13, fontWeight: 700, cursor: "pointer" }}
          >
            Log In
          </button>
          <button
            type="button"
            onClick={() => { setMode("register"); setError(null); }}
            style={{ flex: 1, padding: "8px 12px", borderRadius: 10, border: "none", background: mode === "register" ? "#fff" : "transparent", color: mode === "register" ? "#1a73e8" : "#5f6368", fontSize: 13, fontWeight: 700, cursor: "pointer" }}
          >
            Register
          </button>
        </div>

        <div style={{ width: "100%", marginBottom: error ? 20 : 0 }}>
          {error ? (
            <div
              style={{
                width: "100%",
                background: "#fce8e6",
                border: "1px solid #fad2cf",
                color: "#c5221f",
                padding: "10px 14px",
                borderRadius: 10,
                fontSize: 13,
                fontWeight: 500,
                display: "flex",
                alignItems: "center",
                gap: 8,
                boxSizing: "border-box",
                marginBottom: 20,
              }}
            >
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          ) : null}
        </div>

        <form onSubmit={handleSubmit} style={{ width: "100%", display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label
              style={{
                display: "block",
                fontSize: 11,
                fontWeight: 600,
                color: "#5f6368",
                textTransform: "uppercase",
                letterSpacing: 0.6,
                marginBottom: 6,
              }}
            >
              Username
            </label>
            <input
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. trader_jane"
              disabled={loading}
              autoFocus
              style={{
                width: "100%",
                padding: "10px 14px",
                borderRadius: 10,
                border: "1px solid #e8eaed",
                background: "#f8f9fa",
                fontSize: 14,
                color: "#202124",
                outline: "none",
                boxSizing: "border-box",
                transition: "all 0.15s ease",
              }}
              onFocus={(e) => {
                e.target.style.borderColor = "#1a73e8";
                e.target.style.boxShadow = "0 0 0 3px #e8f0fe";
                e.target.style.background = "#fff";
              }}
              onBlur={(e) => {
                e.target.style.borderColor = "#e8eaed";
                e.target.style.boxShadow = "none";
                e.target.style.background = "#f8f9fa";
              }}
            />
          </div>

          <div>
            <label
              style={{
                display: "block",
                fontSize: 11,
                fontWeight: 600,
                color: "#5f6368",
                textTransform: "uppercase",
                letterSpacing: 0.6,
                marginBottom: 6,
              }}
            >
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              disabled={loading}
              style={{
                width: "100%",
                padding: "10px 14px",
                borderRadius: 10,
                border: "1px solid #e8eaed",
                background: "#f8f9fa",
                fontSize: 14,
                color: "#202124",
                outline: "none",
                boxSizing: "border-box",
                transition: "all 0.15s ease",
              }}
              onFocus={(e) => {
                e.target.style.borderColor = "#1a73e8";
                e.target.style.boxShadow = "0 0 0 3px #e8f0fe";
                e.target.style.background = "#fff";
              }}
              onBlur={(e) => {
                e.target.style.borderColor = "#e8eaed";
                e.target.style.boxShadow = "none";
                e.target.style.background = "#f8f9fa";
              }}
            />
          </div>

          {isRegister ? (
            <div>
              <label
                style={{
                  display: "block",
                  fontSize: 11,
                  fontWeight: 600,
                  color: "#5f6368",
                  textTransform: "uppercase",
                  letterSpacing: 0.6,
                  marginBottom: 6,
                }}
              >
                Confirm Password
              </label>
              <input
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••••••"
                disabled={loading}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: 10,
                  border: "1px solid #e8eaed",
                  background: "#f8f9fa",
                  fontSize: 14,
                  color: "#202124",
                  outline: "none",
                  boxSizing: "border-box",
                  transition: "all 0.15s ease",
                }}
              />
            </div>
          ) : null}

          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 8 }}>
            <button
              type="submit"
              disabled={loading}
              style={{
                width: "100%",
                padding: "12px 16px",
                borderRadius: 10,
                background: "linear-gradient(135deg, #1a73e8, #0d47a1)",
                color: "#fff",
                fontSize: 14,
                fontWeight: 600,
                border: "none",
                cursor: loading ? "not-allowed" : "pointer",
                boxShadow: "0 4px 12px rgba(26, 115, 232, 0.28)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                transition: "all 0.15s ease",
                opacity: loading ? 0.7 : 1,
              }}
            >
              {loading ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  <span>{mode === "login" ? "Authenticating..." : "Creating account..."}</span>
                </>
              ) : (
                <span>{mode === "login" ? "Log In to StockGlass Pro" : "Create StockGlass Account"}</span>
              )}
            </button>

            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              style={{
                width: "100%",
                padding: "10px",
                background: "none",
                border: "none",
                color: "#5f6368",
                fontSize: 13,
                fontWeight: 500,
                cursor: "pointer",
                borderRadius: 8,
                transition: "background 0.15s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "#f1f3f4";
                e.currentTarget.style.color = "#202124";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "none";
                e.currentTarget.style.color = "#5f6368";
              }}
            >
              Cancel / Return to Summary Mode
            </button>
          </div>
        </form>

        <div style={{ marginTop: 24, paddingTop: 16, borderTop: "1px solid #e8eaed", width: "100%", textAlign: "center" }}>
          <p style={{ fontSize: 11, color: "#70757a", margin: 0 }}>
            Secure JWT session with encrypted password verification.
          </p>
        </div>
        </div>
      </div>
    </div>
  );
}
