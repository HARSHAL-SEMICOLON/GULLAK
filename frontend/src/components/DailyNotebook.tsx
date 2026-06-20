"use client";
import { useState } from "react";
import { gullakApi } from "@/lib/api";
import { RefreshCw } from "lucide-react";

const QUICK_CATS = [
  { id: "milk",      name: "Milk",      icon: "🥛", category: "Groceries" },
  { id: "veggies",   name: "Veggies",   icon: "🥬", category: "Groceries" },
  { id: "movies",    name: "Movies",    icon: "🎟️", category: "Entertainment" },
  { id: "gym",       name: "Gym",       icon: "🏋️", category: "Health & Fitness" },
  { id: "otts",      name: "OTTs",      icon: "📺", category: "Subscriptions" },
  { id: "spotify",   name: "Spotify",   icon: "🎵", category: "Subscriptions" },
  { id: "transport", name: "Auto/Cab",  icon: "🚕", category: "Transport" },
  { id: "food",      name: "Food",      icon: "🍕", category: "Food" },
  { id: "shopping",  name: "Shopping",  icon: "🛍️", category: "Shopping" },
];

interface DailyNotebookProps {
  onLogged: () => void;
  profileId: string;
}

export function DailyNotebook({ onLogged, profileId }: DailyNotebookProps) {
  const [selected, setSelected] = useState("");
  const [amount, setAmount]     = useState("");
  const [custom, setCustom]     = useState("");
  const [loading, setLoading]   = useState(false);
  const [toast, setToast]       = useState("");

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 2500);
  };

  const handleLog = async () => {
    if (!selected || !amount) return;
    setLoading(true);
    const cat = QUICK_CATS.find(c => c.id === selected)!;
    try {
      await gullakApi.addDailyLog(
        { item_name: custom || cat.name, category: cat.category, amount: parseFloat(amount) },
        profileId
      );
      onLogged();
      setAmount(""); setCustom(""); setSelected("");
      showToast(`✓ Logged ₹${amount} for ${custom || cat.name}`);
    } catch {
      showToast("Failed — is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass rounded-2xl p-5 space-y-4 relative overflow-hidden">

      {/* Subtle gradient accent */}
      <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-violet-600/8 to-transparent rounded-bl-full pointer-events-none" />

      {/* Toast */}
      {toast && (
        <div className="absolute top-3 right-3 glass-md text-white text-[11px] px-3 py-1.5 rounded-lg slide-up z-10 font-medium">
          {toast}
        </div>
      )}

      <div>
        <div className="flex items-center gap-2">
          <span className="text-lg">📓</span>
          <p className="text-white font-semibold text-sm">Daily Log</p>
        </div>
        <p className="text-slate-600 text-xs mt-0.5 ml-7">Log cash & frequent spends</p>
      </div>

      {/* Category grid */}
      <div className="grid grid-cols-3 gap-2">
        {QUICK_CATS.map(cat => (
          <button
            key={cat.id}
            onClick={() => setSelected(cat.id === selected ? "" : cat.id)}
            className={`p-2.5 rounded-xl border transition-all flex flex-col items-center gap-1 ${
              selected === cat.id
                ? "bg-violet-900/40 border-violet-500/60 text-violet-300 shadow-[0_0_16px_rgba(124,58,237,0.2)]"
                : "glass text-slate-500 hover:border-white/16 hover:text-slate-300"
            }`}
          >
            <span className="text-xl">{cat.icon}</span>
            <span className="text-[9px] font-medium leading-tight">{cat.name}</span>
          </button>
        ))}
      </div>

      {/* Input row */}
      <div className="space-y-2">
        <input
          type="text"
          placeholder="Custom name (optional)"
          value={custom}
          onChange={e => setCustom(e.target.value)}
          className="w-full glass rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-violet-600/60 transition-colors"
        />
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 text-sm font-medium">₹</span>
            <input
              type="number"
              placeholder="Amount"
              value={amount}
              onChange={e => setAmount(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleLog()}
              className="w-full glass rounded-xl pl-7 pr-4 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-violet-600/60 transition-colors"
            />
          </div>
          <button
            onClick={handleLog}
            disabled={!selected || !amount || loading}
            className="bg-violet-600 hover:bg-violet-500 disabled:opacity-30 disabled:cursor-not-allowed text-white font-semibold px-5 rounded-xl text-sm transition-all flex items-center gap-1.5 flex-shrink-0"
          >
            {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : "Log"}
          </button>
        </div>
      </div>
    </div>
  );
}
