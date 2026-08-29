"use client";

import { useEffect, useState } from "react";
import { UploadProgress } from "./UploadProgress";
import { api, ApiError } from "@/lib/api";
import { formatBytes } from "@/lib/format";

type QueueItem = {
  key: string;
  file: File;
  status: "waiting" | "uploading" | "processing" | "error";
  browserPct: number;
  driveFileId?: number;
  error?: string;
};

const CONCURRENCY = 2;

export function UploadQueue({ replication, onSettled }: { replication: string; onSettled: () => void }) {
  const [items, setItems] = useState<QueueItem[]>([]);

  const patchItem = (key: string, patch: Partial<QueueItem>) =>
    setItems((prev) => prev.map((it) => (it.key === key ? { ...it, ...patch } : it)));

  useEffect(() => {
    const active = items.filter((it) => it.status === "uploading" || it.status === "processing").length;
    const waiting = items.filter((it) => it.status === "waiting").slice(0, Math.max(0, CONCURRENCY - active));
    waiting.forEach((item) => {
      patchItem(item.key, { status: "uploading" });
      api
        .uploadFile(item.file, (pct) => patchItem(item.key, { browserPct: pct }), replication)
        .then((created) => patchItem(item.key, { status: "processing", driveFileId: created.id, browserPct: 100 }))
        .catch((err) =>
          patchItem(item.key, {
            status: "error",
            error: err instanceof ApiError ? err.body?.detail || err.message : "Upload failed.",
          })
        );
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items]);

  const enqueue = (files: FileList | File[]) => {
    const newItems: QueueItem[] = Array.from(files).map((file) => ({
      key: `${Date.now()}-${Math.random().toString(36).slice(2)}-${file.name}`,
      file,
      status: "waiting",
      browserPct: 0,
    }));
    setItems((prev) => [...prev, ...newItems]);
  };

  const handleDone = (key: string) => {
    setItems((prev) => prev.filter((it) => it.key !== key));
    onSettled();
  };

  const dismiss = (key: string) => setItems((prev) => prev.filter((it) => it.key !== key));

  return (
    <div className="space-y-3">
      <DropZone onFiles={enqueue} compact={items.length > 0} />
      {items.map((item) => (
        <div key={item.key} className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate font-medium text-slate-700">{item.file.name}</span>
            <span className="shrink-0 text-xs text-slate-400">{formatBytes(item.file.size)}</span>
          </div>
          {item.status === "waiting" && <p className="mt-1 text-xs text-slate-500">Waiting...</p>}
          {item.status === "uploading" && (
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-brand-500" style={{ width: `${item.browserPct}%` }} />
            </div>
          )}
          {item.status === "processing" && item.driveFileId && (
            <div className="mt-2">
              <UploadProgress fileId={item.driveFileId} onDone={() => handleDone(item.key)} />
            </div>
          )}
          {item.status === "error" && (
            <div className="mt-1 flex items-center justify-between text-xs text-red-600">
              <span>{item.error}</span>
              <button onClick={() => dismiss(item.key)} className="text-slate-400 hover:text-slate-600">
                Dismiss
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function DropZone({ onFiles, compact = false }: { onFiles: (files: FileList) => void; compact?: boolean }) {
  const [dragging, setDragging] = useState(false);

  return (
    <label
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (e.dataTransfer.files.length) onFiles(e.dataTransfer.files);
      }}
      className={`flex cursor-pointer items-center justify-center rounded-md border-2 border-dashed text-sm transition-colors ${
        dragging
          ? "border-brand-500 bg-brand-50 text-brand-700"
          : "border-slate-300 text-slate-500 hover:border-slate-400"
      } ${compact ? "px-4 py-2" : "px-4 py-8"}`}
    >
      {compact ? "Drop more files here, or click to browse" : "Drag files here, or click to browse"}
      <input
        type="file"
        multiple
        className="hidden"
        onChange={(e) => {
          if (e.target.files?.length) onFiles(e.target.files);
          e.target.value = "";
        }}
      />
    </label>
  );
}
