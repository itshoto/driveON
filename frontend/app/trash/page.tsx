"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { api, ApiError, TrashedFile } from "@/lib/api";
import { formatBytes, formatDate } from "@/lib/format";

function daysRemaining(purgeAt: string): number {
  const ms = new Date(purgeAt).getTime() - Date.now();
  return Math.max(0, Math.ceil(ms / (1000 * 60 * 60 * 24)));
}

function TrashContent() {
  const [files, setFiles] = useState<TrashedFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    const data = await api.listTrash();
    setFiles(data);
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  const handleRestore = async (file: TrashedFile) => {
    setError(null);
    try {
      await api.restoreFile(file.id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.body?.detail || err.message : "Restore failed.");
    }
  };

  const handlePurge = async (file: TrashedFile) => {
    if (!confirm(`Permanently delete "${file.name}"? This cannot be undone.`)) return;
    setError(null);
    try {
      await api.purgeFile(file.id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.body?.detail || err.message : "Delete failed.");
    }
  };

  return (
    <div>
      <Navbar />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Recycle Bin</h1>
          <Link href="/files" className="text-sm text-brand-600 hover:underline">
            Back to My Files
          </Link>
        </div>
        <p className="mt-1 text-sm text-slate-500">
          Files are kept here for 30 days before being permanently deleted.
        </p>

        {error && <div className="mt-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

        <div className="mt-6 overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Size</th>
                <th className="px-4 py-3 font-medium">Deleted</th>
                <th className="px-4 py-3 font-medium">Permanent deletion</th>
                <th className="px-4 py-3 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                    Loading...
                  </td>
                </tr>
              ) : files.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                    Recycle bin is empty.
                  </td>
                </tr>
              ) : (
                files.map((file) => (
                  <tr key={file.id}>
                    <td className="px-4 py-3">{file.name}</td>
                    <td className="px-4 py-3 text-slate-500">{formatBytes(file.size)}</td>
                    <td className="px-4 py-3 text-slate-500">{formatDate(file.deleted_at)}</td>
                    <td className="px-4 py-3 text-slate-500">in {daysRemaining(file.purge_at)} day(s)</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-3 text-slate-500">
                        <button onClick={() => handleRestore(file)} className="hover:text-brand-600">
                          Restore
                        </button>
                        <button onClick={() => handlePurge(file)} className="hover:text-red-600">
                          Delete permanently
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}

export default function TrashPage() {
  return (
    <ProtectedRoute>
      <TrashContent />
    </ProtectedRoute>
  );
}
