"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { gullakApi } from "@/lib/api";
import { computeScores, getTodaySpend, formatINR } from "@/lib/utils";
import { ScoreRing } from "@/components/ScoreRing";
import { DailyNotebook } from "@/components/DailyNotebook";
import { TransactionCard } from "@/components/TransactionCard";
import { CategoryChart } from "@/components/CategoryChart";
import { SpendHeatmap } from "@/components/SpendHeatmap";
import { InsightsPanel } from "@/components/InsightsPanel";
import { GoalsPanel } from "@/components/GoalsPanel";
import { ProfileManager } from "@/components/ProfileManager";
import { OtherClusters } from "@/components/OtherClusters";
import { Upload, RefreshCw, ChevronDown, Search, SlidersHorizontal, Plus, X } from "lucide-react";

type Tab = "home" | "transactions" | "analytics" | "insights" | "goals";

interface Profile {
  id: string;
  name: string;
  avatar_emoji: string;
}

function timeGreeting() {
  const h = new Date().getHours();
  if (h < 5)  return "Late night grind";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  if (h < 21) return "Good evening";
  return "Late night grind";
}

export default function GullakApp() {
  const [profiles, setProfiles]               = useState<Profile[]>([]);
  const [activeProfileId, setActiveProfileId] = useState<string>("default");
  const [showProfileMgr, setShowProfileMgr]   = useState(false);

  const [transactions, setTransactions] = useState<any[]>([]);
  const [insights, setInsights]         = useState<any>(null);
  const [goals, setGoals]               = useState<any[]>([]);

  const [tab, setTab]               = useState<Tab>("home");
  const [uploading, setUploading]   = useState(false);
  const [loading, setLoading]       = useState(true);
  const [file, setFile]             = useState<File | null>(null);
  const [searchQ, setSearchQ]       = useState("");
  const [catFilter, setCatFilter]   = useState("All");
  const [showFilter, setShowFilter] = useState(false);
  const [showFAB, setShowFAB]       = useState(false); // quick-log drawer

  // Always dark
  useEffect(() => { document.documentElement.classList.add("dark"); }, []);

  const loadProfiles = useCallback(async () => {
    try {
      const res = await gullakApi.getProfiles();
      const data: Profile[] = res.data;
      setProfiles(data);
      const stored = typeof window !== "undefined" ? localStorage.getItem("gullak_profile") : null;
      const valid = data.find(p => p.id === stored);
      if (valid) setActiveProfileId(valid.id);
      else if (data.length > 0) setActiveProfileId(data[0].id);
    } catch { /* backend not ready */ }
  }, []);

  useEffect(() => { loadProfiles(); }, [loadProfiles]);
  useEffect(() => {
    if (typeof window !== "undefined") localStorage.setItem("gullak_profile", activeProfileId);
  }, [activeProfileId]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const txRes = await gullakApi.getTransactions(activeProfileId);
      setTransactions(txRes.data);
      if (txRes.data.length > 0) {
        const [insRes, goalRes] = await Promise.all([
          gullakApi.getInsights(activeProfileId),
          gullakApi.getGoals(activeProfileId),
        ]);
        setInsights(insRes.data);
        setGoals(goalRes.data);
      } else {
        setInsights(null);
        setGoals([]);
      }
    } catch (e) {
      console.error("Backend not reachable", e);
    } finally {
      setLoading(false);
    }
  }, [activeProfileId]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      await gullakApi.uploadStatement(file, activeProfileId);
      await fetchAll();
      setFile(null);
    } catch {
      alert("Upload failed. Is the backend running on :8001?");
    } finally {
      setUploading(false);
    }
  };

  const handleProfileSwitch = (id: string) => {
    setActiveProfileId(id);
    setTransactions([]);
    setInsights(null);
    setGoals([]);
    setSearchQ("");
    setCatFilter("All");
    setTab("home");
  };

  const scores      = useMemo(() => computeScores(transactions), [transactions]);
  const todaySpend  = useMemo(() => getTodaySpend(transactions), [transactions]);
  const totalSpend  = useMemo(
    () => transactions.filter(t => t.transaction_type === "debit").reduce((s, t) => s + t.amount, 0),
    [transactions]
  );
  const debitCount  = useMemo(() => transactions.filter(t => t.transaction_type === "debit").length, [transactions]);
  const spendTotal  = useMemo(() => filteredTxAll().reduce((s, t) => s + (t.transaction_type === "debit" ? t.amount : 0), 0), [transactions, searchQ, catFilter]); // eslint-disable-line

  function filteredTxAll() {
    return transactions.filter(t => {
      const matchQ = t.merchant_clean.toLowerCase().includes(searchQ.toLowerCase());
      const matchC = catFilter === "All" || t.category === catFilter;
      return matchQ && matchC;
    });
  }

  const activeProfile = profiles.find(p => p.id === activeProfileId);
  const categories    = ["All", ...Array.from(new Set(transactions.map(t => t.category)))];
  const filteredTx    = filteredTxAll().slice(0, 100);

  const personaEmoji = (p?: string) =>
    p === "Foodie" ? "🍕" : p === "Shopper" ? "🛍️" : p === "Commuter" ? "🚕" : "⚖️";

  const TABS: { id: Tab; label: string; icon: string }[] = [
    { id: "home",         label: "Home",   icon: "🏠" },
    { id: "transactions", label: "Spends", icon: "💳" },
    { id: "analytics",   label: "Stats",  icon: "📊" },
    { id: "insights",    label: "AI",     icon: "✨" },
    { id: "goals",       label: "Goals",  icon: "🎯" },
  ];

  return (
    <div className="min-h-screen bg-[#080810] text-slate-100 flex flex-col">

      {/* ── HEADER ── */}
      <header className="sticky top-0 z-40 border-b border-white/5 bg-[#080810]/85 backdrop-blur-xl">
        <div className="max-w-lg mx-auto px-4 py-3 flex items-center justify-between gap-3">

          {/* Logo */}
          <div className="flex items-center gap-2.5 flex-shrink-0">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-violet-500 to-emerald-500 flex items-center justify-center text-sm font-black text-white shadow-lg select-none">
              G
            </div>
            <div className="hidden sm:block leading-none">
              <p className="text-white font-bold text-sm">Gullak</p>
              <p className="text-slate-600 text-[9px] tracking-widest uppercase mt-0.5">AI Finance</p>
            </div>
          </div>

          {/* Profile switcher */}
          <button
            onClick={() => setShowProfileMgr(true)}
            className="flex items-center gap-2 px-3 py-1.5 glass rounded-xl hover:border-white/14 transition-all group"
          >
            <span className="text-base">{activeProfile?.avatar_emoji ?? "👤"}</span>
            <span className="text-white text-sm font-medium max-w-[110px] truncate">
              {activeProfile?.name ?? "Loading…"}
            </span>
            <ChevronDown className="w-3 h-3 text-slate-500 group-hover:text-violet-400 transition-colors" />
          </button>

          {/* Upload CTA */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <label className="cursor-pointer">
              <input type="file" accept=".pdf,.csv" className="hidden"
                onChange={e => setFile(e.target.files?.[0] ?? null)} />
              <span className={`text-xs border px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-all whitespace-nowrap ${
                file
                  ? "text-violet-300 border-violet-600/70 bg-violet-900/20"
                  : "text-slate-400 border-white/10 hover:border-white/20 hover:text-white bg-white/4"
              }`}>
                <Upload className="w-3 h-3 flex-shrink-0" />
                <span className="truncate max-w-[70px]">
                  {file ? file.name : "PDF"}
                </span>
              </span>
            </label>

            {file && (
              <button onClick={handleUpload} disabled={uploading}
                className="text-xs bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-colors font-semibold">
                {uploading ? <RefreshCw className="w-3 h-3 animate-spin" /> : "Analyze →"}
              </button>
            )}
          </div>
        </div>
      </header>

      {/* ── MAIN ── */}
      <main className="flex-1 max-w-lg mx-auto w-full nav-safe-pb">

        {/* ────────── HOME ────────── */}
        {tab === "home" && (
          <div className="px-4 pt-4 space-y-4">

            {/* Hero balance card */}
            <div className="mesh-hero rounded-3xl p-6 fade-up">
              <p className="text-slate-500 text-xs font-medium">
                {timeGreeting()}{activeProfile ? `, ${activeProfile.name}` : ""}
              </p>

              <div className="mt-4">
                <p className="text-slate-600 text-[10px] font-semibold tracking-widest uppercase">Total Tracked</p>
                <p className="gradient-text text-5xl font-black mt-1 leading-none tracking-tight">
                  {formatINR(totalSpend)}
                </p>
              </div>

              <div className="mt-5 flex items-stretch gap-4">
                <div>
                  <p className="text-slate-600 text-[10px] tracking-widest uppercase">Today</p>
                  <p className={`font-bold text-xl mt-0.5 ${todaySpend > 0 ? "text-rose-400" : "text-slate-500"}`}>
                    {formatINR(todaySpend)}
                  </p>
                </div>
                <div className="w-px bg-white/8" />
                <div>
                  <p className="text-slate-600 text-[10px] tracking-widest uppercase">Debits</p>
                  <p className="text-white font-bold text-xl mt-0.5">{debitCount}</p>
                </div>
                {insights?.data_for_llm?.profile && (
                  <>
                    <div className="w-px bg-white/8" />
                    <div>
                      <p className="text-slate-600 text-[10px] tracking-widest uppercase">Persona</p>
                      <p className="text-xl mt-0.5">{personaEmoji(insights.data_for_llm.profile)}</p>
                    </div>
                  </>
                )}
              </div>

              {uploading && (
                <div className="mt-4 h-0.5 bg-white/5 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-violet-500 to-emerald-500 w-2/3 rounded-full animate-pulse" />
                </div>
              )}
            </div>

            {/* Wellness scores */}
            {transactions.length > 0 && (
              <div className="fade-up-1">
                <p className="text-slate-600 text-[10px] font-semibold tracking-widest uppercase px-1 mb-3">Wellness</p>
                <div className="flex gap-3 overflow-x-auto pb-2 custom-scroll -mx-4 px-4">
                  <ScoreRing score={scores.financialHealth} label="Health"     icon="💰" />
                  <ScoreRing score={scores.discipline}      label="Discipline" icon="🧠" />
                  <ScoreRing score={scores.moodScore}       label="Mood"       icon="😊" />
                  <ScoreRing score={scores.productivity}    label="Focus"      icon="⚡" />
                  <div className="flex-shrink-0 flex flex-col items-center gap-1.5">
                    <div className="w-[76px] h-[76px] glass rounded-2xl flex flex-col items-center justify-center gap-0.5">
                      <span className="text-xl">🔥</span>
                      <span className="text-amber-400 font-bold text-base">{scores.habitStreak}d</span>
                    </div>
                    <span className="text-[9px] text-slate-600 uppercase tracking-wide">Streak</span>
                  </div>
                </div>
              </div>
            )}

            {/* Persona + AI insight 2-col */}
            {insights?.data_for_llm && (
              <div className="grid grid-cols-2 gap-3 fade-up-2">
                <div className="glass rounded-2xl p-4 flex flex-col gap-1 min-h-[120px]">
                  <p className="text-slate-600 text-[10px] font-semibold tracking-widest uppercase">Persona</p>
                  <p className="text-white font-bold text-xl mt-1">{insights.data_for_llm.profile}</p>
                  <p className="text-3xl mt-auto">{personaEmoji(insights.data_for_llm.profile)}</p>
                </div>

                {insights?.insight ? (
                  <button
                    onClick={() => setTab("insights")}
                    className="glass rounded-2xl p-4 border-l-2 border-l-violet-500/70 flex flex-col gap-1 min-h-[120px] text-left hover:border-white/14 transition-all"
                  >
                    <p className="text-violet-400 text-[10px] font-semibold tracking-widest uppercase">AI Insight ›</p>
                    <p className="text-white text-xs font-semibold leading-snug mt-1 line-clamp-2">
                      {insights.insight.title}
                    </p>
                    <p className="text-slate-500 text-[10px] leading-relaxed mt-1 line-clamp-3">
                      {insights.insight.body}
                    </p>
                  </button>
                ) : (
                  <div className="glass rounded-2xl p-4 flex flex-col items-center justify-center gap-2 min-h-[120px]">
                    <p className="text-2xl">🧠</p>
                    <p className="text-slate-600 text-[10px] text-center leading-relaxed">
                      Set <span className="text-violet-400 font-mono text-[9px]">GROQ_API_KEY</span> for AI insights
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Empty / first-run state */}
            {transactions.length === 0 && !loading && (
              <div className="glass rounded-3xl p-8 text-center fade-up-2 space-y-4">
                <p className="text-5xl">📂</p>
                <div>
                  <p className="text-white font-bold text-base">Import your first statement</p>
                  <p className="text-slate-500 text-sm mt-1">Upload a GPay PDF — we'll categorize everything automatically</p>
                </div>
                <label className="cursor-pointer inline-flex items-center gap-2 bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors">
                  <Upload className="w-4 h-4" />
                  <span>Choose GPay PDF</span>
                  <input type="file" accept=".pdf" className="hidden"
                    onChange={e => setFile(e.target.files?.[0] ?? null)} />
                </label>
                {file && (
                  <div className="flex items-center justify-center gap-2">
                    <p className="text-slate-400 text-sm truncate max-w-[180px]">{file.name}</p>
                    <button onClick={handleUpload} disabled={uploading}
                      className="text-xs bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5">
                      {uploading ? <RefreshCw className="w-3 h-3 animate-spin" /> : "Analyze →"}
                    </button>
                  </div>
                )}
              </div>
            )}

            {loading && transactions.length === 0 && (
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => <div key={i} className="h-24 rounded-2xl shimmer" />)}
              </div>
            )}

            {/* Daily log */}
            <div className="fade-up-3">
              <DailyNotebook onLogged={fetchAll} profileId={activeProfileId} />
            </div>

            {/* Category chart */}
            {transactions.length > 0 && (
              <div className="fade-up-4">
                <CategoryChart transactions={transactions} />
              </div>
            )}
          </div>
        )}

        {/* ────────── SPENDS ────────── */}
        {tab === "transactions" && (
          <div className="px-4 pt-4 space-y-3">

            {/* Stats bar */}
            {transactions.length > 0 && (
              <div className="glass rounded-2xl px-4 py-3 flex items-center justify-between fade-up">
                <div>
                  <p className="text-white font-bold text-lg tabular-nums">
                    {filteredTx.length === transactions.length
                      ? debitCount
                      : `${filteredTx.filter(t => t.transaction_type === "debit").length}`}
                    <span className="text-slate-600 text-sm font-normal"> debits</span>
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-rose-400 font-bold text-lg tabular-nums">
                    −{formatINR(filteredTx.filter(t => t.transaction_type === "debit").reduce((s, t) => s + t.amount, 0))}
                  </p>
                  {catFilter !== "All" && (
                    <p className="text-slate-600 text-[10px]">filtered: {catFilter}</p>
                  )}
                </div>
              </div>
            )}

            {/* Search + filter */}
            <div className="flex gap-2 fade-up">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-600" />
                <input
                  placeholder="Search merchant…"
                  value={searchQ}
                  onChange={e => setSearchQ(e.target.value)}
                  className="w-full glass rounded-xl pl-9 pr-4 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-violet-600/60 transition-colors"
                />
              </div>
              <button
                onClick={() => setShowFilter(!showFilter)}
                className={`w-10 h-10 glass rounded-xl flex items-center justify-center transition-all flex-shrink-0 ${
                  catFilter !== "All" ? "border-violet-600/60 text-violet-400" : "text-slate-500 hover:text-white"
                }`}
              >
                <SlidersHorizontal className="w-4 h-4" />
              </button>
            </div>

            {showFilter && (
              <div className="flex flex-wrap gap-1.5 fade-up">
                {categories.map(c => (
                  <button key={c} onClick={() => setCatFilter(c)}
                    className={`text-xs px-3 py-1 rounded-full border transition-all ${
                      catFilter === c
                        ? "bg-violet-600 border-violet-500 text-white"
                        : "glass text-slate-400 hover:text-white hover:border-white/16"
                    }`}>
                    {c}
                  </button>
                ))}
              </div>
            )}

            <OtherClusters profileId={activeProfileId} onLabelled={fetchAll} />

            {loading && (
              <div className="space-y-2">
                {[...Array(5)].map((_, i) => <div key={i} className="h-16 rounded-xl shimmer" />)}
              </div>
            )}

            <div className="space-y-2 custom-scroll overflow-y-auto max-h-[calc(100dvh-260px)] pr-0.5">
              {filteredTx.length === 0 && !loading && (
                <div className="text-center text-slate-600 py-16">
                  <p className="text-3xl mb-3">🔍</p>
                  <p className="text-sm">No transactions found</p>
                  {searchQ && <button onClick={() => setSearchQ("")} className="mt-2 text-violet-400 text-xs">Clear search</button>}
                </div>
              )}
              {filteredTx.map((tx, i) => (
                <div key={tx.id} style={{ animationDelay: `${Math.min(i * 0.025, 0.25)}s` }} className="fade-up">
                  <TransactionCard tx={tx} onUpdated={fetchAll} />
                </div>
              ))}
              {filteredTx.length >= 100 && (
                <p className="text-center text-slate-700 text-xs py-4">Showing first 100 — use search to narrow down</p>
              )}
            </div>
          </div>
        )}

        {/* ────────── ANALYTICS ────────── */}
        {tab === "analytics" && (
          <div className="px-4 pt-4 space-y-4">
            {transactions.length === 0 ? (
              <div className="text-center py-20 text-slate-600">
                <p className="text-4xl mb-3">📊</p>
                <p>Import a statement to see analytics</p>
              </div>
            ) : (
              <>
                <CategoryChart transactions={transactions} />
                <SpendHeatmap transactions={transactions} />
              </>
            )}
          </div>
        )}

        {/* ────────── AI INSIGHTS ────────── */}
        {tab === "insights" && (
          <div className="px-4 pt-4">
            {insights ? (
              <InsightsPanel insights={insights} />
            ) : (
              <div className="text-center py-20 fade-up">
                <p className="text-5xl mb-4">🧠</p>
                <p className="text-white font-semibold">No data yet</p>
                <p className="text-slate-500 text-sm mt-1">Import a statement to unlock AI insights</p>
              </div>
            )}
          </div>
        )}

        {/* ────────── GOALS ────────── */}
        {tab === "goals" && (
          <div className="px-4 pt-4">
            <GoalsPanel goals={goals} profileId={activeProfileId} onRefresh={fetchAll} />
          </div>
        )}
      </main>

      {/* ── FLOATING QUICK-LOG BUTTON ── */}
      {tab !== "home" && (
        <div className="fixed bottom-20 right-4 z-50 flex flex-col items-end gap-2">
          {showFAB && (
            <div className="glass-strong rounded-2xl p-4 w-72 slide-up shadow-xl">
              <div className="flex items-center justify-between mb-3">
                <p className="text-white font-semibold text-sm">Quick Log</p>
                <button onClick={() => setShowFAB(false)} className="text-slate-500 hover:text-white transition-colors">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <DailyNotebook onLogged={() => { fetchAll(); setShowFAB(false); }} profileId={activeProfileId} />
            </div>
          )}
          <button
            onClick={() => setShowFAB(f => !f)}
            className={`w-12 h-12 rounded-2xl flex items-center justify-center shadow-xl transition-all ${
              showFAB
                ? "bg-slate-700 text-white rotate-45"
                : "bg-violet-600 hover:bg-violet-500 text-white glow-violet"
            }`}
          >
            <Plus className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* ── BOTTOM NAV ── */}
      <nav className="fixed bottom-0 left-0 right-0 z-40 bg-[#080810]/90 backdrop-blur-2xl border-t border-white/5">
        <div className="max-w-lg mx-auto flex">
          {TABS.map(t => {
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => { setTab(t.id); setShowFAB(false); }}
                className="flex-1 py-3.5 flex flex-col items-center gap-0.5 transition-all relative"
              >
                {active && (
                  <span className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-0.5 bg-gradient-to-r from-violet-500 to-emerald-500 rounded-full" />
                )}
                <span className={`text-xl leading-none transition-transform duration-200 ${active ? "scale-110" : "scale-95 opacity-35"}`}>
                  {t.icon}
                </span>
                <span className={`text-[9px] font-semibold tracking-wider mt-0.5 transition-colors ${
                  active ? "text-violet-400" : "text-slate-700"
                }`}>
                  {t.label.toUpperCase()}
                </span>
              </button>
            );
          })}
        </div>
      </nav>

      {/* ── PROFILE MANAGER ── */}
      {showProfileMgr && (
        <ProfileManager
          currentProfileId={activeProfileId}
          onProfileSwitch={handleProfileSwitch}
          onClose={() => { setShowProfileMgr(false); loadProfiles(); fetchAll(); }}
        />
      )}
    </div>
  );
}
