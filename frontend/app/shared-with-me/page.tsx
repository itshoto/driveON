"use client";

import { useEffect, useState } from "react";
import { Navbar } from "@/components/Navbar";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { FilePreviewModal } from "@/components/FilePreviewModal";
import { HealthBadge } from "@/components/HealthBadge";
import { api, ApiError, SharedFile } from "@/lib/api";
import { formatBytes, formatDate } from "@/lib/format";

const PREVIEWABLE_IMAGE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/gif",
  "image/webp",
  "image/bmp",
  "image/x-icon",
]);

function isPreviewable(file: SharedFile) {
  return (
    file.status === "available" &&
    (PREVIEWABLE_IMAGE_TYPES.has(file.mime_type) || file.mime_type === "application/pdf")
  );
}

function SharedWithMeContent() {
  const [files, setFiles] = useState<SharedFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewFile, setPreviewFile] = useState<SharedFile | null>(null);

  useEffect(() => {
    (async () => {
      setFiles(await api.listSharedWithMe());
      setLoading(false);
    })();
  }, []);

  const handleDownload = async (file: SharedFile) => {
    setError(null);
    try {
      await api.downloadFile(file.id, file.name);
    } catch (err) {
      setError(err instanceof ApiError ? err.body?.detail || err.message : "Download failed.");
    }
  };

  return (
    <div>
      <Navbar />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <h1 className="text-2xl font-semibold">Shared with Me</h1>
        {error && <div className="mt-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

        <div className="mt-6 overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Size</th>
                <th className="px-4 py-3 font-medium">Modified</th>
                <th className="px-4 py-3 font-medium">Health</th>
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
                    No one has shared a file with you yet.
                  </td>
                </tr>
              ) : (
                files.map((file) => (
                  <tr key={file.id}>
                    <td className="px-4 py-3">
                      {isPreviewable(file) ? (
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
    </div>
  );
}

export default function SharedWithMePage() {
  return (
    <ProtectedRoute>
      <SharedWithMeContent />
    </ProtectedRoute>
  );
}
