"use client";

import { useEffect, useRef, useState } from "react";
import { api, AISummaryResponse, ApiError } from "@/lib/api";

const POLL_INTERVAL_MS = 2000;

export function SummaryModal({
  fileId,
  fileName,
  onClose,
}: {
  fileId: number;
  fileName: string;
  onClose: () => void;
}) {
  const [data, setData] = useState<AISummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const startedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        const result = await api.getFileSummary(fileId);
        if (cancelled) return;
        setData(result);
        if (result.status === "processing") timer = setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404 && !startedRef.current) {
          startedRef.current = true;
          try {
            const started = await api.requestFileSummary(fileId);
            if (cancelled) return;
            setData(started);
            if (started.status === "processing") timer = setTimeout(poll, POLL_INTERVAL_MS);
          } catch (startErr) {
            setError(
              startErr instanceof ApiError ? startErr.body?.detail || startErr.message : "Couldn't generate a summary."
            );
          }
        } else {
          setError(err instanceof ApiError ? err.body?.detail || err.message : "Couldn't load the summary.");
        }
      }
    };

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileId]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4" onClick={onClose}>
      <div
        className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-lg bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
          <h2 className="truncate pr-4 text-sm font-medium text-slate-900">Summary: {fileName}</h2>
          <button onClick={onClose} className="shrink-0 text-slate-400 hover:text-slate-600" aria-label="Close">
            &#10005;
          </button>
        </div>
        <div className="p-5 text-sm">
          {error ? (
            <p className="text-red-600">{error}</p>
          ) : !data || data.status === "processing" ? (
            <p className="text-slate-500">Generating summary...</p>
          ) : data.summary ? (
            <div className="space-y-4">
              <div>
                <h3 className="text-xs font-semibold uppercase text-slate-500">Key Findings</h3>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-700">
                  {data.summary.key_findings.map((f, i) => (
                    <li key={i}>{f}</li>
                  ))}
                </ul>
              </div>
              {data.summary.methodology && (
                <div>
                  <h3 className="text-xs font-semibold uppercase text-slate-500">Methodology</h3>
                  <p className="mt-1 text-slate-700">{data.summary.methodology}</p>
                </div>
              )}
              {data.summary.dataset && (
                <div>
                  <h3 className="text-xs font-semibold uppercase text-slate-500">Dataset</h3>
                  <p className="mt-1 text-slate-700">{data.summary.dataset}</p>
                </div>
              )}
              {data.summary.limitations.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold uppercase text-slate-500">Limitations</h3>
                  <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-700">
                    {data.summary.limitations.map((l, i) => (
                      <li key={i}>{l}</li>
                    ))}
                  </ul>
                </div>
              )}
              {data.summary.keywords.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {data.summary.keywords.map((k) => (
                    <span key={k} className="rounded-full bg-brand-50 px-2 py-0.5 text-xs text-brand-700">
                      {k}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
