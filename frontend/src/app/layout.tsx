import type { Metadata } from "next";
import "./globals.css";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "StockGlass AI — Institutional Options & Stock Screener",
  description: "Automated 50-factor scanning framework and GenAI assistant",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body
        className={cn(
          "min-h-screen bg-slate-950 text-slate-50 font-sans antialiased"
        )}
      >
        {children}
      </body>
    </html>
  );
}
