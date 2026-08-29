"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { FilePreviewModal } from "@/components/FilePreviewModal";
import { HealthBadge, FileHealth } from "@/components/HealthBadge";
import { ShareModal } from "@/components/ShareModal";
import { SummaryModal } from "@/components/SummaryModal";
import { UploadQueue } from "@/components/UploadQueue";
import { useAuth } from "@/components/AuthProvider";
import { api, ApiError } from "@/lib/api";
import { formatBytes, formatDate } from "@/lib/format";

type DriveFile = {
  id: number;
  name: string;
  mime_type: string;
  size: number;
  status: string;
  replication_level: string;
  category: string;
  health: FileHealth;
  created_at: string;
  updated_at: string;
};

const CATEGORIES: { key?: string; label: string }[] = [
  { key: undefined, label: "All categories" },
  { key: "research", label: "Research" },
  { key: "invoices", label: "Invoices" },
  { key: "legal", label: "Legal" },
  { key: "personal", label: "Personal" },
  { key: "datasets", label: "Datasets" },
  { key: "reports", label: "Reports" },
  { key: "other", label: "Other" },
];

type FileStats = Record<string, number>;

const TYPES: { key?: string; label: string }[] = [
  { key: undefined, label: "All" },
  { key: "image", label: "Images" },
  { key: "video", label: "Videos" },
  { key: "audio", label: "Music" },
  { key: "document", label: "Documents" },
  { key: "pdf", label: "PDFs" },
  { key: "archive", label: "Archives" },
  { key: "other", label: "Other" },
];

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "-created", label: "Newest first" },
  { value: "created", label: "Oldest first" },
  { value: "-modified", label: "Recently modified" },
  { value: "modified", label: "Least recently modified" },
  { value: "name", label: "Name (A–Z)" },
  { value: "-name", label: "Name (Z–A)" },
  { value: "-size", label: "Largest first" },
  { value: "size", label: "Smallest first" },
  { value: "type", label: "Type" },
];

const REPLICATION_OPTIONS: { value: string; label: string; minAccounts: number }[] = [
  { value: "standard", label: "Standard (1 copy)", minAccounts: 1 },
  { value: "safe", label: "Safe (2 copies)", minAccounts: 2 },
  { value: "maximum", label: "Maximum (3 copies)", minAccounts: 3 },
];

// Mirrors the backend's inline-preview whitelist (files.views.PREVIEWABLE_IMAGE_TYPES) --
// keep in sync so the Preview button only appears when the request will actually succeed.
const PREVIEWABLE_IMAGE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/gif",
  "image/webp",
  "image/bmp",
  "image/x-icon",
]);

function isPreviewable(file: DriveFile) {
  return (
    file.status === "available" &&
    (PREVIEWABLE_IMAGE_TYPES.has(file.mime_type) || file.mime_type === "application/pdf")
  );
}

function FilesContent() {
  const { profile } = useAuth();
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [stats, setStats] = useState<FileStats>({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [type, setType] = useState<string | undefined>(undefined);
  const [category, setCategory] = useState<string | undefined>(undefined);
  const [ordering, setOrdering] = useState("-created");
  const [replication, setReplication] = useState("standard");
  const [error, setError] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [previewFile, setPreviewFile] = useState<DriveFile | null>(null);
  const [sharingFile, setSharingFile] = useState<DriveFile | null>(null);
  const [summarizingFile, setSummarizingFile] = useState<DriveFile | null>(null);
  const [categorizing, setCategorizing] = useState(false);

  const connectedAccounts = profile?.connected_accounts ?? 0;

  const loadStats = async () => {
    try {
      setStats(await api.fileStats());
    } catch {
      // Non-fatal: the type tabs just won't show counts.
    }
  };

  const load = async () => {
    setLoading(true);
    const data = await api.listFiles({ search: search || undefined, type, category, ordering });
    setFiles(data);
    setLoading(false);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type, category, ordering]);

  useEffect(() => {
    loadStats();
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    load();
  };

  const handleUploadsSettled = async () => {
    await load();
    await loadStats();
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
    if (!confirm(`Move "${file.name}" to the recycle bin?`)) return;
    await api.deleteFile(file.id);
    await load();
    await loadStats();
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

  const handleCategorize = async () => {
    setCategorizing(true);
    setError(null);
    try {
      await api.categorizeWithAI();
      setTimeout(load, 3000); // best-effort refresh once the background batches likely finish
    } catch (err) {
      setError(err instanceof ApiError ? err.body?.detail || err.message : "Categorization failed.");
    } finally {
      setCategorizing(false);
    }
  };

  return (
    <div>
      <Navbar />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold">My Files</h1>
            <Link href="/duplicates" className="text-sm text-slate-500 hover:text-brand-600 hover:underline">
              Duplicates
            </Link>
            <Link href="/analytics" className="text-sm text-slate-500 hover:text-brand-600 hover:underline">
              Analytics
            </Link>
            <Link href="/trash" className="text-sm text-slate-500 hover:text-brand-600 hover:underline">
              Recycle Bin
            </Link>
            <Link href="/ai/search" className="text-sm text-slate-500 hover:text-brand-600 hover:underline">
              Ask driveON
            </Link>
            <Link href="/ai/chat" className="text-sm text-slate-500 hover:text-brand-600 hover:underline">
              Chat with PDFs
            </Link>
          </div>
          <select
            value={replication}
            onChange={(e) => setReplication(e.target.value)}
            title="Redundancy: how many copies of each chunk to keep across your drives"
            className="rounded-md border border-slate-300 px-2 py-2 text-sm text-slate-700"
          >
            {REPLICATION_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value} disabled={connectedAccounts < opt.minAccounts}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="mt-4">
          <UploadQueue replication={replication} onSettled={handleUploadsSettled} />
        </div>

        {error && <div className="mt-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

        <div className="mt-6 flex flex-wrap gap-2">
          {TYPES.filter((t) => t.key).map((t) => (
            <div
              key={t.label}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500"
            >
              <span className="block text-sm font-semibold text-slate-900">
                {stats[t.key as string] ?? 0}
              </span>
              {t.label}
            </div>
          ))}
          <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500">
            <span className="block text-sm font-semibold text-slate-900">{stats.total ?? 0}</span>
            Total
          </div>
        </div>

        <form onSubmit={handleSearchSubmit} className="mt-6 flex flex-wrap items-center gap-2">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Try: type:pdf size:>500MB modified:last30days"
            className="w-full max-w-md rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          <select
            value={ordering}
            onChange={(e) => setOrdering(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <select
            value={category ?? ""}
            onChange={(e) => setCategory(e.target.value || undefined)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700"
          >
            {CATEGORIES.map((c) => (
              <option key={c.label} value={c.key ?? ""}>
                {c.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={handleCategorize}
            disabled={categorizing}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {categorizing ? "Categorizing..." : "Categorize with AI"}
          </button>
        </form>

        <div className="mt-4 flex flex-wrap gap-2 border-b border-slate-200">
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

        <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Size</th>
                <th className="px-4 py-3 font-medium">Modified</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Health</th>
                <th className="px-4 py-3 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                    Loading...
                  </td>
                </tr>
              ) : files.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
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
                      ) : isPreviewable(file) ? (
                        <button
                          onClick={() => setPreviewFile(file)}
                          className="text-left hover:text-brand-600 hover:underline"
                        >
                          {file.name}
                        </button>
                      ) : (
                        file.name
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-500">{formatBytes(file.size)}</td>
                    <td className="px-4 py-3 text-slate-500">{formatDate(file.updated_at)}</td>
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
                    <td className="px-4 py-3">
                      <HealthBadge health={file.health} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-3 text-slate-500">
                        {isPreviewable(file) && (
                          <button onClick={() => setPreviewFile(file)} className="hover:text-brand-600">
                            Preview
                          </button>
                        )}
                        <button onClick={() => handleDownload(file)} className="hover:text-brand-600">
                          Download
                        </button>
                        {file.mime_type === "application/pdf" && file.status === "available" && (
                          <button onClick={() => setSummarizingFile(file)} className="hover:text-brand-600">
                            Summarize
                          </button>
                        )}
                        <button onClick={() => setSharingFile(file)} className="hover:text-brand-600">
                          Share
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

      {previewFile && (
        <FilePreviewModal
          fileId={previewFile.id}
          fileName={previewFile.name}
          onClose={() => setPreviewFile(null)}
        />
      )}
      {sharingFile && (
        <ShareModal
          fileId={sharingFile.id}
          fileName={sharingFile.name}
          onClose={() => setSharingFile(null)}
        />
      )}
      {summarizingFile && (
        <SummaryModal
          fileId={summarizingFile.id}
          fileName={summarizingFile.name}
          onClose={() => setSummarizingFile(null)}
        />
      )}
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
