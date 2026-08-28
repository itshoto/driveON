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

function uploadWithProgress(file: File, onProgress?: (pct: number) => void): Promise<any> {
  return new Promise(async (resolve, reject) => {
    const headers = await authHeader();
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/files/upload`);
    Object.entries(headers).forEach(([key, value]) => xhr.setRequestHeader(key, value));
    xhr.upload.onprogress = (event) => {
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

  connectGoogle: () => request("/google/connect"),
  listGoogleAccounts: () => request("/google/accounts"),
  removeGoogleAccount: (id: number, force = false) =>
    request(`/google/accounts/${id}${force ? "?force=true" : ""}`, { method: "DELETE" }),

  storageSummary: () => request("/storage/summary"),

  listFiles: (params?: { search?: string; type?: string }) => {
    const qs = new URLSearchParams();
    if (params?.search) qs.set("search", params.search);
    if (params?.type) qs.set("type", params.type);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request(`/files${suffix}`);
  },
  uploadFile: (file: File, onProgress?: (pct: number) => void) => uploadWithProgress(file, onProgress),
  renameFile: (id: number, name: string) =>
    request(`/files/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  deleteFile: (id: number) => request(`/files/${id}`, { method: "DELETE" }),
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
};
