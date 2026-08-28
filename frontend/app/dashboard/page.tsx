"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { StorageBar } from "@/components/StorageBar";
import { useAuth } from "@/components/AuthProvider";
import { api } from "@/lib/api";
import { formatBytes } from "@/lib/format";

type StorageSummary = { total: number; used: number; available: number };
type DriveFile = { id: number; name: string; size: number };

function DashboardContent() {
  const { profile } = useAuth();
  const [summary, setSummary] = useState<StorageSummary | null>(null);
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const [summaryData, filesData] = await Promise.all([api.storageSummary(), api.listFiles()]);
      setSummary(summaryData);
      setFiles(filesData.slice(0, 5));
      setLoading(false);
    })();
  }, []);

  return (
    <div>
      <Navbar />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <h1 className="text-2xl font-semibold">Welcome back, {profile?.username}!</h1>

        {loading ? (
          <p className="mt-8 text-slate-500">Loading...</p>
        ) : (
          <div className="mt-8 grid gap-6 md:grid-cols-2">
            <div className="rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="text-sm font-medium text-slate-500">Storage</h2>
              <p className="mt-1 text-2xl font-semibold">
                {formatBytes(summary?.used ?? 0)} / {formatBytes(summary?.total ?? 0)}
              </p>
              <div className="mt-3">
                <StorageBar used={summary?.used ?? 0} total={summary?.total ?? 0} />
              </div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="text-sm font-medium text-slate-500">Connected Drives</h2>
              <p className="mt-1 text-2xl font-semibold">
                {profile?.connected_google_accounts ?? 0} / {profile?.max_google_accounts ?? 5}
              </p>
              <Link href="/drives" className="mt-3 inline-block text-sm text-brand-600 hover:underline">
                Manage drives &rarr;
              </Link>
            </div>
          </div>
        )}

        <div className="mt-8 rounded-lg border border-slate-200 bg-white p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-slate-500">Recent Files</h2>
            <div className="flex items-center gap-4">
              <Link href="/files" className="text-sm text-brand-600 hover:underline">
                Upload
              </Link>
              <Link href="/files" className="text-sm text-brand-600 hover:underline">
                View all &rarr;
              </Link>
            </div>
          </div>
          {files.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">No files yet. Head to My Files to upload one.</p>
          ) : (
            <ul className="mt-4 divide-y divide-slate-100">
              {files.map((f) => (
                <li key={f.id} className="flex items-center justify-between py-2 text-sm">
                  <span>{f.name}</span>
                  <span className="text-slate-400">{formatBytes(f.size)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}
