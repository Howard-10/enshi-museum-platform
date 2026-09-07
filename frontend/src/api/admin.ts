const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
export const ADMIN_TOKEN_KEY = "enshi-admin-token";

export type AdminSummary = {
  artifacts: number;
  documents: number;
  media_assets: number;
  approved_documents: number;
  documents_needing_review: number;
  media_links_needing_review: number;
};

export type AdminArtifact = {
  id: string;
  name: string;
  aliases: string[];
  era: string | null;
  category: string | null;
  description: string | null;
  location: string | null;
  material: string | null;
  document_count: number;
  media_count: number;
};

export type AdminDocument = {
  id: string;
  title: string;
  source_filename: string;
  mime_type: string;
  import_status: string;
  review_status: "approved" | "rejected" | "needs_review";
  review_note: string | null;
  artifact_id: string | null;
  artifact_name: string | null;
  chunk_count: number;
};

export type AdminMediaLink = {
  artifact_id: string;
  artifact_name: string;
  review_status: string;
  association_confidence: string;
};

export type AdminMedia = {
  id: string;
  original_filename: string;
  media_type: "audio" | "image" | "video";
  mime_type: string;
  byte_size: number;
  sha256: string;
  links: AdminMediaLink[];
};

export type AdminAudit = {
  id: string;
  actor: string;
  action: string;
  object_type: string;
  object_id: string | null;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  created_at: string;
};

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

async function adminFetch<T>(token: string, path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  Object.entries(authHeaders(token)).forEach(([key, value]) => headers.set(key, value));
  const response = await fetch(`${API_BASE_URL}/admin${path}`, { ...init, headers });
  if (!response.ok) {
    let message = "管理端请求失败";
    try {
      const detail = (await response.json()) as { detail?: string };
      if (detail.detail) message = detail.detail;
    } catch {
      // Keep the friendly fallback when the server did not return JSON.
    }
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function getSavedAdminToken(): string {
  try {
    return window.sessionStorage.getItem(ADMIN_TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function saveAdminToken(token: string): void {
  window.sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
}

export function clearAdminToken(): void {
  window.sessionStorage.removeItem(ADMIN_TOKEN_KEY);
}

export const getAdminSummary = (token: string) => adminFetch<AdminSummary>(token, "/summary");
export const getAdminArtifacts = (token: string) => adminFetch<AdminArtifact[]>(token, "/artifacts");
export const getAdminDocuments = (token: string) => adminFetch<AdminDocument[]>(token, "/documents");
export const getAdminMedia = (token: string) => adminFetch<AdminMedia[]>(token, "/media");
export const getAdminAudit = (token: string) => adminFetch<AdminAudit[]>(token, "/audit?limit=80");

export async function getAdminMediaDownloadUrl(mediaId: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/media/${encodeURIComponent(mediaId)}/download-url`);
  if (!response.ok) throw new Error("暂时无法获取媒体预览地址");
  const payload = (await response.json()) as { url: string };
  return payload.url;
}

export function updateAdminArtifact(token: string, id: string, payload: Partial<AdminArtifact>) {
  return adminFetch<AdminArtifact>(token, `/artifacts/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function reviewAdminDocument(token: string, id: string, review_status: AdminDocument["review_status"]) {
  return adminFetch<AdminDocument>(token, `/documents/${id}/review`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ review_status }),
  });
}

export function uploadAdminDocument(token: string, file: File, artifactId: string) {
  const body = new FormData();
  body.append("file", file);
  if (artifactId) body.append("artifact_id", artifactId);
  return adminFetch<AdminDocument>(token, "/documents/upload", { method: "POST", body });
}

export function uploadAdminMedia(token: string, file: File, artifactId: string) {
  const body = new FormData();
  body.append("file", file);
  if (artifactId) body.append("artifact_id", artifactId);
  return adminFetch<AdminMedia>(token, "/media/upload", { method: "POST", body });
}

export function linkAdminMedia(token: string, mediaId: string, artifactId: string, reviewStatus = "needs_review") {
  return adminFetch<AdminMedia>(token, `/media/${mediaId}/links`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ artifact_id: artifactId, review_status: reviewStatus, association_confidence: "manual" }),
  });
}

export function unlinkAdminMedia(token: string, mediaId: string, artifactId: string) {
  return adminFetch<void>(token, `/media/${mediaId}/links/${artifactId}`, { method: "DELETE" });
}
