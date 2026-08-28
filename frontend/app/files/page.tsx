"use client";

import { useEffect, useState } from "react";
import { Navbar } from "@/components/Navbar";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { api, ApiError } from "@/lib/api";
import { formatBytes } from "@/lib/format";

type DriveFile = {
  id: number;
  name: string;
  mime_type: string;
  size: number;
  status: string;
  created_at: string;
};

const TYPES: { key?: string; label: string }[] = [
  { key: undefined, label: "All" },
  { key: "pdf", label: "PDFs" },
  { key: "image", label: "Images" },
  { key: "video", label: "Videos" },
  { key: "document", label: "Documents" },
];

function FilesContent() {
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [type, setType] = useState<string | undefined>(undefined);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const load = async () => {
    setLoading(true);
    const data = await api.listFiles({ search: search || undefined, type });
    setFiles(data);
    setLoading(false);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    load();
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError(null);
    setUploadPct(0);
    try {
      await api.uploadFile(file, setUploadPct);
      await load();
    } catch (err) {
      if (err instanceof ApiError) {
        const detail = err.body?.detail || err.message;
        const shortBy = err.body?.short_by_bytes;
        setError(shortBy ? `${detail} Short by ${formatBytes(shortBy)}.` : detail);
      } else {
        setError("Upload failed.");
      }
    } finally {
      setUploadPct(null);
    }
  };

  const handleDownload = async (file: DriveFile) => {
    setError(null);
    try {
      await api.downloadFile(file.id, file.name);
    } catch (err) {
      setError(err instanceof ApiError ? err.body?.detail || err.message : "Download failed.");
    }
  };

  const handleDelete = async (file: DriveFile) => {
    if (!confirm(`Delete "${file.name}"? This cannot be undone.`)) return;
    await api.deleteFile(file.id);
    await load();
  };

  const startRename = (file: DriveFile) => {
    setRenamingId(file.id);
    setRenameValue(file.name);
  };

  const submitRename = async (file: DriveFile) => {
    if (renameValue.trim() && renameValue !== file.name) {
      try {
        await api.renameFile(file.id, renameValue.trim());
        await load();
      } catch (err) {
        setError(err instanceof ApiError ? err.body?.detail || err.message : "Rename failed.");
      }
    }
    setRenamingId(null);
  };

  return (
    <div>
      <Navbar />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-2xl font-semibold">My Files</h1>
          <label className="cursor-pointer rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
            Upload
            <input type="file" className="hidden" onChange={handleUpload} />
          </label>
        </div>

        {uploadPct !== null && (
          <div className="mt-4 rounded-md bg-brand-50 px-4 py-3 text-sm text-brand-700">
            Uploading... {uploadPct}%
          </div>
        )}
        {error && <div className="mt-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

        <form onSubmit={handleSearchSubmit} className="mt-6 flex gap-2">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search files..."
            className="w-full max-w-sm rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </form>

        <div className="mt-4 flex gap-2 border-b border-slate-200">
          {TYPES.map((t) => (
            <button
              key={t.label}
              onClick={() => setType(t.key)}
              className={`border-b-2 px-3 py-2 text-sm font-medium ${
                type === t.key
                  ? "border-brand-600 text-brand-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Size</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-slate-500">
                    Loading...
                  </td>
                </tr>
              ) : files.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-slate-500">
                    No files found.
                  </td>
                </tr>
              ) : (
                files.map((file) => (
                  <tr key={file.id}>
                    <td className="px-4 py-3">
                      {renamingId === file.id ? (
                        <input
                          autoFocus
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onBlur={() => submitRename(file)}
                          onKeyDown={(e) => e.key === "Enter" && submitRename(file)}
                          className="rounded-md border border-slate-300 px-2 py-1 text-sm"
                        />
                      ) : (
                        file.name
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-500">{formatBytes(file.size)}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${
                          file.status === "available"
                            ? "bg-emerald-50 text-emerald-700"
                            : file.status === "partially_available"
                            ? "bg-amber-50 text-amber-700"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {file.status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-3 text-slate-500">
                        <button onClick={() => handleDownload(file)} className="hover:text-brand-600">
                          Download
                        </button>
                        <button onClick={() => startRename(file)} className="hover:text-brand-600">
                          Rename
                        </button>
                        <button onClick={() => handleDelete(file)} className="hover:text-red-600">
                          Delete
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

export default function FilesPage() {
  return (
    <ProtectedRoute>
      <FilesContent />
    </ProtectedRoute>
  );
}
