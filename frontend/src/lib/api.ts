import axios from "axios";

const BASE = "http://127.0.0.1:8001";
export const api = axios.create({ baseURL: BASE });

// ── Profile-aware API client ─────────────────────────────────────────────────
// All calls that are profile-scoped accept a profileId param.
// Pass it as a query string: ?profile_id=xxx

export const gullakApi = {
  // ── Profiles
  getProfiles: () =>
    api.get("/profiles"),
  createProfile: (name: string, avatar_emoji: string) =>
    api.post("/profiles", { name, avatar_emoji }),
  deleteProfile: (profileId: string) =>
    api.delete(`/profiles/${profileId}`),
  getProfileStats: (profileId: string) =>
    api.get(`/profiles/${profileId}/stats`),

  // ── Uploads (PDFs)
  listUploads: (profileId: string) =>
    api.get("/uploads", { params: { profile_id: profileId } }),
  uploadStatement: (file: File, profileId: string) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.post("/upload", fd, { params: { profile_id: profileId } });
  },
  deleteUpload: (source: string, profileId: string) =>
    api.delete(`/uploads/${encodeURIComponent(source)}`, { params: { profile_id: profileId } }),

  // ── Transactions
  getTransactions: (profileId: string) =>
    api.get("/transactions", { params: { profile_id: profileId } }),
  markRegret: (txId: string, status: "worth_it" | "regret" | "neutral") =>
    api.post(`/transactions/${txId}/regret`, { regret_status: status }),
  clearTransactions: (profileId: string) =>
    api.delete("/transactions/clear", { params: { profile_id: profileId } }),

  /**
   * Active-Learning Flywheel:
   * Labels a transaction's category and optionally applies the label to all
   * similar merchants, saving the pattern into merchant_memory for future uploads.
   */
  labelTransaction: (txId: string, category: string, applyToSimilar = true) =>
    api.post(`/transactions/${txId}/label`, {
      category,
      apply_to_similar: applyToSimilar,
    }),

  // ── Daily log
  addDailyLog: (
    p: { item_name: string; category: string; amount: number; date?: string },
    profileId: string
  ) => api.post("/daily-log", p, { params: { profile_id: profileId } }),

  // ── Intelligence
  getInsights: (profileId: string) =>
    api.get("/intelligence/insights", { params: { profile_id: profileId } }),
  getSubscriptions: (profileId: string) =>
    api.get("/intelligence/subscriptions", { params: { profile_id: profileId } }),

  /**
   * Returns KMeans clusters of all "Other" / "Unsure:*" transactions
   * so the user can batch-label a whole cluster of similar merchants.
   */
  getOtherClusters: (profileId: string, nClusters = 5) =>
    api.get("/intelligence/other-clusters", {
      params: { profile_id: profileId, n_clusters: nClusters },
    }),

  // ── Goals
  getGoals: (profileId: string) =>
    api.get("/goals", { params: { profile_id: profileId } }),
  createGoal: (
    g: { name: string; target_amount: number; current_amount?: number; deadline?: string },
    profileId: string
  ) => api.post("/goals", g, { params: { profile_id: profileId } }),
  deleteGoal: (goalId: string) =>
    api.delete(`/goals/${goalId}`),

  // ── Budgets
  getBudgets: (profileId: string) =>
    api.get("/budgets", { params: { profile_id: profileId } }),
  createBudget: (
    b: { category: string; target_amount: number; month: string },
    profileId: string
  ) => api.post("/budgets", b, { params: { profile_id: profileId } }),

  // ── Summary
  getMonthlySummary: (profileId: string) =>
    api.get("/summary/monthly", { params: { profile_id: profileId } }),
};
