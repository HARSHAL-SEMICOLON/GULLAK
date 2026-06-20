"use client";
import { useState, useEffect } from "react";
import { gullakApi } from "@/lib/api";
import { RefreshCw, Trash2, Plus, X, FileText, Check, ChevronRight } from "lucide-react";

const AVATAR_OPTIONS = ["👤", "👦", "👩", "🧑", "👨‍💼", "👩‍💼", "🧔", "👱", "🦊", "🐼", "🦁", "🐯", "🚀", "💎", "🌟", "🔥"];

interface Profile {
  id: string;
  name: string;
  avatar_emoji: string;
  created_at?: string;
}

interface Upload {
  source: string;
  tx_count: number;
  date_from: string;
  date_to: string;
  total_amount: number;
}

interface ProfileManagerProps {
  currentProfileId: string;
  onProfileSwitch: (profileId: string) => void;
  onClose: () => void;
}

export function ProfileManager({ currentProfileId, onProfileSwitch, onClose }: ProfileManagerProps) {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"profiles" | "pdfs">("profiles");

  // Create profile form
  const [newName, setNewName] = useState("");
  const [newAvatar, setNewAvatar] = useState("👤");
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);

  // Delete states
  const [deletingProfile, setDeletingProfile] = useState<string | null>(null);
  const [deletingUpload, setDeletingUpload] = useState<string | null>(null);

  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const loadProfiles = async () => {
    try {
      const res = await gullakApi.getProfiles();
      setProfiles(res.data);
    } catch { /* backend might be starting */ }
  };

  const loadUploads = async () => {
    try {
      const res = await gullakApi.listUploads(currentProfileId);
      setUploads(res.data);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    setLoading(true);
    Promise.all([loadProfiles(), loadUploads()]).finally(() => setLoading(false));
  }, [currentProfileId]);

  const handleCreateProfile = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await gullakApi.createProfile(newName.trim(), newAvatar);
      await loadProfiles();
      setNewName("");
      setNewAvatar("👤");
      setShowCreate(false);
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteProfile = async (id: string) => {
    if (confirmDelete !== id) {
      setConfirmDelete(id);
      return;
    }
    setDeletingProfile(id);
    try {
      await gullakApi.deleteProfile(id);
      if (id === currentProfileId) {
        const remaining = profiles.find(p => p.id !== id);
        if (remaining) onProfileSwitch(remaining.id);
      }
      await loadProfiles();
      setConfirmDelete(null);
    } catch (e: any) {
      alert(e?.response?.data?.detail || "Cannot delete profile");
    } finally {
      setDeletingProfile(null);
    }
  };

  const handleDeleteUpload = async (source: string) => {
    if (confirmDelete !== source) {
      setConfirmDelete(source);
      return;
    }
    setDeletingUpload(source);
    try {
      await gullakApi.deleteUpload(source, currentProfileId);
      await loadUploads();
      setConfirmDelete(null);
    } finally {
      setDeletingUpload(null);
    }
  };

  const currentProfile = profiles.find(p => p.id === currentProfileId);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-end">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Drawer */}
      <div className="relative w-full max-w-sm h-full bg-slate-950 border-l border-slate-800 shadow-2xl flex flex-col slide-up">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <div>
            <h2 className="text-white font-bold text-lg">Profile Manager</h2>
            <p className="text-slate-500 text-xs mt-0.5">Switch profiles & manage PDFs</p>
          </div>
          <button onClick={onClose}
            className="w-8 h-8 rounded-lg border border-slate-700 flex items-center justify-center text-slate-400 hover:text-white transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 px-5 pt-4 pb-2">
          {(["profiles", "pdfs"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-all capitalize ${
                tab === t
                  ? "bg-emerald-800/60 text-emerald-300 border border-emerald-700/50"
                  : "text-slate-500 hover:text-slate-300 bg-slate-900"
              }`}>
              {t === "profiles" ? `👥 Profiles` : `📄 PDFs`}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-3 space-y-3 custom-scroll">
          {loading && (
            <div className="space-y-2">
              {[1, 2, 3].map(i => <div key={i} className="h-16 rounded-xl shimmer" />)}
            </div>
          )}

          {/* ── PROFILES TAB ── */}
          {!loading && tab === "profiles" && (
            <>
              {profiles.map(profile => (
                <div key={profile.id}
                  className={`flex items-center gap-3 p-3 rounded-xl border transition-all ${
                    profile.id === currentProfileId
                      ? "bg-emerald-900/20 border-emerald-700/50"
                      : "bg-slate-900 border-slate-800 hover:border-slate-600"
                  }`}>
                  {/* Avatar */}
                  <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-xl flex-shrink-0">
                    {profile.avatar_emoji}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-medium text-sm truncate">{profile.name}</p>
                    <p className="text-slate-500 text-xs">
                      {profile.id === currentProfileId ? "Active profile" : "Click to switch"}
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1.5">
                    {profile.id !== currentProfileId && (
                      <button
                        onClick={() => { onProfileSwitch(profile.id); onClose(); }}
                        className="text-xs text-emerald-400 border border-emerald-800 px-2 py-1 rounded-lg hover:bg-emerald-900/30 transition-colors">
                        Switch
                      </button>
                    )}
                    {profile.id === currentProfileId && (
                      <span className="text-emerald-400 text-xs flex items-center gap-1">
                        <Check className="w-3 h-3" /> Active
                      </span>
                    )}
                    {profiles.length > 1 && (
                      <button
                        onClick={() => handleDeleteProfile(profile.id)}
                        disabled={deletingProfile === profile.id}
                        className={`w-7 h-7 rounded-lg flex items-center justify-center transition-colors ${
                          confirmDelete === profile.id
                            ? "bg-rose-700 text-white"
                            : "text-slate-600 hover:text-rose-400 hover:bg-rose-900/20 border border-slate-800"
                        }`}
                        title={confirmDelete === profile.id ? "Click again to confirm delete" : "Delete profile"}>
                        {deletingProfile === profile.id
                          ? <RefreshCw className="w-3 h-3 animate-spin" />
                          : confirmDelete === profile.id
                          ? <Check className="w-3 h-3" />
                          : <Trash2 className="w-3 h-3" />}
                      </button>
                    )}
                  </div>
                </div>
              ))}

              {/* Create profile */}
              {showCreate ? (
                <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 space-y-3 slide-up">
                  <p className="text-white text-sm font-medium">New Profile</p>
                  {/* Avatar picker */}
                  <div className="grid grid-cols-8 gap-1.5">
                    {AVATAR_OPTIONS.map(em => (
                      <button key={em} onClick={() => setNewAvatar(em)}
                        className={`w-8 h-8 rounded-lg text-base flex items-center justify-center transition-all ${
                          newAvatar === em ? "bg-emerald-800 ring-1 ring-emerald-500" : "hover:bg-slate-800"
                        }`}>
                        {em}
                      </button>
                    ))}
                  </div>
                  <input
                    value={newName}
                    onChange={e => setNewName(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && handleCreateProfile()}
                    placeholder="Profile name…"
                    autoFocus
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-emerald-600"
                  />
                  <div className="flex gap-2">
                    <button onClick={handleCreateProfile} disabled={!newName.trim() || creating}
                      className="flex-1 bg-emerald-700 hover:bg-emerald-600 disabled:opacity-40 text-white text-sm py-2 rounded-lg flex items-center justify-center gap-1.5 transition-colors">
                      {creating ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                      Create
                    </button>
                    <button onClick={() => { setShowCreate(false); setNewName(""); }}
                      className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm rounded-lg transition-colors">
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <button onClick={() => setShowCreate(true)}
                  className="w-full flex items-center justify-center gap-2 py-2.5 border border-dashed border-slate-700 rounded-xl text-slate-500 hover:text-emerald-400 hover:border-emerald-700 text-sm transition-colors">
                  <Plus className="w-4 h-4" /> Add New Profile
                </button>
              )}
            </>
          )}

          {/* ── PDFs TAB ── */}
          {!loading && tab === "pdfs" && (
            <>
              <div className="flex items-center justify-between mb-1">
                <p className="text-slate-400 text-xs">
                  PDFs imported for <strong className="text-white">{currentProfile?.name}</strong>
                </p>
                <span className="text-slate-600 text-xs">{uploads.length} file{uploads.length !== 1 ? "s" : ""}</span>
              </div>

              {uploads.length === 0 && (
                <div className="text-center py-10">
                  <p className="text-4xl mb-3">📭</p>
                  <p className="text-slate-500 text-sm">No PDFs imported yet.</p>
                  <p className="text-slate-600 text-xs mt-1">Use "Import PDF" in the top navbar.</p>
                </div>
              )}

              {uploads.map(u => (
                <div key={u.source} className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                      <div className="min-w-0">
                        <p className="text-white text-sm font-medium truncate">{u.source}</p>
                        <p className="text-slate-500 text-xs">{u.date_from} → {u.date_to}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeleteUpload(u.source)}
                      disabled={deletingUpload === u.source}
                      className={`flex-shrink-0 flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border transition-all ${
                        confirmDelete === u.source
                          ? "bg-rose-700 border-rose-600 text-white"
                          : "border-slate-700 text-slate-400 hover:border-rose-700 hover:text-rose-400 hover:bg-rose-900/20"
                      }`}>
                      {deletingUpload === u.source
                        ? <RefreshCw className="w-3 h-3 animate-spin" />
                        : confirmDelete === u.source
                        ? <><Check className="w-3 h-3" /> Confirm</>
                        : <><Trash2 className="w-3 h-3" /> Remove</>}
                    </button>
                  </div>

                  <div className="flex gap-4 text-xs text-slate-500">
                    <span>{u.tx_count} transactions</span>
                    <span>₹{Math.round(u.total_amount).toLocaleString("en-IN")} total</span>
                  </div>
                </div>
              ))}

              {/* Danger zone */}
              {uploads.length > 0 && (
                <div className="mt-4 border border-rose-900/40 rounded-xl p-4 space-y-2">
                  <p className="text-rose-400 text-xs font-semibold">⚠️ Danger Zone</p>
                  <p className="text-slate-500 text-xs">Remove ALL transactions for this profile.</p>
                  <button
                    onClick={async () => {
                      if (!confirm("Delete ALL transactions for this profile? This cannot be undone.")) return;
                      await gullakApi.clearTransactions(currentProfileId);
                      await loadUploads();
                    }}
                    className="w-full text-xs text-rose-400 border border-rose-800 py-2 rounded-lg hover:bg-rose-900/20 transition-colors">
                    🗑️ Clear All Transactions
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
