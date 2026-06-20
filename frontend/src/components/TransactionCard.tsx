"use client";
import { useState } from "react";
import { gullakApi } from "@/lib/api";
import { CATEGORY_ICONS, CATEGORY_COLORS } from "@/lib/utils";

const REGRET_OPTIONS = [
  { value: "worth_it", label: "Worth it", icon: "✅", active: "text-emerald-400 border-emerald-700/80 bg-emerald-900/20" },
  { value: "neutral",  label: "Meh",      icon: "😐", active: "text-slate-300 border-slate-600 bg-slate-800/60" },
  { value: "regret",   label: "Regret",   icon: "😬", active: "text-rose-400 border-rose-700/80 bg-rose-900/20" },
];

const REGRET_DOT: Record<string, string> = {
  worth_it: "bg-emerald-500",
  neutral:  "bg-slate-500",
  regret:   "bg-rose-500",
};

const ALL_CATEGORIES = [
  "Food", "Groceries", "Health", "Transport", "Petrol",
  "Entertainment", "Subscriptions", "Clothing", "Education",
  "Stationery", "Tech / Devices", "Personal Care", "Utilities",
  "Finance", "P2P Transfer", "Other",
];

/** Converts ALL-CAPS raw merchant names to Title Case */
function readableName(name: string): string {
  if (!name) return name;
  const upper = name.replace(/[^a-zA-Z]/g, "");
  if (upper.length > 3 && upper === upper.toUpperCase()) {
    return name
      .toLowerCase()
      .replace(/(?:^|\s|_)\S/g, c => c.toUpperCase())
      .replace(/_/g, " ")
      .trim();
  }
  return name;
}

interface TransactionCardProps {
  tx: any;
  onUpdated: () => void;
}

export function TransactionCard({ tx, onUpdated }: TransactionCardProps) {
  const [expanded,    setExpanded]   = useState(false);
  const [verifying,   setVerifying]  = useState(false);
  const [marking,     setMarking]    = useState(false);
  const [saving,      setSaving]     = useState(false);
  const [savedBadge,  setSavedBadge] = useState<string | null>(null);
  const [applyAll,    setApplyAll]   = useState(true);
  const [displayCategory, setDisplayCategory] = useState<string>(tx.category);

  const isUnsure    = tx.category?.startsWith("Unsure: ");
  const isOther     = tx.category === "Other";
  const isLabelled  = !!tx.user_label;
  const needsVerify = isUnsure || isOther || tx.flag === "low_confidence";
  const suggestedCat = isUnsure ? tx.category.replace("Unsure: ", "") : null;
  const isCredit    = tx.transaction_type === "credit";
  const hasRegret   = !!tx.regret_status;

  const icon  = CATEGORY_ICONS[displayCategory?.replace("Unsure: ", "")] ?? "📦";
  const color = CATEGORY_COLORS[displayCategory?.replace("Unsure: ", "")] ?? "#64748b";

  const mark = async (status: string) => {
    setMarking(true);
    try { await gullakApi.markRegret(tx.id, status as any); onUpdated(); }
    finally { setMarking(false); }
  };

  const saveLabel = async (chosenCat: string) => {
    setSaving(true);
    try {
      const res = await gullakApi.labelTransaction(tx.id, chosenCat, applyAll);
      const similar = res.data?.similar_updated ?? 0;
      setDisplayCategory(chosenCat);
      setSavedBadge(similar > 1 ? `✓ ${chosenCat} · ${similar} updated` : `✓ Saved`);
      setVerifying(false);
      setExpanded(false);
      onUpdated();
      setTimeout(() => setSavedBadge(null), 3500);
    } finally { setSaving(false); }
  };

  return (
    <div
      className={`glass rounded-2xl overflow-hidden transition-all ${
        expanded ? "border-white/14" : "hover:border-white/10"
      }`}
    >
      {/* Confidence accent line */}
      {needsVerify && !isLabelled && (
        <div className="h-0.5 bg-gradient-to-r from-amber-500/70 to-transparent" />
      )}

      {/* ── Main row — tap to expand ── */}
      <button
        className="w-full text-left"
        onClick={() => { setExpanded(e => !e); setVerifying(false); }}
      >
        <div className="p-3.5 flex items-center gap-3">

          {/* Category icon */}
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center text-lg flex-shrink-0"
            style={{ background: `${color}18`, boxShadow: `0 0 0 1px ${color}28` }}
          >
            {icon}
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 min-w-0">
              <p className="text-white font-semibold text-sm leading-tight truncate">
                {readableName(tx.merchant_clean)}
              </p>
              {isLabelled && (
                <span className="text-violet-500 text-[8px] font-bold tracking-wide bg-violet-900/30 px-1.5 py-0.5 rounded-full flex-shrink-0">
                  ✎
                </span>
              )}
            </div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-slate-600 text-[10px]">{tx.date}</span>
              <span className="text-slate-700">·</span>
              <span
                className="text-[10px] font-medium truncate max-w-[100px]"
                style={{ color: isUnsure ? "#fbbf24" : isLabelled ? "#a78bfa" : "#64748b" }}
              >
                {displayCategory}
              </span>
            </div>
          </div>

          {/* Amount + indicators */}
          <div className="flex flex-col items-end gap-1 flex-shrink-0">
            <p className={`text-sm font-bold tabular-nums ${isCredit ? "text-emerald-400" : "text-white"}`}>
              {isCredit ? "+" : "−"}₹{Math.round(tx.amount).toLocaleString("en-IN")}
            </p>

            <div className="flex items-center gap-1.5">
              {/* Regret dot — shows status without taking up space */}
              {!isCredit && hasRegret && (
                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${REGRET_DOT[tx.regret_status] ?? "bg-slate-600"}`} />
              )}
              {/* Confidence warning */}
              {needsVerify && !isLabelled && (
                <span className="text-[9px] text-amber-500 font-medium">verify</span>
              )}
              {/* Saved badge */}
              {savedBadge && (
                <span className="text-[9px] text-violet-400 font-medium">{savedBadge}</span>
              )}
              {/* Expand chevron */}
              <span className={`text-slate-700 text-[10px] transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}>
                ▾
              </span>
            </div>
          </div>
        </div>
      </button>

      {/* ── Expanded panel ── */}
      {expanded && (
        <div className="border-t border-white/5 slide-up">

          {/* Category section */}
          {!verifying ? (
            <div className="px-3.5 py-2.5 flex items-center justify-between">
              <div>
                {needsVerify && !isLabelled && (
                  <p className="text-amber-400 text-xs font-medium mb-0.5">
                    {isUnsure ? `Is this ${suggestedCat}?` : "Category needs verification"}
                  </p>
                )}
                <p className="text-slate-500 text-[10px]">Category · tap to change</p>
              </div>
              <button
                onClick={() => setVerifying(true)}
                className={`text-xs px-3 py-1 rounded-lg border transition-all font-medium ${
                  needsVerify && !isLabelled
                    ? "text-amber-300 border-amber-700/60 bg-amber-900/15 hover:bg-amber-900/30"
                    : "text-slate-400 border-white/8 hover:text-white hover:border-white/16"
                }`}
              >
                {needsVerify && !isLabelled && suggestedCat ? `✓ ${suggestedCat}` : "✏️ Change"}
              </button>
            </div>
          ) : (
            <div className="px-3 py-3 space-y-2.5">
              <div className="flex items-center justify-between">
                <p className="text-xs text-violet-300 font-medium">Change category</p>
                <button onClick={() => setVerifying(false)} className="text-[10px] text-slate-600 hover:text-slate-300">✕ close</button>
              </div>

              {suggestedCat && (
                <button
                  disabled={saving}
                  onClick={() => saveLabel(suggestedCat)}
                  className="w-full text-xs bg-amber-700/25 hover:bg-amber-700/40 text-amber-200 border border-amber-700/60 rounded-xl py-1.5 font-semibold transition-all"
                >
                  ✓ Yes, it's {suggestedCat}
                </button>
              )}

              <div className="grid grid-cols-4 gap-1">
                {ALL_CATEGORIES.map(cat => (
                  <button
                    key={cat}
                    disabled={saving}
                    onClick={() => saveLabel(cat)}
                    className={`text-[9px] py-1.5 px-1 rounded-lg border transition-all flex flex-col items-center gap-0.5 ${
                      cat === displayCategory?.replace("Unsure: ", "")
                        ? "border-violet-500 text-white bg-violet-900/40"
                        : "border-white/6 text-slate-500 hover:border-violet-600/50 hover:text-white hover:bg-violet-900/20"
                    }`}
                  >
                    <span className="text-base">{CATEGORY_ICONS[cat] ?? "📦"}</span>
                    <span className="leading-tight text-center">{cat}</span>
                  </button>
                ))}
              </div>

              <label className="flex items-center gap-1.5 cursor-pointer select-none">
                <input type="checkbox" checked={applyAll} onChange={e => setApplyAll(e.target.checked)}
                  className="accent-violet-500 w-3 h-3 rounded" />
                <span className="text-[10px] text-slate-500">Apply to all similar merchants</span>
              </label>
            </div>
          )}

          {/* Regret section — only for debits, only when expanded */}
          {!isCredit && (
            <div className="flex border-t border-white/5">
              {REGRET_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  disabled={marking}
                  onClick={e => { e.stopPropagation(); mark(opt.value); }}
                  className={`flex-1 text-[10px] py-2.5 font-medium transition-all flex items-center justify-center gap-1 ${
                    tx.regret_status === opt.value
                      ? opt.active
                      : "text-slate-600 hover:text-slate-300"
                  }`}
                >
                  <span>{opt.icon}</span>
                  <span>{opt.label}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
