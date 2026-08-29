"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { api, DuplicatesResponse } from "@/lib/api";
import { formatBytes, formatDate } from "@/lib/format";

function DuplicatesContent() {
  const [data, setData] = useState<DuplicatesResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    setData(await api.listDuplicates());
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  const handleTrash = async (fileId: number) => {
    if (!confirm("Move this copy to the recycle bin?")) return;
    await api.deleteFile(fileId);
    await load();
  };

  return (
    <div>
      <Navbar />
      <main className="mx-auto max-w-4xl px-6 py-8">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Duplicate Files</h1>
          <Link href="/files" className="text-sm text-brand-600 hover:underline">
            Back to My Files
          </Link>
        </div>

        {loading ? (
          <p className="mt-8 text-slate-500">Loading...</p>
        ) : !data || data.groups.length === 0 ? (
          <p className="mt-8 text-slate-500">No duplicate files found.</p>
        ) : (
          <>
            <p className="mt-4 text-sm text-slate-600">
              Found {data.groups.length} duplicate group{data.groups.length === 1 ? "" : "s"}. Moving the
              extra copies to the recycle bin could free up{" "}
              <span className="font-medium">{formatBytes(data.total_reclaimable_bytes)}</span>.
            </p>
            <div className="mt-6 space-y-4">
              {data.groups.map((group, i) => (
                <div key={i} className="rounded-lg border border-slate-200 bg-white p-5">
                  <p className="text-sm font-medium text-slate-700">
                    Same content &middot; could reclaim {formatBytes(group.reclaimable_bytes)}
                  </p>
                  <ul className="mt-3 divide-y divide-slate-100">
                    {group.files.map((file, idx) => (
                      <li key={file.id} className="flex items-center justify-between py-2 text-sm">
                        <div>
                          <span className="font-medium text-slate-900">{file.name}</span>
                          <span className="ml-2 text-xs text-slate-400">
                            {formatBytes(file.size)} &middot; uploaded {formatDate(file.created_at)}
                          </span>
                        </div>
                        {idx === 0 ? (
                          <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700">
                            Keep (oldest)
                          </span>
                        ) : (
                          <button
                            onClick={() => handleTrash(file.id)}
                            className="text-slate-500 hover:text-red-600"
                          >
                            Move to trash
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

export default function DuplicatesPage() {
  return (
    <ProtectedRoute>
      <DuplicatesContent />
    </ProtectedRoute>
  );
}
