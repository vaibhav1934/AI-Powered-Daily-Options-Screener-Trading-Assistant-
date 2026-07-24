import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AI-Powered Daily Options Screener",
  description: "Automated 50-factor scanning framework and GenAI assistant",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={cn(
          "min-h-screen bg-slate-950 text-slate-50 font-sans antialiased",
          inter.variable
        )}
      >
        {children}
      </body>
    </html>
  );
}
