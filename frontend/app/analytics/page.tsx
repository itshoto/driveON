"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { api, FileStats, StorageSummary } from "@/lib/api";
import { formatBytes } from "@/lib/format";

const TYPE_LABELS: Record<string, string> = {
  image: "Images",
  video: "Videos",
  audio: "Music",
  document: "Documents",
  pdf: "PDFs",
  archive: "Archives",
  other: "Other",
};

function Bar({ label, value, max, detail }: { label: string; value: number; max: number; detail: string }) {
  const pct = max > 0 ? Math.max(2, Math.round((value / max) * 100)) : 0;
  return (
    <div>
      <div className="flex justify-between text-xs text-slate-600">
        <span className="font-medium">{label}</span>
        <span>{detail}</span>
      </div>
      <div className="mt-1 h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-brand-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function AnalyticsContent() {
  const [summary, setSummary] = useState<StorageSummary | null>(null);
  const [stats, setStats] = useState<FileStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const [summaryData, statsData] = await Promise.all([api.storageSummary(), api.fileStats()]);
      setSummary(summaryData);
      setStats(statsData);
      setLoading(false);
    })();
  }, []);

  const sizes = stats?.sizes ?? {};
  const typeEntries = Object.entries(TYPE_LABELS)
    .map(([key, label]) => ({ key, label, size: sizes[key] ?? 0, count: stats?.[key] ?? 0 }))
    .filter((entry) => entry.count > 0)
    .sort((a, b) => b.size - a.size);
  const maxTypeSize = Math.max(1, ...typeEntries.map((e) => e.size));
  const maxAccountUsed = Math.max(1, ...(summary?.accounts.map((a) => a.storage_used) ?? [0]));

  return (
    <div>
      <Navbar />
      <main className="mx-auto max-w-4xl px-6 py-8">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Storage Analytics</h1>
          <Link href="/files" className="text-sm text-brand-600 hover:underline">
            Back to My Files
          </Link>
        </div>

        {loading ? (
          <p className="mt-8 text-slate-500">Loading...</p>
        ) : (
          <div className="mt-8 grid gap-6 md:grid-cols-2">
            <div className="rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="text-sm font-medium text-slate-500">Usage by Drive</h2>
              <div className="mt-4 space-y-4">
                {summary?.accounts.length ? (
                  summary.accounts.map((account) => (
                    <Bar
                      key={account.id}
                      label={account.email}
                      value={account.storage_used}
                      max={maxAccountUsed}
                      detail={`${formatBytes(account.storage_used)} / ${formatBytes(account.storage_total)}`}
                    />
                  ))
                ) : (
                  <p className="text-sm text-slate-500">No connected drives yet.</p>
                )}
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="text-sm font-medium text-slate-500">Usage by File Type</h2>
              <div className="mt-4 space-y-4">
                {typeEntries.length ? (
                  typeEntries.map((entry) => (
                    <Bar
                      key={entry.key}
                      label={entry.label}
                      value={entry.size}
                      max={maxTypeSize}
                      detail={`${formatBytes(entry.size)} (${entry.count})`}
                    />
                  ))
                ) : (
                  <p className="text-sm text-slate-500">No files yet.</p>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default function AnalyticsPage() {
  return (
    <ProtectedRoute>
      <AnalyticsContent />
    </ProtectedRoute>
  );
}
