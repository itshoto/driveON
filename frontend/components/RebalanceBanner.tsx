"use client";

import { useEffect, useState } from "react";
import { api, RebalanceCheck } from "@/lib/api";

export function RebalanceBanner() {
  const [check, setCheck] = useState<RebalanceCheck | null>(null);
  const [running, setRunning] = useState(false);
  const [runId, setRunId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    api.checkRebalance().then(setCheck).catch(() => {});
  }, []);

  useEffect(() => {
    if (runId === null) return;
    let cancelled = false;

    const poll = async () => {
      const result = await api.getRebalanceStatus(runId);
      if (cancelled) return;
      if (result.status === "running") {
        setTimeout(poll, 1500);
        return;
      }
      setRunning(false);
      setRunId(null);
      setMessage(
        result.status === "completed"
          ? `Rebalanced ${result.chunks_moved} chunk${result.chunks_moved === 1 ? "" : "s"}.`
          : "Rebalancing failed. Please try again later."
      );
      api.checkRebalance().then(setCheck).catch(() => {});
    };

    poll();
    return () => {
      cancelled = true;
    };
  }, [runId]);

  const handleRebalance = async () => {
    setRunning(true);
    setMessage(null);
    try {
      const { run_id } = await api.triggerRebalance();
      setRunId(run_id);
    } catch {
      setRunning(false);
      setMessage("Couldn't start rebalancing. Please try again.");
    }
  };

  if (message) {
    return (
      <div className="mt-8 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
        {message}
      </div>
    );
  }

  if (!check?.imbalanced) return null;

  return (
    <div className="mt-8 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-amber-800">Storage imbalance detected</p>
          {check.fullest_account && check.emptiest_account && (
            <p className="mt-0.5 text-xs text-amber-700">
              {check.fullest_account.email} is {Math.round(check.fullest_account.usage_ratio * 100)}% full while{" "}
              {check.emptiest_account.email} is only {Math.round(check.emptiest_account.usage_ratio * 100)}% full.
            </p>
          )}
        </div>
        <button
          onClick={handleRebalance}
          disabled={running}
          className="shrink-0 rounded-md bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
        >
          {running ? "Rebalancing..." : "Rebalance Now"}
        </button>
      </div>
    </div>
  );
}
