"use client";

interface InsightsPanelProps {
  insights: any;
}

function AIInsightCard({ insight }: { insight: any }) {
  if (!insight) return null;
  const toneStyles: Record<string, string> = {
    supportive: "from-violet-600/15 to-transparent border-violet-700/40",
    nudge:      "from-amber-600/12 to-transparent border-amber-700/40",
    warning:    "from-rose-600/15 to-transparent border-rose-700/40",
    celebrate:  "from-emerald-600/15 to-transparent border-emerald-700/40",
  };
  const toneLabel: Record<string, { color: string; dot: string }> = {
    supportive: { color: "text-violet-400",  dot: "bg-violet-500" },
    nudge:      { color: "text-amber-400",   dot: "bg-amber-500" },
    warning:    { color: "text-rose-400",    dot: "bg-rose-500" },
    celebrate:  { color: "text-emerald-400", dot: "bg-emerald-500" },
  };
  const style = toneStyles[insight.tone] ?? toneStyles.supportive;
  const label = toneLabel[insight.tone]  ?? toneLabel.supportive;

  return (
    <div className={`rounded-2xl p-5 space-y-3 bg-gradient-to-br ${style} border`}>
      <div className="flex items-center gap-2">
        <span className={`w-1.5 h-1.5 rounded-full ${label.dot} pulse-dot`} />
        <span className={`text-[10px] font-semibold tracking-widest uppercase ${label.color}`}>
          AI Insight · Groq llama-3.3-70b
        </span>
      </div>
      <p className="text-white font-bold text-base leading-snug">{insight.title}</p>
      <p className="text-slate-300 text-sm leading-relaxed">{insight.body}</p>
      {insight.action && (
        <div className="flex items-start gap-2.5 bg-white/4 rounded-xl p-3 border border-white/6">
          <span className="text-base flex-shrink-0 mt-0.5">💡</span>
          <p className={`text-sm font-medium leading-snug ${label.color}`}>{insight.action}</p>
        </div>
      )}
    </div>
  );
}

function WastefulAlert({ data }: { data: any }) {
  if (!data?.found) return null;
  return (
    <div className="glass rounded-2xl p-4 border-l-2 border-l-amber-500/70">
      <div className="flex items-start gap-3">
        <span className="text-2xl flex-shrink-0">🚨</span>
        <div>
          <p className="text-amber-300 font-semibold text-sm">Faltu Kharcha Alert</p>
          <p className="text-slate-400 text-xs mt-1 leading-relaxed">
            You order food delivery <span className="text-white font-semibold">{data.avg_weekly_food_orders}×/week</span> on
            average — ₹{data.total_food_delivery_spent?.toLocaleString("en-IN")} total.
            Cooking just 2 meals/week saves ₹1,200+ monthly.
          </p>
        </div>
      </div>
    </div>
  );
}

function SubscriptionLeaks({ subs }: { subs: any[] }) {
  if (!subs?.length) return null;
  return (
    <div className="glass rounded-2xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-white font-semibold text-sm flex items-center gap-2">
          <span>📱</span> Subscription Leaks
        </p>
        <span className="text-slate-600 text-xs">{subs.length} detected</span>
      </div>
      {subs.slice(0, 5).map((s, i) => (
        <div key={i} className="flex items-center justify-between py-1 border-t border-white/4 first:border-0 first:pt-0">
          <div>
            <p className="text-slate-200 text-sm font-medium">{s.merchant}</p>
            <p className="text-slate-600 text-xs mt-0.5">Recurring · {s.occurrences}× detected</p>
          </div>
          <div className="text-right">
            <p className="text-rose-400 font-bold text-sm">₹{Math.round(s.amount).toLocaleString("en-IN")}</p>
            <p className="text-slate-600 text-[10px]">per cycle</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function RegretSummary({ data }: { data: any }) {
  if (!data?.count) return null;
  return (
    <div className="glass rounded-2xl p-4 border-l-2 border-l-rose-500/70">
      <div className="flex items-center justify-between mb-2">
        <p className="text-rose-300 font-semibold text-sm flex items-center gap-2">
          <span>😬</span> Regret Spending
        </p>
        <span className="text-rose-400 font-bold text-sm">₹{Math.round(data.amount).toLocaleString("en-IN")}</span>
      </div>
      <p className="text-slate-400 text-xs leading-relaxed">
        You've flagged <span className="text-white font-semibold">{data.count} purchase{data.count !== 1 ? "s" : ""}</span> as
        regret. These are draining your peace of mind and your wallet.
      </p>
      <div className="mt-3 h-1 bg-white/5 rounded-full overflow-hidden">
        <div className="h-full bg-gradient-to-r from-rose-600 to-rose-400 rounded-full" style={{ width: "100%" }} />
      </div>
    </div>
  );
}

export function InsightsPanel({ insights }: InsightsPanelProps) {
  if (!insights) return null;
  const d = insights.data_for_llm;

  return (
    <div className="space-y-4">
      <AIInsightCard insight={insights.insight} />
      <WastefulAlert data={d?.wasteful_spending} />
      <RegretSummary data={d?.regret_tracking} />
      <SubscriptionLeaks subs={d?.subscriptions_detected} />

      {/* No Groq key fallback notice */}
      {!insights.insight?.tone && (
        <div className="glass rounded-2xl p-4 text-center">
          <p className="text-slate-600 text-xs">
            Set <span className="text-violet-400 font-mono">GROQ_API_KEY</span> to get personalized AI insights
          </p>
        </div>
      )}
    </div>
  );
}
