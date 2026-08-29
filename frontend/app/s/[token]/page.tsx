"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError, PublicShareInfo } from "@/lib/api";
import { formatBytes } from "@/lib/format";

export default function PublicSharePage() {
  const params = useParams<{ token: string }>();
  const token = params.token;

  const [info, setInfo] = useState<PublicShareInfo | null>(null);
  const [password, setPassword] = useState("");
  const [dlToken, setDlToken] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    api
      .getPublicShare(token)
      .then(setInfo)
      .catch((err) =>
        setError(err instanceof ApiError ? err.body?.detail || err.message : "This link isn't available.")
      )
      .finally(() => setLoading(false));
  }, [token]);

  const handleUnlock = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const result = await api.unlockPublicShare(token, password);
      setDlToken(result.dl);
      setInfo({ requires_password: false, name: result.name, size: result.size, mime_type: result.mime_type });
    } catch (err) {
      setError(err instanceof ApiError ? err.body?.detail || err.message : "Incorrect password.");
    }
  };

  const handleDownload = async () => {
    if (!info) return;
    setDownloading(true);
    setError(null);
    try {
      await api.downloadPublicShare(token, info.name, dlToken);
    } catch (err) {
      setError(err instanceof ApiError ? err.body?.detail || err.message : "Download failed.");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <div className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 text-center shadow-sm">
        <p className="text-lg font-semibold text-brand-600">driveON</p>

        {loading ? (
          <p className="mt-6 text-sm text-slate-500">Loading...</p>
        ) : !info ? (
          <p className="mt-6 text-sm text-red-600">{error}</p>
        ) : info.requires_password ? (
          <form onSubmit={handleUnlock} className="mt-6 space-y-3 text-left">
            <p className="text-sm text-slate-700">
              <span className="font-medium">{info.name}</span> is password-protected.
            </p>
            <input
              type="password"
              required
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              className="w-full rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
            >
              Unlock
            </button>
          </form>
        ) : (
          <div className="mt-6">
            <p className="text-sm font-medium text-slate-900">{info.name}</p>
            {info.size !== undefined && <p className="mt-1 text-xs text-slate-500">{formatBytes(info.size)}</p>}
            {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
            <button
              onClick={handleDownload}
              disabled={downloading}
              className="mt-4 w-full rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {downloading ? "Downloading..." : "Download"}
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
