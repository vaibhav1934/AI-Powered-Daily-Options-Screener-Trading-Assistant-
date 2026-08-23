"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart2, BriefcaseBusiness } from "lucide-react";

interface MobileBottomNavProps {
  isMobile?: boolean;
}

export function MobileBottomNav({ isMobile }: MobileBottomNavProps) {
  const pathname = usePathname();

  if (!isMobile) return null;

  return (
    <div
      style={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        height: 56,
        background: "rgba(255, 255, 255, 0.95)",
        backdropFilter: "blur(10px)",
        WebkitBackdropFilter: "blur(10px)",
        borderTop: "1px solid #e8eaed",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-around",
        zIndex: 900,
        boxShadow: "0 -2px 10px rgba(0, 0, 0, 0.05)",
        boxSizing: "border-box",
        padding: "0 16px",
      }}
    >
      <Link
        href="/"
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 3,
          textDecoration: "none",
          color: pathname === "/" ? "#1a73e8" : "#5f6368",
          fontSize: 11,
          fontWeight: pathname === "/" ? 700 : 500,
          padding: "6px 24px",
          borderRadius: 16,
          background: pathname === "/" ? "#e8f0fe" : "transparent",
          transition: "all 0.15s ease",
        }}
      >
        <BarChart2 size={18} color={pathname === "/" ? "#1a73e8" : "#5f6368"} />
        <span>Screener</span>
      </Link>

      <Link
        href="/portfolio"
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 3,
          textDecoration: "none",
          color: pathname === "/portfolio" ? "#1a73e8" : "#5f6368",
          fontSize: 11,
          fontWeight: pathname === "/portfolio" ? 700 : 500,
          padding: "6px 24px",
          borderRadius: 16,
          background: pathname === "/portfolio" ? "#e8f0fe" : "transparent",
          transition: "all 0.15s ease",
        }}
      >
        <BriefcaseBusiness size={18} color={pathname === "/portfolio" ? "#1a73e8" : "#5f6368"} />
        <span>Portfolio</span>
      </Link>
    </div>
  );
}
