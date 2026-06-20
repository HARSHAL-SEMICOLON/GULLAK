"use client";
import { useState, useEffect } from "react";
import { gullakApi } from "@/lib/api";
import { CATEGORY_ICONS } from "@/lib/utils";

const ALL_CATEGORIES = [
  "Food", "Groceries", "Health", "Transport", "Petrol",
  "Entertainment", "Subscriptions", "Clothing", "Education",
  "Stationery", "Tech / Devices", "Personal Care", "Utilities",
  "Finance", "P2P Transfer", "Other",
];

interface Cluster {
  merchants: string[];
  tx_count: number;
  total_amount: number;
}

interface OtherClustersProps {
  profileId: string;
  onLabelled: () => void;
}

export function OtherClusters({ profileId, onLabelled }: OtherClustersProps) {
  const [clusters, setClusters] = useState<Record<string, Cluster>>({});
  const [totalUncategorised, setTotalUncategorised] = useState(0);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState<string | null>(null); // cluster id being saved
  const [open, setOpen] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await gullakApi.getOtherClusters(profileId, 6);
      setClusters(res.data.clusters ?? {});
      setTotalUncategorised(res.data.total_uncategorised ?? 0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, profileId]);

  const labelCluster = async (clusterId: string, category: string) => {
    const cluster = clusters[clusterId];
    if (!cluster) return;
    setSaving(clusterId);
    try {
      // Fetch all transaction IDs for merchants in this cluster
      const txRes = await gullakApi.getTransactions(profileId);
      const allTx: any[] = txRes.data ?? [];
      const clusterMerchants = new Set(cluster.merchants);

      const toLabel = allTx.filter(
        (t: any) =>
          clusterMerchants.has(t.merchant_raw) &&
          (t.category === "Other" || t.category?.startsWith("Unsure:"))
      );

      // Label each tx (apply_to_similar=false since we're doing it explicitly)
      await Promise.all(
        toLabel.map((t: any) =>
          gullakApi.labelTransaction(t.id, category, false)
        )
      );

      // Remove this cluster from local state
      setClusters((prev) => {
        const next = { ...prev };
        delete next[clusterId];
        return next;
      });
      setTotalUncategorised((n) => Math.max(0, n - cluster.merchants.length));
      onLabelled();
    } finally {
      setSaving(null);
    }
  };

  if (totalUncategorised === 0 && !open) return null;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
      {/* Header / toggle */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-800/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-amber-400 text-sm">🧩</span>
          <span className="text-sm font-semibold text-slate-200">
            Uncategorised Clusters
          </span>
          {totalUncategorised > 0 && (
            <span className="text-[10px] bg-amber-700/40 text-amber-300 border border-amber-700 rounded-full px-2 py-0.5">
              {totalUncategorised} merchants
            </span>
          )}
        </div>
        <span className="text-slate-500 text-sm">{open ? "▲" : "▼"}</span>
      </button>

      {/* Cluster list */}
      {open && (
        <div className="px-4 pb-4 flex flex-col gap-3">
          {loading && (
            <p className="text-xs text-slate-500 text-center py-4">
              Clustering… (this uses ML embeddings and may take a moment)
            </p>
          )}

          {!loading && Object.keys(clusters).length === 0 && (
            <p className="text-xs text-slate-500 text-center py-4">
              🎉 No uncategorised transactions found!
            </p>
          )}

          {!loading &&
            Object.entries(clusters).map(([cid, cluster]) => (
              <div
                key={cid}
                className="rounded-lg border border-slate-700 bg-slate-800/40 p-3 flex flex-col gap-2"
              >
                {/* Cluster meta */}
                <div className="flex items-center justify-between">
                  <p className="text-xs font-medium text-slate-300">
                    Group {parseInt(cid) + 1} —{" "}
                    <span className="text-slate-400">
                      {cluster.tx_count} transactions · ₹
                      {Math.round(cluster.total_amount).toLocaleString("en-IN")}
                    </span>
                  </p>
                </div>

                {/* Merchant pills */}
                <div className="flex flex-wrap gap-1">
                  {cluster.merchants.map((m) => (
                    <span
                      key={m}
                      className="text-[10px] bg-slate-700 text-slate-300 px-2 py-0.5 rounded-full truncate max-w-[160px]"
                      title={m}
                    >
                      {m}
                    </span>
                  ))}
                </div>

                {/* Category picker */}
                <div className="grid grid-cols-4 gap-1 mt-1">
                  {ALL_CATEGORIES.filter((c) => c !== "Other").map((cat) => (
                    <button
                      key={cat}
                      disabled={saving === cid}
                      onClick={() => labelCluster(cid, cat)}
                      className="text-[10px] py-1 px-1.5 rounded-md border border-slate-600 text-slate-300
                        hover:border-violet-500 hover:text-white hover:bg-violet-900/30 transition-all truncate"
                    >
                      {CATEGORY_ICONS[cat] ?? "📦"} {cat}
                    </button>
                  ))}
                </div>

                {saving === cid && (
                  <p className="text-[10px] text-violet-400 text-center animate-pulse">
                    Saving labels…
                  </p>
                )}
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
