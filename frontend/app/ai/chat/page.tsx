"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { api, AIConversationDetail, AIConversationSummary, ApiError, DriveFileSummary } from "@/lib/api";

const MAX_CHAT_FILES = 5;

function ChatContent() {
  const [conversations, setConversations] = useState<AIConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [detail, setDetail] = useState<AIConversationDetail | null>(null);
  const [pdfs, setPdfs] = useState<DriveFileSummary[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [showPicker, setShowPicker] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadConversations = async () => {
    setConversations(await api.listConversations());
  };

  useEffect(() => {
    loadConversations();
    api.listFiles({ type: "pdf" }).then((files: DriveFileSummary[]) => setPdfs(files));
  }, []);

  const openConversation = async (id: number) => {
    setShowPicker(false);
    setActiveId(id);
    setDetail(await api.getConversation(id));
  };

  const handleCreate = async () => {
    if (selectedIds.length === 0) return;
    setError(null);
    try {
      const conversation = await api.createConversation(selectedIds);
      setSelectedIds([]);
      await loadConversations();
      await openConversation(conversation.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.body?.detail || err.message : "Couldn't start the conversation.");
    }
  };

  const handleSend = async () => {
    if (!activeId || !input.trim() || sending) return;
    const content = input.trim();
    setInput("");
    setSending(true);
    setError(null);
    setDetail((prev) =>
      prev
        ? { ...prev, messages: [...prev.messages, { id: -Date.now(), role: "user", content, created_at: new Date().toISOString() }] }
        : prev
    );
    try {
      const { message } = await api.sendChatMessage(activeId, content);
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              messages: [
                ...prev.messages,
                { id: -Date.now() - 1, role: "assistant", content: message.content, created_at: new Date().toISOString() },
              ],
            }
          : prev
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.body?.detail || err.message : "Message failed.");
    } finally {
      setSending(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this conversation?")) return;
    await api.deleteConversation(id);
    if (activeId === id) {
      setActiveId(null);
      setDetail(null);
    }
    await loadConversations();
  };

  return (
    <div>
      <Navbar />
      <main className="mx-auto flex max-w-6xl gap-6 px-6 py-8">
        <aside className="w-64 shrink-0">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-slate-500">Conversations</h2>
            <button
              onClick={() => {
                setShowPicker(true);
                setActiveId(null);
                setDetail(null);
              }}
              className="text-xs text-brand-600 hover:underline"
            >
              + New
            </button>
          </div>
          <ul className="mt-3 space-y-1">
            {conversations.map((c) => (
              <li key={c.id}>
                <button
                  onClick={() => openConversation(c.id)}
                  className={`w-full truncate rounded-md px-2 py-1.5 text-left text-sm ${
                    activeId === c.id ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {c.title || "Conversation"}
                </button>
              </li>
            ))}
            {conversations.length === 0 && <p className="text-sm text-slate-400">No conversations yet.</p>}
          </ul>
        </aside>

        <section className="min-w-0 flex-1">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-semibold">Chat with your PDFs</h1>
            <Link href="/files" className="text-sm text-brand-600 hover:underline">
              Back to My Files
            </Link>
          </div>
          {error && <div className="mt-3 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

          {showPicker && (
            <div className="mt-4 rounded-lg border border-slate-200 bg-white p-4">
              <p className="text-sm font-medium text-slate-700">Pick up to {MAX_CHAT_FILES} PDFs</p>
              <div className="mt-2 max-h-48 space-y-1 overflow-y-auto">
                {pdfs.map((pdf) => (
                  <label key={pdf.id} className="flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(pdf.id)}
                      onChange={(e) =>
                        setSelectedIds((prev) =>
                          e.target.checked ? [...prev, pdf.id].slice(-MAX_CHAT_FILES) : prev.filter((id) => id !== pdf.id)
                        )
                      }
                    />
                    {pdf.name}
                  </label>
                ))}
                {pdfs.length === 0 && <p className="text-sm text-slate-400">No PDFs uploaded yet.</p>}
              </div>
              <div className="mt-3 flex gap-2">
                <button
                  onClick={handleCreate}
                  disabled={selectedIds.length === 0}
                  className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                >
                  Start chat
                </button>
                <button
                  onClick={() => setShowPicker(false)}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {!showPicker && detail && (
            <div className="mt-4 flex h-[60vh] flex-col rounded-lg border border-slate-200 bg-white">
              <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2">
                <p className="truncate text-sm font-medium text-slate-700">{detail.title}</p>
                <button onClick={() => handleDelete(detail.id)} className="text-xs text-slate-400 hover:text-red-600">
                  Delete
                </button>
              </div>
              <div className="flex-1 space-y-3 overflow-y-auto p-4">
                {detail.messages.map((m) => (
                  <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div
                      className={`max-w-[80%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${
                        m.role === "user" ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {m.content}
                    </div>
                  </div>
                ))}
                {sending && <p className="text-xs text-slate-400">Thinking...</p>}
              </div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSend();
                }}
                className="flex gap-2 border-t border-slate-100 p-3"
              >
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask a question about these PDFs..."
                  className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
                <button
                  type="submit"
                  disabled={sending || !input.trim()}
                  className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                >
                  Send
                </button>
              </form>
            </div>
          )}

          {!showPicker && !detail && (
            <p className="mt-8 text-sm text-slate-500">
              Select a conversation, or{" "}
              <button onClick={() => setShowPicker(true)} className="text-brand-600 hover:underline">
                start a new one
              </button>
              .
            </p>
          )}
        </section>
      </main>
    </div>
  );
}

export default function ChatPage() {
  return (
    <ProtectedRoute>
      <ChatContent />
    </ProtectedRoute>
  );
}
