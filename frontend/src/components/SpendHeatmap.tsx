"use client";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

interface SpendHeatmapProps {
  transactions: any[];
}

export function SpendHeatmap({ transactions }: SpendHeatmapProps) {
  // 24-hour spend heatmap
  const hourly: number[] = Array(24).fill(0);
  transactions
    .filter((t) => t.transaction_type === "debit")
    .forEach((t) => {
      const h = parseInt(t.time?.split(":")[0] ?? "12");
      hourly[h] += t.amount;
    });

  const data = hourly.map((amount, hour) => ({
    hour: `${hour.toString().padStart(2, "0")}:00`,
    amount: Math.round(amount),
    fill: hour >= 23 || hour < 5 ? "#f87171" : hour >= 12 && hour < 18 ? "#10b981" : "#60a5fa",
  }));

  // Weekly spend trend (group by date)
  const dailyMap: Record<string, number> = {};
  transactions
    .filter((t) => t.transaction_type === "debit")
    .forEach((t) => {
      dailyMap[t.date] = (dailyMap[t.date] ?? 0) + t.amount;
    });

  const weeklyData = Object.entries(dailyMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-30)
    .map(([date, amount]) => ({
      date: date.slice(5), // MM-DD
      amount: Math.round(amount),
    }));

  return (
    <div className="space-y-6">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
        <h3 className="text-white font-semibold mb-1">Hourly Spending Heatmap</h3>
        <p className="text-slate-500 text-xs mb-4">
          <span className="text-rose-400">■</span> Late night &nbsp;
          <span className="text-blue-400">■</span> Morning &nbsp;
          <span className="text-emerald-400">■</span> Afternoon
        </p>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={data} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="#1e293b" />
            <XAxis
              dataKey="hour"
              tick={{ fill: "#475569", fontSize: 9 }}
              tickLine={false}
              interval={3}
            />
            <YAxis tick={{ fill: "#475569", fontSize: 9 }} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 12 }}
              formatter={(v: any) => [`₹${Number(v).toLocaleString("en-IN")}`, "Spent"]}
            />
            <Bar dataKey="amount" radius={[3, 3, 0, 0]} fill="#60a5fa" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {weeklyData.length > 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
          <h3 className="text-white font-semibold mb-4">30-Day Spending Trend</h3>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={weeklyData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: "#475569", fontSize: 9 }} tickLine={false} interval={4} />
              <YAxis tick={{ fill: "#475569", fontSize: 9 }} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 12 }}
                formatter={(v: any) => [`₹${Number(v).toLocaleString("en-IN")}`, "Spent"]}
              />
              <Bar dataKey="amount" fill="#10b981" radius={[3, 3, 0, 0]} opacity={0.85} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
