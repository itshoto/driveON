export type FileHealth = {
  status: "healthy" | "at_risk" | "unavailable";
  chunks_available: number;
  chunks_total: number;
};

const CONFIG: Record<FileHealth["status"], { dot: string; label: string }> = {
  healthy: { dot: "bg-emerald-500", label: "Healthy" },
  at_risk: { dot: "bg-amber-500", label: "At risk" },
  unavailable: { dot: "bg-red-500", label: "Unavailable" },
};

export function HealthBadge({ health }: { health: FileHealth }) {
  const config = CONFIG[health.status];
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs text-slate-600"
      title={`${health.chunks_available}/${health.chunks_total} chunks available`}
    >
      <span className={`h-2 w-2 shrink-0 rounded-full ${config.dot}`} />
      {config.label}
      <span className="text-slate-400">
        ({health.chunks_available}/{health.chunks_total})
      </span>
    </span>
  );
}
