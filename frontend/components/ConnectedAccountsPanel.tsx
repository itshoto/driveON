"use client";

import { useEffect, useState } from "react";
import { StorageBar } from "@/components/StorageBar";
import { useAuth } from "@/components/AuthProvider";
import { api, ApiError, StorageAccount } from "@/lib/api";
import { formatBytes } from "@/lib/format";

const PROVIDER_LABELS: Record<StorageAccount["provider"], string> = {
  google: "Google Drive",
  microsoft: "OneDrive",
};

export function ConnectedAccountsPanel({ title = "Connected Drives" }: { title?: string }) {
  const { profile, refreshProfile } = useAuth();
  const [accounts, setAccounts] = useState<StorageAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingRemoval, setPendingRemoval] = useState<{ id: number; message: string } | null>(null);

  const load = async () => {
    setLoading(true);
    const data = await api.listAccounts();
    setAccounts(data);
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  const handleConnect = async (provider: "google" | "microsoft") => {
    setError(null);
    try {
      const { authorization_url } = await api.connectAccount(provider);
      window.location.href = authorization_url;
    } catch (err) {
      setError(err instanceof ApiError ? err.body?.detail || err.message : "Couldn't start the connection.");
    }
  };

  const handleRemove = async (id: number, force = false) => {
    try {
      await api.removeAccount(id, force);
      setPendingRemoval(null);
      await load();
      await refreshProfile();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setPendingRemoval({ id, message: err.body?.detail || "This account has files depending on it." });
      }
    }
  };

  const atLimit = (profile?.connected_accounts ?? 0) >= (profile?.max_connected_accounts ?? 5);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{title}</h2>
        <div className="flex gap-2">
          <button
            onClick={() => handleConnect("google")}
            disabled={atLimit}
            className="rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            + Add Google Drive
          </button>
          <button
            onClick={() => handleConnect("microsoft")}
            disabled={atLimit}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            + Add OneDrive
          </button>
        </div>
      </div>

      {error && <div className="mt-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      {atLimit && (
        <p className="mt-4 text-sm text-amber-600">
          You&apos;ve reached your plan&apos;s limit of {profile?.max_connected_accounts} connected accounts.
        </p>
      )}

      <div className="mt-6 space-y-4">
        {loading ? (
          <p className="text-slate-500">Loading...</p>
        ) : accounts.length === 0 ? (
          <p className="text-slate-500">No drives connected yet.</p>
        ) : (
          accounts.map((account) => (
            <div key={account.id} className="rounded-lg border border-slate-200 bg-white p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">{account.email}</p>
                  <p className="text-sm text-slate-500">
                    {PROVIDER_LABELS[account.provider]} &middot;{" "}
                    <span className="capitalize">{account.status}</span>
                  </p>
                </div>
                {account.status === "connected" && (
                  <button
                    onClick={() => handleRemove(account.id)}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
                  >
                    Remove
                  </button>
                )}
              </div>
              {account.status === "connected" && (
                <div className="mt-3">
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>{formatBytes(account.storage_used)} used</span>
                    <span>{formatBytes(account.storage_total)} total</span>
                  </div>
                  <div className="mt-1">
                    <StorageBar used={account.storage_used} total={account.storage_total} />
                  </div>
                </div>
              )}
              {pendingRemoval?.id === account.id && (
                <div className="mt-3 rounded-md bg-amber-50 p-3 text-sm text-amber-800">
                  <p>{pendingRemoval.message}</p>
                  <div className="mt-2 flex gap-2">
                    <button
                      onClick={() => handleRemove(account.id, true)}
                      className="rounded-md bg-amber-600 px-3 py-1 text-white hover:bg-amber-700"
                    >
                      Remove anyway
                    </button>
                    <button
                      onClick={() => setPendingRemoval(null)}
                      className="rounded-md border border-amber-300 px-3 py-1 text-amber-700"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
