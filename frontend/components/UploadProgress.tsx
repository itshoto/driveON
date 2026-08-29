"use client";

import { useEffect, useRef, useState } from "react";
import { api, UploadStatus } from "@/lib/api";
import { formatBytes } from "@/lib/format";

const POLL_INTERVAL_MS = 1000;

export function UploadProgress({ fileId, onDone }: { fileId: number; onDone?: () => void }) {
  const [uploadStatus, setUploadStatus] = useState<UploadStatus | null>(null);
  const [speedBps, setSpeedBps] = useState(0);
  const lastSampleRef = useRef<{ bytes: number; time: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        const data = await api.getUploadStatus(fileId);
        if (cancelled) return;

        // Combined MB/s is derived client-side by diffing two polls'
        // totals over measured wall-clock time -- no server-side
        // rate-window state needed for this.
        const now = performance.now();
        if (lastSampleRef.current) {
          const elapsedSec = (now - lastSampleRef.current.time) / 1000;
          const deltaBytes = data.bytes_transferred - lastSampleRef.current.bytes;
          if (elapsedSec > 0) setSpeedBps(Math.max(0, deltaBytes / elapsedSec));
        }
        lastSampleRef.current = { bytes: data.bytes_transferred, time: now };
        setUploadStatus(data);

        if (data.status === "uploading") {
          timer = setTimeout(poll, POLL_INTERVAL_MS);
        } else {
          onDone?.();
        }
      } catch {
        if (!cancelled) timer = setTimeout(poll, POLL_INTERVAL_MS);
      }
    };

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileId]);

  if (!uploadStatus) return null;

  const overallPct = uploadStatus.bytes_total
    ? Math.min(100, Math.round((uploadStatus.bytes_transferred / uploadStatus.bytes_total) * 100))
    : 0;

  return (
    <div className="rounded-md border border-brand-100 bg-brand-50 px-4 py-3 text-sm">
      <div className="flex items-center justify-between">
        <span className="font-medium text-brand-700">
          Distributing across {uploadStatus.accounts.length} drive{uploadStatus.accounts.length === 1 ? "" : "s"}
          ... {overallPct}%
        </span>
        <span className="text-brand-600">{formatBytes(speedBps)}/s</span>
      </div>
      <div className="mt-2 space-y-1.5">
        {uploadStatus.accounts.map((account) => {
          const accountPct = account.bytes_total
            ? Math.min(100, Math.round((account.bytes_transferred / account.bytes_total) * 100))
            : 0;
          return (
            <div key={account.account_id}>
              <div className="flex justify-between text-xs text-brand-700">
                <span>{account.email}</span>
                <span>
                  {formatBytes(account.bytes_transferred)} / {formatBytes(account.bytes_total)}
                </span>
              </div>
              <div className="mt-0.5 h-1.5 w-full overflow-hidden rounded-full bg-brand-100">
                <div className="h-full rounded-full bg-brand-500" style={{ width: `${accountPct}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
