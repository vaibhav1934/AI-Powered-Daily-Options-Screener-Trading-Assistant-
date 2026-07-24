"use client";

import { useState } from "react";
import { 
  Activity, 
  Clock, 
  MessageSquare, 
  ShieldAlert, 
  TrendingUp, 
  Filter,
  CheckCircle2,
  Lock,
  Camera
} from "lucide-react";
import { cn } from "@/lib/utils";

// Mock data to scaffold the UI before backend integration
const MOCK_WATCHLIST = [
  { id: 1, ticker: "NVDA", score: 8.5, bucket: "LOW", list: "LIST_1", status: "PENDING_CONFIRMATION", gap: "+2.4%", price: "128.50" },
  { id: 2, ticker: "AAPL", score: 7.2, bucket: "MODERATE", list: "LIST_1", status: "CONFIRMED", gap: "+1.1%", price: "215.20" },
  { id: 3, ticker: "PLTR", score: 6.5, bucket: "HIGH_RISK_HALO", list: "LIST_2", status: "PENDING_CONFIRMATION", gap: "+5.2%", price: "25.10" },
  { id: 4, ticker: "TSLA", score: 0.0, bucket: "UNASSIGNED", list: "LIST_2", status: "LOCKED", gap: "-1.5%", price: "185.30", veto: "F40: No Clean Setup" },
];

export default function Home() {
  const [activeTab, setActiveTab] = useState("watchlist");

  return (
    <main className="flex h-screen bg-slate-950 text-slate-300 overflow-hidden font-sans">
      
      {/* LEFT PANEL: Watchlist & Dashboard */}
      <div className="flex-1 flex flex-col h-full border-r border-slate-800">
        
        {/* Header */}
        <header className="h-16 border-b border-slate-800 flex items-center justify-between px-6 bg-slate-950/50 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
              <Activity size={20} />
            </div>
            <h1 className="text-xl font-semibold text-slate-100 tracking-tight">AI Options Screener</h1>
          </div>
          <div className="flex items-center gap-4 text-sm font-medium">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-slate-900 border border-slate-800 text-amber-400">
              <Clock size={16} />
              <span>10:24 AM CST (Pre-Cutoff)</span>
            </div>
          </div>
        </header>

        {/* Filters Bar */}
        <div className="h-14 border-b border-slate-800 flex items-center px-6 gap-4 bg-slate-900/30">
          <button className="flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200 transition-colors">
            <Filter size={16} />
            <span>Filters</span>
          </button>
          <div className="h-4 w-px bg-slate-800 mx-2"></div>
          <div className="flex gap-2">
            <span className="px-3 py-1 text-xs font-medium rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">List 1 (Daily)</span>
            <span className="px-3 py-1 text-xs font-medium rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Low Risk</span>
          </div>
        </div>

        {/* Watchlist Content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            
            {MOCK_WATCHLIST.map((item) => (
              <div 
                key={item.id} 
                className="group relative flex flex-col p-5 rounded-xl border border-slate-800 bg-slate-900/50 hover:bg-slate-800/80 transition-all duration-200 hover:shadow-xl hover:shadow-indigo-500/5 hover:-translate-y-0.5 overflow-hidden"
              >
                {/* Status Indicator Bar */}
                <div className={cn(
                  "absolute top-0 left-0 w-full h-1",
                  item.status === 'CONFIRMED' ? "bg-emerald-500" :
                  item.status === 'LOCKED' ? "bg-red-500" : "bg-amber-500"
                )} />

                <div className="flex justify-between items-start mb-4 pt-1">
                  <div>
                    <h2 className="text-2xl font-bold text-slate-100 tracking-tight">{item.ticker}</h2>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-sm text-slate-400">${item.price}</span>
                      <span className={cn(
                        "text-xs font-medium px-1.5 py-0.5 rounded-sm",
                        item.gap.startsWith('+') ? "text-emerald-400 bg-emerald-400/10" : "text-red-400 bg-red-400/10"
                      )}>
                        {item.gap} gap
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-col items-end">
                    <span className={cn(
                      "text-xl font-bold font-mono tracking-tighter",
                      item.score >= 7.0 ? "text-emerald-400" : 
                      item.score >= 5.0 ? "text-amber-400" : "text-slate-500"
                    )}>
                      {item.score.toFixed(1)}
                    </span>
                    <span className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">Conviction</span>
                  </div>
                </div>

                <div className="mt-auto space-y-3">
                  {/* Badges */}
                  <div className="flex flex-wrap gap-2">
                    <span className={cn(
                      "text-[10px] font-semibold uppercase tracking-wider px-2 py-1 rounded-md border",
                      item.bucket === 'LOW' ? "border-emerald-500/30 text-emerald-400 bg-emerald-500/10" :
                      item.bucket === 'MODERATE' ? "border-amber-500/30 text-amber-400 bg-amber-500/10" :
                      item.bucket === 'HIGH_RISK_HALO' ? "border-fuchsia-500/30 text-fuchsia-400 bg-fuchsia-500/10" :
                      "border-slate-700 text-slate-500 bg-slate-800"
                    )}>
                      {item.bucket.replace('_', ' ')}
                    </span>
                    <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-1 rounded-md border border-indigo-500/30 text-indigo-400 bg-indigo-500/10">
                      {item.list.replace('_', ' ')}
                    </span>
                  </div>

                  {/* Veto or Status Action */}
                  {item.veto ? (
                    <div className="flex items-start gap-2 p-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs">
                      <ShieldAlert size={14} className="shrink-0 mt-0.5" />
                      <span className="font-medium leading-snug">{item.veto}</span>
                    </div>
                  ) : (
                    <button className={cn(
                      "w-full flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-semibold transition-all",
                      item.status === 'CONFIRMED' 
                        ? "bg-slate-800/50 text-emerald-400 border border-emerald-500/20 cursor-default"
                        : "bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20"
                    )}>
                      {item.status === 'CONFIRMED' ? (
                        <>
                          <CheckCircle2 size={16} />
                          <span>Confirmed</span>
                        </>
                      ) : (
                        <>
                          <Camera size={16} />
                          <span>Confirm Setup</span>
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            ))}

          </div>
        </div>
      </div>

      {/* RIGHT PANEL: GenAI Chat Assistant */}
      <div className="w-[450px] flex flex-col h-full bg-slate-900 border-l border-slate-800 shadow-2xl z-10 relative">
        <div className="h-16 border-b border-slate-800 flex items-center px-6 bg-slate-950">
          <div className="flex items-center gap-3 text-indigo-400">
            <MessageSquare size={20} />
            <h2 className="text-base font-semibold text-slate-100">AI Assistant</h2>
          </div>
        </div>
        
        {/* Chat History */}
        <div className="flex-1 overflow-auto p-6 space-y-6">
          <div className="flex gap-4">
            <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center shrink-0 shadow-lg shadow-indigo-500/20">
              <Activity size={14} className="text-white" />
            </div>
            <div className="bg-slate-800/80 border border-slate-700/50 p-4 rounded-2xl rounded-tl-sm text-sm text-slate-200 leading-relaxed shadow-sm">
              <p>Good morning. The daily scan is complete.</p>
              <p className="mt-2 text-slate-400 text-xs font-mono bg-slate-900/50 p-2 rounded border border-slate-700/30">
                Processed 1,204 tickers.<br/>
                Actionable (List 1): 3<br/>
                Vetoed: 412
              </p>
              <p className="mt-3">How can I help you analyze today's setups?</p>
            </div>
          </div>
          
          <div className="flex gap-4 flex-row-reverse">
            <div className="bg-indigo-600 p-4 rounded-2xl rounded-tr-sm text-sm text-white leading-relaxed shadow-md shadow-indigo-900/20 max-w-[85%]">
              <p>Why was TSLA vetoed today?</p>
            </div>
          </div>

          <div className="flex gap-4">
            <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center shrink-0 shadow-lg shadow-indigo-500/20">
              <Activity size={14} className="text-white" />
            </div>
            <div className="bg-slate-800/80 border border-slate-700/50 p-4 rounded-2xl rounded-tl-sm text-sm text-slate-200 leading-relaxed shadow-sm">
              <p>TSLA was vetoed by <strong>F40: No Clean Setup</strong>.</p>
              <ul className="mt-2 space-y-1 list-disc list-inside text-slate-300">
                <li>Conviction Score: 0.0 (Below 3.0 minimum)</li>
                <li>Live factors triggered: 0 (Below 3 minimum)</li>
              </ul>
              <p className="mt-3 text-red-400 text-xs font-medium flex items-center gap-1 bg-red-400/10 p-2 rounded-md border border-red-500/20">
                <Lock size={12} /> Execution details locked.
              </p>
            </div>
          </div>
        </div>

        {/* Chat Input */}
        <div className="p-4 bg-slate-950 border-t border-slate-800">
          <div className="relative flex items-center">
            <input 
              type="text" 
              placeholder="Ask about a ticker or rule..." 
              className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded-xl pl-4 pr-12 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all placeholder:text-slate-500"
            />
            <button className="absolute right-2 p-2 rounded-lg text-indigo-400 hover:text-indigo-300 hover:bg-indigo-500/10 transition-colors">
              <TrendingUp size={18} />
            </button>
          </div>
          <div className="mt-3 flex gap-2 overflow-x-auto pb-1 no-scrollbar">
            <button className="whitespace-nowrap px-3 py-1.5 bg-slate-800/50 hover:bg-slate-800 border border-slate-700 text-xs rounded-full text-slate-400 transition-colors">
              Explain NVDA score
            </button>
            <button className="whitespace-nowrap px-3 py-1.5 bg-slate-800/50 hover:bg-slate-800 border border-slate-700 text-xs rounded-full text-slate-400 transition-colors">
              Filter by Low Risk
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
