"use client";

import { useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { api, AISearchResponse, ApiError } from "@/lib/api";

function AISearchContent() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<AISearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await api.searchWithAI(query.trim()));
    } catch (err) {
      setError(err instanceof ApiError ? err.body?.detail || err.message : "Search failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Navbar />
      <main className="mx-auto max-w-3xl px-6 py-8">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Ask driveON</h1>
          <Link href="/files" className="text-sm text-brand-600 hover:underline">
            Back to My Files
          </Link>
        </div>
        <p className="mt-1 text-sm text-slate-500">
          Search your files with plain language, e.g. &quot;research papers about Alzheimer&apos;s from last
          month&quot;. Files without a generated summary are matched by name/type/date only.
        </p>

        <form onSubmit={handleSearch} className="mt-6 flex gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="What are you looking for?"
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {loading ? "Searching..." : "Search"}
          </button>
        </form>

        {error && <div className="mt-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

        {result && (
          <div className="mt-6">
            <p className="text-sm text-slate-500">
              {result.results.length} match{result.results.length === 1 ? "" : "es"} out of {result.considered_count}{" "}
              file{result.considered_count === 1 ? "" : "s"} considered
              {result.truncated ? " (some older files were skipped)" : ""}.
            </p>
            <ul className="mt-4 space-y-3">
              {result.results.map((r) => (
                <li key={r.file_id} className="rounded-lg border border-slate-200 bg-white p-4">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-slate-900">{r.name}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        r.relevance === "high" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                      }`}
                    >
                      {r.relevance}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-slate-500">{r.reason}</p>
                </li>
              ))}
              {result.results.length === 0 && <p className="text-sm text-slate-400">No matches found.</p>}
            </ul>
          </div>
        )}
      </main>
    </div>
  );
}

export default function AISearchPage() {
  return (
    <ProtectedRoute>
      <AISearchContent />
    </ProtectedRoute>
  );
}
