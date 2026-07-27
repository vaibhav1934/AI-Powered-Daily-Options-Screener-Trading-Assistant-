// src/components/auth/AuthOverlay.tsx
// Glassmorphic Authentication Overlay for Institutional Features (Brand Aesthetic)
"use client";

import React, { useState, useEffect } from "react";
import { isAuthenticated, getStoredUser, UserProfile } from "@/lib/auth";
import LoginModal from "./LoginModal";
import { Lock, ShieldCheck, Sparkles } from "lucide-react";

interface AuthOverlayProps {
  children: React.ReactNode;
  featureName?: string;
  description?: string;
  onLoginSuccess?: (user: UserProfile) => void;
}

export default function AuthOverlay({
  children,
  featureName = "Deep Analytics & AI Chat",
  description = "Log in with institutional credentials to access 50-factor breakdowns, live options chain execution, and AI trading assistant synthesis.",
  onLoginSuccess,
}: AuthOverlayProps) {
  const [authed, setAuthed] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [user, setUser] = useState<UserProfile | null>(null);

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

  const handleSuccess = (loggedInUser: UserProfile) => {
    setAuthed(true);
    setUser(loggedInUser);
    if (onLoginSuccess) {
      onLoginSuccess(loggedInUser);
    }
  };

  if (authed) {
    return <>{children}</>;
  }

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        minHeight: 460,
        overflow: "hidden",
        borderRadius: 16,
        border: "1px solid #e8eaed",
        background: "#f8f9fa",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Blurred Underlying Content */}
      <div
        style={{
          width: "100%",
          height: "100%",
          filter: "blur(7px)",
          pointerEvents: "none",
          userSelect: "none",
          opacity: 0.35,
          transition: "all 0.3s ease",
          flex: 1,
        }}
      >
        {children}
      </div>

      {/* Glassmorphic Locked Card Overlay */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          zIndex: 20,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: 24,
          background: "radial-gradient(circle at center, rgba(255, 255, 255, 0.4) 0%, rgba(248, 249, 250, 0.85) 100%)",
        }}
      >
        <div
          style={{
            position: "relative",
            width: "100%",
            maxWidth: 380,
            background: "rgba(255, 255, 255, 0.94)",
            backdropFilter: "blur(16px)",
            borderRadius: 20,
            padding: "32px 28px",
            border: "1px solid #d2e3fc",
            boxShadow: "0 16px 40px rgba(26, 115, 232, 0.12), 0 4px 12px rgba(0, 0, 0, 0.04)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            textAlign: "center",
            boxSizing: "border-box",
          }}
        >
          {/* Brand Shield Badge */}
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 16,
              background: "#e8f0fe",
              border: "1px solid #d2e3fc",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: 16,
              color: "#1a73e8",
              boxShadow: "0 6px 16px rgba(26, 115, 232, 0.15)",
            }}
          >
            <Lock size={26} strokeWidth={2.2} />
          </div>

          <span
            style={{
              background: "#e8f0fe",
              color: "#1a73e8",
              border: "1px solid #d2e3fc",
              padding: "4px 12px",
              borderRadius: 20,
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: 0.8,
              textTransform: "uppercase",
              marginBottom: 12,
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <ShieldCheck size={12} /> Institutional Verification
          </span>

          <h3 style={{ fontSize: 18, fontWeight: 700, color: "#202124", margin: "0 0 8px", letterSpacing: -0.3 }}>
            {featureName}
          </h3>

          <p style={{ fontSize: 13, color: "#5f6368", lineHeight: 1.5, margin: "0 0 24px" }}>
            {description}
          </p>

          <button
            onClick={() => setIsModalOpen(true)}
            style={{
              width: "100%",
              padding: "12px 20px",
              borderRadius: 12,
              background: "linear-gradient(135deg, #1a73e8, #0d47a1)",
              color: "#fff",
              fontSize: 14,
              fontWeight: 600,
              border: "none",
              cursor: "pointer",
              boxShadow: "0 4px 14px rgba(26, 115, 232, 0.3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              transition: "all 0.15s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = "translateY(-1px)";
              e.currentTarget.style.boxShadow = "0 6px 18px rgba(26, 115, 232, 0.35)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = "0 4px 14px rgba(26, 115, 232, 0.3)";
            }}
          >
            <Lock size={15} />
            <span>Log In to Unlock Feature</span>
          </button>

          <div
            style={{
              marginTop: 18,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              fontSize: 11,
              color: "#70757a",
              fontWeight: 500,
            }}
          >
            <Sparkles size={13} color="#1a73e8" />
            <span>Zero-Mock Realtime Engine • Pro Tier</span>
          </div>
        </div>
      </div>

      <LoginModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={handleSuccess}
      />
    </div>
  );
}
