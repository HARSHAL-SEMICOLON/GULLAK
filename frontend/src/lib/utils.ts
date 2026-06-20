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
  const debits = transactions.filter(t => t.transaction_type === "debit");
  const n = debits.length;

  // Return neutral defaults when no data
  if (n === 0) return { financialHealth: 72, discipline: 68, moodScore: 75, habitStreak: 0, productivity: 70 };

  const totalAmount = debits.reduce((s, t) => s + t.amount, 0);

  // Count-based ratios (amount-based is always near-zero and meaningless)
  const regretCount   = debits.filter(t => t.regret_status === "regret").length;
  const worthItCount  = debits.filter(t => t.regret_status === "worth_it").length;
  const lateNight     = debits.filter(t => { const h = parseInt(t.time?.split(":")[0] ?? "12"); return h >= 22 || h < 5; }).length;
  const uncategorized = debits.filter(t => t.category === "Other" || t.category?.startsWith("Unsure")).length;

  // Food delivery spend (Swiggy / Zomato)
  const foodDeliveryAmt = debits
    .filter(t => t.category === "Food" &&
      /(swiggy|zomato|dunzo|blinkit)/i.test(t.merchant_clean))
    .reduce((s, t) => s + t.amount, 0);

  // "Useful" categories: groceries, health, education, utilities, transport
  const usefulAmt = debits
    .filter(t => ["Groceries","Health","Education","Utilities","Transport"].includes(t.category))
    .reduce((s, t) => s + t.amount, 0);

  const regretR        = regretCount  / n;                          // 5 regrets / 724 tx = 0.007
  const worthItR       = worthItCount / n;
  const lateR          = lateNight    / n;                          // 12 / 724 = 0.017
  const uncatR         = uncategorized / n;                         // 100 / 724 = 0.138
  const foodDeliveryR  = totalAmount > 0 ? foodDeliveryAmt / totalAmount : 0;
  const usefulR        = totalAmount > 0 ? usefulAmt / totalAmount : 0;

  // ── Financial Health (50-95) ──────────────────────────────────────────────
  // Penalise: regret transactions, uncategorized clutter, food delivery overuse
  // Reward:   worth-it tagging, useful spending (groceries, health, education)
  const financialHealth = clamp(
    78
    - regretR   * 350    // 5% regret count → -17.5
    + worthItR  * 120    // 10% worth-it    → +12
    - uncatR    * 55     // 15% uncategorized → -8.25
    - foodDeliveryR * 60 // 10% food delivery spend → -6
    + usefulR   * 40,    // 20% useful spend → +8
    40, 95
  );

  // ── Discipline (35-95) ────────────────────────────────────────────────────
  // Late-night spending and regret count both hurt discipline
  const discipline = clamp(
    82
    - lateR   * 550    // 2% late-night → -11
    - regretR * 280    // 1% regret     → -2.8
    + worthItR * 80,
    35, 95
  );

  // ── Mood Score (30-95) ───────────────────────────────────────────────────
  // Directly tracks how you feel about your purchases
  const moodScore = clamp(
    72
    - regretR  * 500   // even small regret % tanks mood
    + worthItR * 200,  // worth-it tagging is a strong positive signal
    30, 95
  );

  // ── Habit Streak (days without regret) ───────────────────────────────────
  const spendDays  = new Set(debits.map(t => t.date)).size;
  const regretDays = new Set(debits.filter(t => t.regret_status === "regret").map(t => t.date)).size;
  const habitStreak = Math.max(0, spendDays - regretDays);

  // ── Productivity (40-95) ─────────────────────────────────────────────────
  // Rewards spending on "useful" categories (groceries, health, education)
  const productivity = clamp(
    68
    + usefulR  * 90    // 20% useful → +18
    - lateR    * 280   // late night hurts focus
    - regretR  * 180,
    40, 95
  );

  return {
    financialHealth: Math.round(financialHealth),
    discipline:      Math.round(discipline),
    moodScore:       Math.round(moodScore),
    habitStreak,
    productivity:    Math.round(productivity),
  };
}

function clamp(v: number, min: number, max: number) {
  return Math.min(max, Math.max(min, v));
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

