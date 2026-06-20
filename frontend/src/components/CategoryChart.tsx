"use client";
import { CATEGORY_COLORS, CATEGORY_ICONS, formatINR } from "@/lib/utils";
import { PieChart, Pie, Tooltip, ResponsiveContainer } from "recharts";

interface CategoryChartProps {
  transactions: any[];
}

export function CategoryChart({ transactions }: CategoryChartProps) {
  const debits = transactions.filter(t => t.transaction_type === "debit");
  const totals: Record<string, number> = {};
  debits.forEach(t => { totals[t.category] = (totals[t.category] ?? 0) + t.amount; });

  const data = Object.entries(totals)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([name, value]) => ({
      name,
      value: Math.round(value),
      fill: CATEGORY_COLORS[name] ?? "#4b5563",
    }));

  if (data.length === 0) return null;

  const total = data.reduce((s, d) => s + d.value, 0);

  return (
    <div className="glass rounded-2xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-white font-semibold text-sm">Spending Breakdown</p>
        <p className="text-slate-500 text-xs">{formatINR(total)} total</p>
      </div>

      <div className="flex gap-4 items-center">
        {/* Donut chart */}
        <div className="flex-shrink-0 relative">
          <ResponsiveContainer width={140} height={140}>
            <PieChart>
              <Pie
                data={data}
                cx="50%" cy="50%"
                innerRadius={42} outerRadius={64}
                paddingAngle={2}
                dataKey="value"
                strokeWidth={0}
              />

              <Tooltip
                contentStyle={{
                  background: "rgba(13,13,26,0.95)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: 12,
                  fontSize: 11,
                  backdropFilter: "blur(20px)",
                  padding: "8px 12px",
                }}
                formatter={(v: any) => [`₹${Number(v).toLocaleString("en-IN")}`, ""]}
                itemStyle={{ color: "#f1f5f9" }}
              />
            </PieChart>
          </ResponsiveContainer>
          {/* Center label */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="text-center">
              <p className="text-white font-bold text-xs">{data.length}</p>
              <p className="text-slate-600 text-[9px]">cats</p>
            </div>
          </div>
        </div>

        {/* Legend bars */}
        <div className="flex-1 space-y-2 min-w-0">
          {data.map(item => {
            const pct = total > 0 ? Math.round((item.value / total) * 100) : 0;
            const color = CATEGORY_COLORS[item.name] ?? "#4b5563";
            const icon = CATEGORY_ICONS[item.name] ?? "📦";
            return (
              <div key={item.name}>
                <div className="flex items-center justify-between text-[10px] mb-1 gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="text-xs flex-shrink-0">{icon}</span>
                    <span className="text-slate-300 truncate">{item.name}</span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-slate-500">{pct}%</span>
                    <span className="text-slate-400 font-medium">₹{item.value.toLocaleString("en-IN")}</span>
                  </div>
                </div>
                <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{ width: `${pct}%`, background: color, opacity: 0.85 }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
