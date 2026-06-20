import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatINR(amount: number): string {
  return `₹${Math.round(amount).toLocaleString("en-IN")}`;
}

export function getScoreColor(score: number) {
  if (score >= 75) return "text-emerald-400";
  if (score >= 50) return "text-amber-400";
  return "text-rose-400";
}

export function computeScores(transactions: any[]) {
  const debits = transactions.filter((t) => t.transaction_type === "debit");
  const total = debits.reduce((s, t) => s + t.amount, 0);
  const regretted = debits.filter((t) => t.regret_status === "regret").reduce((s, t) => s + t.amount, 0);
  const lateNight = debits.filter((t) => {
    const h = parseInt(t.time?.split(":")[0] ?? "12");
    return h >= 23 || h < 5;
  }).length;
  const regretRatio = total > 0 ? regretted / total : 0;
  const lateRatio = debits.length > 0 ? lateNight / debits.length : 0;
  const financialHealth = Math.round(Math.max(20, 100 - regretRatio * 60 - lateRatio * 40));
  const discipline = Math.round(Math.max(20, 100 - lateRatio * 80));
  const moodScore = Math.round(Math.max(20, 100 - regretRatio * 80));
  const uniqueDays = new Set(debits.map((t) => t.date)).size;
  const regretDays = new Set(debits.filter((t) => t.regret_status === "regret").map((t) => t.date)).size;
  const habitStreak = Math.max(1, uniqueDays - regretDays);
  const productivity = Math.round(Math.max(20, 100 - lateRatio * 50 - regretRatio * 30));
  return { financialHealth, discipline, moodScore, habitStreak, productivity };
}

export function getTodaySpend(transactions: any[]) {
  const today = new Date().toISOString().split("T")[0];
  return transactions
    .filter((t) => t.transaction_type === "debit" && t.date === today)
    .reduce((s, t) => s + t.amount, 0);
}

export function buildDailySummary(transactions: any[]): string {
  const today = new Date().toISOString().split("T")[0];
  const todayTx = transactions.filter((t) => t.transaction_type === "debit" && t.date === today);
  if (todayTx.length === 0) return "No spending logged today. Stay disciplined! 💪";
  const total = todayTx.reduce((s, t) => s + t.amount, 0);
  const lateNight = todayTx.filter((t) => {
    const h = parseInt(t.time?.split(":")[0] ?? "12");
    return h >= 23 || h < 5;
  }).length;
  const regret = todayTx.filter((t) => t.regret_status === "regret").length;
  if (lateNight > 0) return `Late-night cravings detected — ₹${Math.round(total)} spent, ${lateNight} late-night transactions. 🌙`;
  if (regret > 0) return `You marked ${regret} purchase(s) as regret today. ₹${Math.round(total)} total spent.`;
  return `You stayed disciplined today. ₹${Math.round(total)} spent across ${todayTx.length} transactions. ✨`;
}

export const CATEGORY_ICONS: Record<string, string> = {
  Food: "🍕", Groceries: "🛒", Transport: "🚕", Entertainment: "🎬",
  Health: "💊", "Health & Fitness": "🏋️", Subscriptions: "📱", Shopping: "🛍️",
  Education: "📚", "Tech / Devices": "💻", Clothing: "👕", Petrol: "⛽",
  Stationery: "📎", "P2P Transfer": "🤝", "Personal Care": "🪥",
  Utilities: "💡", Finance: "📈",
  Other: "📦", "Daily Notebook": "📓",
};

export const CATEGORY_COLORS: Record<string, string> = {
  Food: "#f59e0b", Groceries: "#10b981", Transport: "#3b82f6",
  Entertainment: "#8b5cf6", Health: "#ec4899", "Health & Fitness": "#ec4899",
  Subscriptions: "#06b6d4", Shopping: "#f97316", Education: "#84cc16",
  "Tech / Devices": "#6366f1", Clothing: "#a855f7", Petrol: "#14b8a6",
  Stationery: "#0ea5e9", "P2P Transfer": "#78716c", "Personal Care": "#f472b6",
  Utilities: "#fbbf24", Finance: "#22d3ee",
  Other: "#64748b", "Daily Notebook": "#059669",
};

