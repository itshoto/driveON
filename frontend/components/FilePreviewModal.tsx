"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";

export function FilePreviewModal({
  fileId,
  fileName,
  onClose,
}: {
  fileId: number;
  fileName: string;
  onClose: () => void;
}) {
  const [preview, setPreview] = useState<{ objectUrl: string; contentType: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    api
      .previewFile(fileId)
      .then((result) => {
        if (cancelled) {
          URL.revokeObjectURL(result.objectUrl);
          return;
        }
        objectUrl = result.objectUrl;
        setPreview(result);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.body?.detail || err.message : "Couldn't load preview.");
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [fileId]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-lg bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <h2 className="truncate pr-4 text-sm font-medium text-slate-900">{fileName}</h2>
          <button onClick={onClose} className="shrink-0 text-slate-400 hover:text-slate-600" aria-label="Close">
            &#10005;
          </button>
        </div>
        <div className="flex flex-1 items-center justify-center overflow-auto bg-slate-100 p-4">
          {error ? (
            <p className="max-w-sm text-center text-sm text-red-600">{error}</p>
          ) : !preview ? (
            <p className="text-sm text-slate-500">Loading preview...</p>
          ) : preview.contentType.startsWith("image/") ? (
            <img
              src={preview.objectUrl}
              alt={fileName}
              className="max-h-[75vh] max-w-full object-contain"
            />
          ) : (
            <iframe src={preview.objectUrl} title={fileName} className="h-[75vh] w-full border-0" />
          )}
        </div>
      </div>
    </div>
  );
}
