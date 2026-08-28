"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Navbar } from "@/components/Navbar";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { StorageBar } from "@/components/StorageBar";
import { useAuth } from "@/components/AuthProvider";
import { api, ApiError } from "@/lib/api";
import { formatBytes } from "@/lib/format";

type GoogleAccount = {
  id: number;
  email: string;
  display_name: string;
  storage_total: number;
  storage_used: number;
  status: string;
};

const ERROR_MESSAGES: Record<string, string> = {
  access_denied: "Google sign-in was cancelled.",
  invalid_request: "Something went wrong starting the connection. Please try again.",
  invalid_state: "This connection request expired. Please try again.",
  already_connected:
    "This Google account is already connected to another driveON account. Please use a different Google account.",
  max_accounts_reached: "You've reached the maximum number of connected Google accounts for your plan.",
  missing_refresh_token:
    "Google didn't grant offline access. Try removing driveON's access at myaccount.google.com/permissions and reconnecting.",
  oauth_failed: "Couldn't complete the Google connection. Please try again.",
};

function DrivesContent() {
  const { profile, refreshProfile } = useAuth();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [accounts, setAccounts] = useState<GoogleAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [banner, setBanner] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [pendingRemoval, setPendingRemoval] = useState<{ id: number; message: string } | null>(null);

  const load = async () => {
    setLoading(true);
    const data = await api.listGoogleAccounts();
    setAccounts(data);
    setLoading(false);
  };

  useEffect(() => {
    load();
    const error = searchParams.get("error");
    const connected = searchParams.get("connected");
    if (error) {
      setBanner({ type: "error", text: ERROR_MESSAGES[error] || "Something went wrong." });
      router.replace("/drives");
    } else if (connected) {
      setBanner({ type: "success", text: "Google Drive connected." });
      refreshProfile();
      router.replace("/drives");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleConnect = async () => {
    const { authorization_url } = await api.connectGoogle();
    window.location.href = authorization_url;
  };

  const handleRemove = async (id: number, force = false) => {
    try {
      await api.removeGoogleAccount(id, force);
      setPendingRemoval(null);
      await load();
      await refreshProfile();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setPendingRemoval({ id, message: err.body?.detail || "This account has files depending on it." });
      }
    }
  };

  const atLimit = (profile?.connected_google_accounts ?? 0) >= (profile?.max_google_accounts ?? 5);

  return (
    <div>
      <Navbar />
      <main className="mx-auto max-w-4xl px-6 py-8">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Connected Google Drives</h1>
          <button
            onClick={handleConnect}
            disabled={atLimit}
            className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            + Add Google Drive
          </button>
        </div>

        {banner && (
          <div
            className={`mt-4 rounded-md px-4 py-3 text-sm ${
              banner.type === "success" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
            }`}
          >
            {banner.text}
          </div>
        )}

        {atLimit && (
          <p className="mt-4 text-sm text-amber-600">
            You&apos;ve reached your plan&apos;s limit of {profile?.max_google_accounts} connected accounts.
          </p>
        )}

        <div className="mt-6 space-y-4">
          {loading ? (
            <p className="text-slate-500">Loading...</p>
          ) : accounts.length === 0 ? (
            <p className="text-slate-500">No Google Drives connected yet.</p>
          ) : (
            accounts.map((account) => (
              <div key={account.id} className="rounded-lg border border-slate-200 bg-white p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{account.email}</p>
                    <p className="text-sm capitalize text-slate-500">{account.status}</p>
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
      </main>
    </div>
  );
}

export default function DrivesPage() {
  return (
    <ProtectedRoute>
      <Suspense fallback={null}>
        <DrivesContent />
      </Suspense>
    </ProtectedRoute>
  );
}
