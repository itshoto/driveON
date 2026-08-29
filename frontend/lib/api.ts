import { auth } from "./firebase";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

async function authHeader(): Promise<Record<string, string>> {
  const user = auth.currentUser;
  if (!user) return {};
  const token = await user.getIdToken();
  return { Authorization: `Bearer ${token}` };
}

export class ApiError extends Error {
  status: number;
  body: any;
  constructor(status: number, body: any) {
    super(body?.detail || `Request failed with status ${status}`);
    this.status = status;
    this.body = body;
  }
}

async function request(path: string, options: RequestInit = {}) {
  const headers = {
    ...(await authHeader()),
    ...(options.headers || {}),
  };
  const res = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    let body: any = null;
    try {
      body = await res.json();
    } catch {
      // no JSON body
    }
    throw new ApiError(res.status, body);
  }
  if (res.status === 204) return null;
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return res.json();
  return res;
}

function uploadWithProgress(
  file: File,
  onProgress?: (pct: number) => void,
  replication?: string
): Promise<any> {
  return new Promise(async (resolve, reject) => {
    const headers = await authHeader();
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/files/upload`);
    Object.entries(headers).forEach(([key, value]) => xhr.setRequestHeader(key, value));
    xhr.upload.onprogress = (event) => {
      // This tracks only the browser -> driveON leg. Once it hits 100%
      // the file is still being split and uploaded to Google Drive in
      // the background -- see api.getUploadStatus for that second leg.
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.responseText ? JSON.parse(xhr.responseText) : null);
      } else {
        let body: any = null;
        try {
          body = JSON.parse(xhr.responseText);
        } catch {
          // no JSON body
        }
        reject(new ApiError(xhr.status, body));
      }
    };
    xhr.onerror = () => reject(new Error("Network error during upload"));
    const formData = new FormData();
    formData.append("file", file);
    if (replication) formData.append("replication", replication);
    xhr.send(formData);
  });
}

export const api = {
  syncUser: (username?: string) =>
    request("/auth/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(username ? { username } : {}),
    }),
  me: () => request("/auth/me"),
  deleteAccount: (confirmation: string) =>
    request("/auth/me", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmation }),
    }),

  connectAccount: (provider: "google" | "microsoft") => request(`/accounts/connect/${provider}`),
  listAccounts: (): Promise<StorageAccount[]> => request("/accounts"),
  removeAccount: (id: number, force = false) =>
    request(`/accounts/${id}${force ? "?force=true" : ""}`, { method: "DELETE" }),

  storageSummary: (): Promise<StorageSummary> => request("/storage/summary"),

  listFiles: (params?: { search?: string; type?: string; category?: string; ordering?: string }) => {
    const qs = new URLSearchParams();
    if (params?.search) qs.set("search", params.search);
    if (params?.type) qs.set("type", params.type);
    if (params?.category) qs.set("category", params.category);
    if (params?.ordering) qs.set("ordering", params.ordering);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request(`/files${suffix}`);
  },
  fileStats: (): Promise<FileStats> => request("/files/stats"),
  listDuplicates: (): Promise<DuplicatesResponse> => request("/files/duplicates"),
  uploadFile: (file: File, onProgress?: (pct: number) => void, replication?: string) =>
    uploadWithProgress(file, onProgress, replication),
  getUploadStatus: (id: number): Promise<UploadStatus> => request(`/files/${id}/upload-status`),
  renameFile: (id: number, name: string) =>
    request(`/files/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  deleteFile: (id: number) => request(`/files/${id}`, { method: "DELETE" }),
  listTrash: (): Promise<TrashedFile[]> => request("/files/trash"),
  restoreFile: (id: number) => request(`/files/${id}/restore`, { method: "POST" }),
  purgeFile: (id: number) => request(`/files/${id}/purge`, { method: "DELETE" }),
  downloadFile: async (id: number, filename: string) => {
    const headers = await authHeader();
    const res = await fetch(`${API_BASE_URL}/files/${id}/download`, { headers });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new ApiError(res.status, body);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },
  previewFile: async (id: number): Promise<{ objectUrl: string; contentType: string }> => {
    const headers = await authHeader();
    const res = await fetch(`${API_BASE_URL}/files/${id}/preview`, { headers });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new ApiError(res.status, body);
    }
    const blob = await res.blob();
    return { objectUrl: URL.createObjectURL(blob), contentType: res.headers.get("content-type") || blob.type };
  },

  checkRebalance: (): Promise<RebalanceCheck> => request("/storage/rebalance/check"),
  triggerRebalance: (): Promise<{ run_id: number }> => request("/storage/rebalance/trigger", { method: "POST" }),
  getRebalanceStatus: (runId: number): Promise<RebalanceStatus> => request(`/storage/rebalance/status/${runId}`),

  listNotifications: (): Promise<NotificationItem[]> => request("/notifications"),
  unreadNotificationCount: (): Promise<{ count: number }> => request("/notifications/unread-count"),
  markNotificationRead: (id: number) => request(`/notifications/${id}/read`, { method: "POST" }),
  markAllNotificationsRead: () => request("/notifications/read-all", { method: "POST" }),
  getNotificationPreferences: (): Promise<NotificationPreferences> => request("/notifications/preferences"),
  updateNotificationPreferences: (prefs: Partial<NotificationPreferences>) =>
    request("/notifications/preferences", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(prefs),
    }),

  createShareLink: (
    fileId: number,
    opts: { password?: string; expires_in_days?: number; max_downloads?: number }
  ): Promise<ShareLink> =>
    request(`/sharing/files/${fileId}/links`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(opts),
    }),
  listShareLinks: (fileId: number): Promise<ShareLink[]> => request(`/sharing/files/${fileId}/links`),
  revokeShareLink: (linkId: number) => request(`/sharing/links/${linkId}`, { method: "DELETE" }),

  getPublicShare: (token: string): Promise<PublicShareInfo> => request(`/sharing/public/${token}`),
  unlockPublicShare: (token: string, password: string): Promise<PublicShareUnlocked> =>
    request(`/sharing/public/${token}/unlock`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    }),
  downloadPublicShare: async (token: string, filename: string, dl?: string) => {
    const suffix = dl ? `?dl=${encodeURIComponent(dl)}` : "";
    const res = await fetch(`${API_BASE_URL}/sharing/public/${token}/download${suffix}`);
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new ApiError(res.status, body);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },

  listSharedWithMe: (): Promise<SharedFile[]> => request("/sharing/shared-with-me"),
  listCollaborators: (fileId: number): Promise<FileCollaboratorEntry[]> =>
    request(`/sharing/files/${fileId}/collaborators`),
  addCollaborator: (fileId: number, username: string, role: string): Promise<FileCollaboratorEntry> =>
    request(`/sharing/files/${fileId}/collaborators`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, role }),
    }),
  removeCollaborator: (fileId: number, userId: number) =>
    request(`/sharing/files/${fileId}/collaborators/${userId}`, { method: "DELETE" }),

  getAIQuota: (): Promise<AIQuota> => request("/ai/quota"),
  getFileSummary: (fileId: number): Promise<AISummaryResponse> => request(`/ai/files/${fileId}/summary`),
  requestFileSummary: (fileId: number): Promise<AISummaryResponse> =>
    request(`/ai/files/${fileId}/summary`, { method: "POST" }),

  listConversations: (): Promise<AIConversationSummary[]> => request("/ai/conversations"),
  createConversation: (fileIds: number[]): Promise<AIConversationSummary> =>
    request("/ai/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_ids: fileIds }),
    }),
  getConversation: (id: number): Promise<AIConversationDetail> => request(`/ai/conversations/${id}`),
  deleteConversation: (id: number) => request(`/ai/conversations/${id}`, { method: "DELETE" }),
  sendChatMessage: (
    conversationId: number,
    content: string
  ): Promise<{ message: AIMessageItem; quota: AIQuota }> =>
    request(`/ai/conversations/${conversationId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    }),

  searchWithAI: (query: string): Promise<AISearchResponse> =>
    request("/ai/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    }),
  categorizeWithAI: (fileIds?: number[]): Promise<{ status: string; batches: number }> =>
    request("/ai/categorize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fileIds ? { file_ids: fileIds } : {}),
    }),
};

export type StorageAccount = {
  id: number;
  provider: "google" | "microsoft";
  email: string;
  display_name: string;
  storage_total: number;
  storage_used: number;
  storage_available: number;
  status: string;
  quota_checked_at: string | null;
  created_at: string;
};

export type UploadStatus = {
  status: string;
  bytes_total: number;
  bytes_transferred: number;
  chunks_available: number;
  chunks_total: number;
  accounts: {
    account_id: number;
    email: string;
    provider: "google" | "microsoft";
    bytes_transferred: number;
    bytes_total: number;
  }[];
};

export type StorageSummary = {
  total: number;
  used: number;
  available: number;
  accounts: StorageAccount[];
};

export type FileStats = Record<string, number> & { sizes?: Record<string, number> };

export type DriveFileSummary = {
  id: number;
  name: string;
  mime_type: string;
  size: number;
  status: string;
  created_at: string;
  updated_at: string;
};

export type DuplicatesResponse = {
  groups: { files: DriveFileSummary[]; reclaimable_bytes: number }[];
  total_reclaimable_bytes: number;
};

export type TrashedFile = {
  id: number;
  name: string;
  mime_type: string;
  size: number;
  status: string;
  deleted_at: string;
  purge_at: string;
};

export type NotificationItem = {
  id: number;
  category: "upload" | "account" | "rebalance";
  level: "info" | "warning" | "critical";
  title: string;
  body: string;
  link: string;
  is_read: boolean;
  created_at: string;
};

export type NotificationPreferences = {
  email_upload: boolean;
  email_account: boolean;
  email_rebalance: boolean;
};

export type RebalanceAccountSummary = {
  id: number;
  email: string;
  usage_ratio: number;
  storage_used: number;
  storage_total: number;
};

export type RebalanceCheck = {
  imbalanced: boolean;
  delta?: number;
  fullest_account?: RebalanceAccountSummary;
  emptiest_account?: RebalanceAccountSummary;
};

export type RebalanceStatus = {
  status: "running" | "completed" | "failed";
  chunks_planned: number;
  chunks_moved: number;
  errors_count: number;
};

export type ShareLink = {
  id: number;
  token: string;
  url?: string;
  expires_at: string | null;
  max_downloads: number | null;
  download_count: number;
  revoked_at: string | null;
  created_at: string;
};

export type PublicShareInfo = {
  requires_password: boolean;
  name: string;
  size?: number;
  mime_type?: string;
};

export type PublicShareUnlocked = {
  dl: string;
  name: string;
  size: number;
  mime_type: string;
};

export type SharedFile = {
  id: number;
  name: string;
  mime_type: string;
  size: number;
  status: string;
  health: { status: "healthy" | "at_risk" | "unavailable"; chunks_available: number; chunks_total: number };
  created_at: string;
  updated_at: string;
};

export type FileCollaboratorEntry = {
  id: number;
  user_id: number;
  username: string;
  email: string;
  role: "viewer" | "downloader";
  created_at: string;
};

export type AIQuota = { used: number; limit: number };

export type AISummaryResponse = {
  file_id: number;
  status: "processing" | "ready";
  model?: string;
  generated_at?: string;
  detail?: string;
  summary?: {
    key_findings: string[];
    methodology: string;
    dataset: string;
    limitations: string[];
    keywords: string[];
  };
};

export type AIConversationSummary = {
  id: number;
  title: string;
  file_ids: number[];
  created_at: string;
  updated_at: string;
};

export type AIMessageItem = {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type AIConversationDetail = AIConversationSummary & { messages: AIMessageItem[] };

export type AISearchResultItem = {
  file_id: number;
  name: string;
  relevance: "high" | "medium" | "low";
  reason: string;
};

export type AISearchResponse = {
  query: string;
  results: AISearchResultItem[];
  considered_count: number;
  truncated: boolean;
};
