"use client";
import { useState } from "react";
import { gullakApi } from "@/lib/api";
import { RefreshCw, Trash2, Plus, X } from "lucide-react";

interface GoalsPanelProps {
  goals: any[];
  profileId: string;
  onRefresh: () => void;
}

function GoalRing({ pct }: { pct: number }) {
  const r = 22;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  const color = pct >= 80 ? "#10b981" : pct >= 40 ? "#a78bfa" : "#f59e0b";

  return (
    <svg width={52} height={52} viewBox="0 0 52 52" className="-rotate-90 flex-shrink-0">
      <circle cx={26} cy={26} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={5} />
      <circle
        cx={26} cy={26} r={r} fill="none"
        stroke={color} strokeWidth={5}
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        className="transition-all duration-1000 ease-out"
      />
    </svg>
  );
}

export function GoalsPanel({ goals, profileId, onRefresh }: GoalsPanelProps) {
  const [name, setName]         = useState("");
  const [target, setTarget]     = useState("");
  const [current, setCurrent]   = useState("");
  const [deadline, setDeadline] = useState("");
  const [loading, setLoading]   = useState(false);
  const [open, setOpen]         = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!name || !target) return;
    setLoading(true);
    try {
      await gullakApi.createGoal(
        { name, target_amount: parseFloat(target), current_amount: parseFloat(current || "0"), deadline: deadline || undefined },
        profileId
      );
      onRefresh();
      setName(""); setTarget(""); setCurrent(""); setDeadline(""); setOpen(false);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (goalId: string) => {
    setDeleting(goalId);
    try { await gullakApi.deleteGoal(goalId); onRefresh(); }
    finally { setDeleting(null); }
  };

  return (
    <div className="space-y-4">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-white font-bold text-lg">Goals</p>
          <p className="text-slate-600 text-xs mt-0.5">{goals.length} active target{goals.length !== 1 ? "s" : ""}</p>
        </div>
        <button
          onClick={() => setOpen(!open)}
          className={`flex items-center gap-1.5 text-xs px-4 py-2 rounded-xl font-semibold transition-all ${
            open
              ? "bg-white/6 text-slate-400 border border-white/8"
              : "bg-violet-600 hover:bg-violet-500 text-white"
          }`}
        >
          {open ? <><X className="w-3 h-3" /> Cancel</> : <><Plus className="w-3 h-3" /> New Goal</>}
        </button>
      </div>

      {/* Create form */}
      {open && (
        <div className="glass rounded-2xl p-5 space-y-3 slide-up border-violet-800/30">
          <p className="text-violet-400 text-xs font-semibold tracking-wide uppercase">New Goal</p>
          <input
            value={name} onChange={e => setName(e.target.value)}
            placeholder="Goal name  (e.g. Goa Trip, PS5, Emergency Fund)"
            className="w-full glass rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-violet-600/60 transition-colors"
          />
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 text-sm">₹</span>
              <input
                value={target} onChange={e => setTarget(e.target.value)}
                placeholder="Target amount" type="number"
                className="w-full glass rounded-xl pl-7 pr-4 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-violet-600/60 transition-colors"
              />
            </div>
            <div className="flex-1 relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-600 text-sm">₹</span>
              <input
                value={current} onChange={e => setCurrent(e.target.value)}
                placeholder="Already saved" type="number"
                className="w-full glass rounded-xl pl-7 pr-4 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-violet-600/60 transition-colors"
              />
            </div>
          </div>
          <input
            value={deadline} onChange={e => setDeadline(e.target.value)}
            type="date"
            className="w-full glass rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-violet-600/60 transition-colors"
          />
          <button
            onClick={handleCreate}
            disabled={!name || !target || loading}
            className="w-full bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white text-sm py-2.5 rounded-xl flex items-center justify-center gap-2 transition-colors font-semibold"
          >
            {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : "Save Goal"}
          </button>
        </div>
      )}

      {/* Empty state */}
      {goals.length === 0 && !open && (
        <div className="glass rounded-2xl p-10 text-center">
          <p className="text-4xl mb-3">🎯</p>
          <p className="text-white font-semibold">No goals yet</p>
          <p className="text-slate-500 text-sm mt-1">Set a savings target to track your progress</p>
        </div>
      )}

      {/* Goal cards */}
      {goals.map((g, i) => {
        const pct = g.target_amount > 0
          ? Math.min(100, Math.round((g.current_amount / g.target_amount) * 100))
          : 0;
        const daysLeft = g.deadline
          ? Math.ceil((new Date(g.deadline).getTime() - Date.now()) / 86400000)
          : null;
        const remaining = Math.max(0, g.target_amount - g.current_amount);

        return (
          <div
            key={g.id}
            className="glass rounded-2xl p-4 space-y-3 fade-up"
            style={{ animationDelay: `${i * 0.06}s` }}
          >
            {/* Top row */}
            <div className="flex items-center gap-3">
              <div className="relative flex-shrink-0">
                <GoalRing pct={pct} />
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-white font-bold text-xs">{pct}%</span>
                </div>
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-white font-semibold text-sm leading-tight truncate">{g.name}</p>
                {daysLeft !== null && (
                  <p className={`text-xs mt-0.5 font-medium ${
                    daysLeft < 0 ? "text-rose-400" : daysLeft < 30 ? "text-amber-400" : "text-slate-500"
                  }`}>
                    {daysLeft < 0 ? `${Math.abs(daysLeft)}d overdue` : `${daysLeft}d left`}
                  </p>
                )}
              </div>

              <button
                onClick={() => handleDelete(g.id)}
                disabled={deleting === g.id}
                className="text-slate-700 hover:text-rose-400 transition-colors p-1"
              >
                {deleting === g.id
                  ? <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  : <Trash2 className="w-3.5 h-3.5" />}
              </button>
            </div>

            {/* Progress bar */}
            <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-1000"
                style={{
                  width: `${pct}%`,
                  background: pct >= 80
                    ? "linear-gradient(90deg, #10b981, #34d399)"
                    : pct >= 40
                    ? "linear-gradient(90deg, #7c3aed, #a78bfa)"
                    : "linear-gradient(90deg, #d97706, #fbbf24)",
                }}
              />
            </div>

            {/* Amounts */}
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">
                <span className="text-white font-medium">₹{Math.round(g.current_amount).toLocaleString("en-IN")}</span>
                {" "}saved
              </span>
              <span className="text-slate-600">
                ₹{Math.round(remaining).toLocaleString("en-IN")} to go · <span className="text-slate-500">₹{Math.round(g.target_amount).toLocaleString("en-IN")}</span>
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
