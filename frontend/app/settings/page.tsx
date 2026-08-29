"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { EmailAuthProvider, reauthenticateWithCredential, signOut } from "firebase/auth";
import { Navbar } from "@/components/Navbar";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { ConnectedAccountsPanel } from "@/components/ConnectedAccountsPanel";
import { useAuth } from "@/components/AuthProvider";
import { auth } from "@/lib/firebase";
import { api, AIQuota, ApiError, NotificationPreferences } from "@/lib/api";

const CONFIRMATION_PHRASE = "DELETE";

function AIUsageSection() {
  const [quota, setQuota] = useState<AIQuota | null>(null);

  useEffect(() => {
    api.getAIQuota().then(setQuota).catch(() => {});
  }, []);

  if (!quota) return null;

  const pct = quota.limit > 0 ? Math.min(100, Math.round((quota.used / quota.limit) * 100)) : 0;

  return (
    <div className="mt-6 rounded-lg border border-slate-200 bg-white p-6">
      <h2 className="text-lg font-semibold">AI Usage</h2>
      <p className="mt-1 text-sm text-slate-500">
        {quota.used} / {quota.limit} AI queries used this month (summaries, chat, search, and manual
        categorization -- automatic categorization after upload doesn&apos;t count).
      </p>
      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full ${pct > 90 ? "bg-red-500" : pct > 70 ? "bg-amber-500" : "bg-brand-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

const PREFERENCE_LABELS: { key: keyof NotificationPreferences; label: string }[] = [
  { key: "email_upload", label: "Upload issues (failed or partial uploads)" },
  { key: "email_account", label: "Account changes (a drive gets disconnected)" },
  { key: "email_rebalance", label: "Rebalancing issues" },
];

function NotificationPreferencesSection() {
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    api.getNotificationPreferences().then(setPrefs).catch(() => {});
  }, []);

  const handleToggle = async (key: keyof NotificationPreferences) => {
    if (!prefs) return;
    const next = { ...prefs, [key]: !prefs[key] };
    setPrefs(next);
    setSaving(key);
    try {
      await api.updateNotificationPreferences({ [key]: next[key] });
    } catch {
      setPrefs(prefs); // revert on failure
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className="mt-6 rounded-lg border border-slate-200 bg-white p-6">
      <h2 className="text-lg font-semibold">Notification Preferences</h2>
      <p className="mt-1 text-sm text-slate-500">Choose which events driveON should email you about.</p>
      <div className="mt-4 space-y-3">
        {PREFERENCE_LABELS.map(({ key, label }) => (
          <label key={key} className="flex items-center justify-between gap-4 text-sm">
            <span className="text-slate-700">{label}</span>
            <input
              type="checkbox"
              checked={prefs?.[key] ?? true}
              disabled={!prefs || saving === key}
              onChange={() => handleToggle(key)}
              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
            />
          </label>
        ))}
      </div>
    </div>
  );
}

function SettingsContent() {
  const { profile, firebaseUser } = useAuth();
  const router = useRouter();
  const [showDeleteFlow, setShowDeleteFlow] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const resetDeleteFlow = () => {
    setShowDeleteFlow(false);
    setPassword("");
    setConfirmation("");
    setError(null);
  };

  const handleSignOut = async () => {
    await signOut(auth);
    router.replace("/login");
  };

  const handleDelete = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (confirmation !== CONFIRMATION_PHRASE) {
      setError(`Type "${CONFIRMATION_PHRASE}" to confirm.`);
      return;
    }
    if (!firebaseUser?.email) {
      setError("Can't verify your identity. Please sign out, sign back in, then retry.");
      return;
    }

    setSubmitting(true);
    try {
      // Re-proves the password right before an irreversible action, and
      // gives the backend a freshly-issued token so its reauth-window
      // check (see users.views.MeView.delete) passes.
      await reauthenticateWithCredential(firebaseUser, EmailAuthProvider.credential(firebaseUser.email, password));
      await api.deleteAccount(CONFIRMATION_PHRASE);
      await signOut(auth);
      router.replace("/login");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.body?.detail || err.message);
      } else {
        setError("Incorrect password. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <Navbar />
      <main className="mx-auto max-w-2xl px-6 py-8">
        <h1 className="text-2xl font-semibold">Settings</h1>

        <div className="mt-8 rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="text-sm font-medium text-slate-500">Account</h2>
          <p className="mt-2 text-sm text-slate-700">
            {profile?.username} &middot; {profile?.email}
          </p>
          <button
            onClick={handleSignOut}
            className="mt-4 rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
          >
            Sign out
          </button>
        </div>

        <div className="mt-6 rounded-lg border border-slate-200 bg-white p-6">
          <ConnectedAccountsPanel />
        </div>

        <NotificationPreferencesSection />

        <AIUsageSection />

        <div className="mt-6 rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="text-lg font-semibold">Recycle Bin</h2>
          <p className="mt-1 text-sm text-slate-500">
            Deleted files are kept for 30 days before being permanently removed.
          </p>
          <Link href="/trash" className="mt-3 inline-block text-sm text-brand-600 hover:underline">
            View Recycle Bin &rarr;
          </Link>
        </div>

        <div className="mt-6 rounded-lg border border-red-200 bg-red-50 p-6">
          <h2 className="text-sm font-medium text-red-700">Danger zone</h2>
          <p className="mt-2 text-sm text-red-700">
            Deleting your account removes your driveON profile, disconnects every linked drive account,
            and revokes driveON&apos;s access to them. Files already stored in your own Google Drive or
            OneDrive are not deleted &mdash; only driveON&apos;s record of and access to them are removed.
            This cannot be undone.
          </p>

          {!showDeleteFlow ? (
            <button
              onClick={() => setShowDeleteFlow(true)}
              className="mt-4 rounded-md border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100"
            >
              Delete my account
            </button>
          ) : (
            <form onSubmit={handleDelete} className="mt-4 space-y-3">
              <div>
                <label className="block text-sm font-medium text-red-700">Confirm your password</label>
                <input
                  required
                  autoFocus
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="mt-1 w-full rounded-md border border-red-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-red-700">
                  Type {CONFIRMATION_PHRASE} to confirm
                </label>
                <input
                  required
                  value={confirmation}
                  onChange={(e) => setConfirmation(e.target.value)}
                  className="mt-1 w-full rounded-md border border-red-300 px-3 py-2 text-sm"
                />
              </div>
              {error && <p className="text-sm text-red-800">{error}</p>}
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={submitting}
                  className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
                >
                  {submitting ? "Deleting..." : "Permanently delete account"}
                </button>
                <button
                  type="button"
                  onClick={resetDeleteFlow}
                  className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>
      </main>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <ProtectedRoute>
      <SettingsContent />
    </ProtectedRoute>
  );
}
