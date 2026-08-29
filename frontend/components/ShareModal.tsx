"use client";

import { useEffect, useState } from "react";
import { api, ApiError, FileCollaboratorEntry, ShareLink } from "@/lib/api";
import { formatDate } from "@/lib/format";

export function ShareModal({
  fileId,
  fileName,
  onClose,
}: {
  fileId: number;
  fileName: string;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<"link" | "people">("link");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4" onClick={onClose}>
      <div className="w-full max-w-lg rounded-lg bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
          <h2 className="truncate pr-4 text-sm font-medium text-slate-900">Share &quot;{fileName}&quot;</h2>
          <button onClick={onClose} className="shrink-0 text-slate-400 hover:text-slate-600" aria-label="Close">
            &#10005;
          </button>
        </div>
        <div className="flex gap-4 border-b border-slate-200 px-5">
          {(["link", "people"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`border-b-2 py-2 text-sm font-medium ${
                tab === t ? "border-brand-600 text-brand-600" : "border-transparent text-slate-500"
              }`}
            >
              {t === "link" ? "Link" : "People"}
            </button>
          ))}
        </div>
        <div className="max-h-[70vh] overflow-y-auto p-5">
          {tab === "link" ? <LinkTab fileId={fileId} /> : <PeopleTab fileId={fileId} />}
        </div>
      </div>
    </div>
  );
}

function LinkTab({ fileId }: { fileId: number }) {
  const [links, setLinks] = useState<ShareLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [password, setPassword] = useState("");
  const [expiresInDays, setExpiresInDays] = useState("");
  const [maxDownloads, setMaxDownloads] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    setLinks(await api.listShareLinks(fileId));
    setLoading(false);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCreate = async () => {
    setError(null);
    try {
      await api.createShareLink(fileId, {
        password: password || undefined,
        expires_in_days: expiresInDays ? Number(expiresInDays) : undefined,
        max_downloads: maxDownloads ? Number(maxDownloads) : undefined,
      });
      setPassword("");
      setExpiresInDays("");
      setMaxDownloads("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.body?.detail || err.message : "Couldn't create link.");
    }
  };

  const handleCopy = (link: ShareLink) => {
    if (link.url) navigator.clipboard.writeText(link.url);
    setCopiedId(link.id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const handleRevoke = async (linkId: number) => {
    await api.revokeShareLink(linkId);
    await load();
  };

  return (
    <div>
      <div className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-slate-600">Password (optional)</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
        </div>
        <div className="flex gap-3">
          <div className="flex-1">
            <label className="block text-xs font-medium text-slate-600">Expires in (days)</label>
            <input
              type="number"
              min={1}
              value={expiresInDays}
              onChange={(e) => setExpiresInDays(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
            />
          </div>
          <div className="flex-1">
            <label className="block text-xs font-medium text-slate-600">Max downloads</label>
            <input
              type="number"
              min={1}
              value={maxDownloads}
              onChange={(e) => setMaxDownloads(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
            />
          </div>
        </div>
        {error && <p className="text-xs text-red-600">{error}</p>}
        <button
          onClick={handleCreate}
          className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700"
        >
          Create link
        </button>
      </div>

      <div className="mt-5 border-t border-slate-100 pt-4">
        {loading ? (
          <p className="text-sm text-slate-500">Loading...</p>
        ) : links.length === 0 ? (
          <p className="text-sm text-slate-500">No active links yet.</p>
        ) : (
          <ul className="space-y-2">
            {links.map((link) => (
              <li
                key={link.id}
                className="flex items-center justify-between gap-3 rounded-md border border-slate-200 px-3 py-2 text-sm"
              >
                <div className="min-w-0">
                  <p className="truncate text-slate-700">{link.url}</p>
                  <p className="text-xs text-slate-400">
                    {link.download_count} download{link.download_count === 1 ? "" : "s"}
                    {link.max_downloads ? ` / ${link.max_downloads}` : ""}
                    {link.expires_at ? ` · expires ${formatDate(link.expires_at)}` : ""}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <button onClick={() => handleCopy(link)} className="text-brand-600 hover:underline">
                    {copiedId === link.id ? "Copied!" : "Copy"}
                  </button>
                  <button onClick={() => handleRevoke(link.id)} className="text-slate-500 hover:text-red-600">
                    Revoke
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function PeopleTab({ fileId }: { fileId: number }) {
  const [collaborators, setCollaborators] = useState<FileCollaboratorEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState("");
  const [role, setRole] = useState<"viewer" | "downloader">("downloader");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setCollaborators(await api.listCollaborators(fileId));
    setLoading(false);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleAdd = async () => {
    setError(null);
    if (!username.trim()) return;
    try {
      await api.addCollaborator(fileId, username.trim(), role);
      setUsername("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.body?.detail || err.message : "Couldn't add that person.");
    }
  };

  const handleRemove = async (userId: number) => {
    await api.removeCollaborator(fileId, userId);
    await load();
  };

  return (
    <div>
      <div className="flex gap-2">
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="driveON username"
          className="min-w-0 flex-1 rounded-md border border-slate-300 px-2 py-1.5 text-sm"
        />
        <select
          value={role}
          onChange={(e) => setRole(e.target.value as "viewer" | "downloader")}
          className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="downloader">Downloader</option>
          <option value="viewer">Viewer</option>
        </select>
        <button
          onClick={handleAdd}
          className="shrink-0 rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700"
        >
          Add
        </button>
      </div>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}

      <div className="mt-4">
        {loading ? (
          <p className="text-sm text-slate-500">Loading...</p>
        ) : collaborators.length === 0 ? (
          <p className="text-sm text-slate-500">Not shared with anyone yet.</p>
        ) : (
          <ul className="space-y-2">
            {collaborators.map((c) => (
              <li
                key={c.id}
                className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm"
              >
                <div>
                  <p className="text-slate-700">{c.username}</p>
                  <p className="text-xs capitalize text-slate-400">{c.role}</p>
                </div>
                <button onClick={() => handleRemove(c.user_id)} className="text-slate-500 hover:text-red-600">
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
