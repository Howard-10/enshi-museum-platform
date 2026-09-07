import type { ChatRequest, ChatResponse, ConversationHistoryResponse } from "../types/chat";
import type { ArtifactCatalogResponse, KnowledgeSeedResponse, PopularArtifactResponse } from "../types/knowledge";
import type { SystemReadinessResponse } from "../types/system";
import type { Citation, MediaItem } from "../types/chat";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export async function sendChatMessage(payload: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error("后端暂时无法响应，请检查服务是否已启动。");
  }

  return response.json() as Promise<ChatResponse>;
}

export type VisualSearchArtifact = {
  id: string;
  name: string;
  era: string | null;
  location: string | null;
  material: string | null;
};

export type VisualSearchResponse = {
  recognized_artifact: VisualSearchArtifact | null;
  confidence: number;
  visual_note: string;
  answer: string;
  notice: string | null;
  citations: Citation[];
  media: MediaItem[];
  visual_matches: Array<{ artifact: string; source: string; score: number; backend: string }>;
};

export async function recognizeArtifactImage(file: File): Promise<VisualSearchResponse> {
  const formData = new FormData();
  formData.append("image", file);
  const response = await fetch(`${API_BASE_URL}/visual-search`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    let message = "图片识别失败，请稍后重试。";
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) message = payload.detail;
    } catch {
      // Keep the visitor-facing fallback above when the server does not return JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<VisualSearchResponse>;
}

export async function getConversationHistory(sessionId: string): Promise<ConversationHistoryResponse> {
  const response = await fetch(`${API_BASE_URL}/chat/${encodeURIComponent(sessionId)}/history`);
  if (!response.ok) {
    throw new Error("暂时无法读取对话记录，请检查后端服务。");
  }
  return response.json() as Promise<ConversationHistoryResponse>;
}

export async function getKnowledgeSeed(): Promise<KnowledgeSeedResponse> {
  const response = await fetch(`${API_BASE_URL}/knowledge/seed`);
  if (!response.ok) {
    throw new Error("暂时无法读取知识库清单，请检查后端服务。");
  }
  return response.json() as Promise<KnowledgeSeedResponse>;
}

export async function getArtifactCatalog(): Promise<ArtifactCatalogResponse> {
  const response = await fetch(`${API_BASE_URL}/knowledge/catalog`);
  if (!response.ok) {
    throw new Error("暂时无法读取文物目录，请检查后端服务。");
  }
  return response.json() as Promise<ArtifactCatalogResponse>;
}

export async function getPopularArtifacts(): Promise<PopularArtifactResponse> {
  const response = await fetch(`${API_BASE_URL}/knowledge/popular?limit=6`);
  if (!response.ok) {
    throw new Error("暂时无法读取热门文物，请检查后端服务。");
  }
  return response.json() as Promise<PopularArtifactResponse>;
}

export async function recordArtifactVisit(artifactId: string): Promise<{ artifact_id: string; view_count: number }> {
  const response = await fetch(`${API_BASE_URL}/knowledge/artifacts/${encodeURIComponent(artifactId)}/visit`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error("暂时无法记录文物访问。");
  }
  return response.json() as Promise<{ artifact_id: string; view_count: number }>;
}

export type ArtifactMedia = {
  id: string;
  artifact_name: string | null;
  original_filename: string;
  media_type: "audio" | "image" | "video";
  mime_type: string;
  byte_size: number;
  url: string;
};

export async function getArtifactMedia(artifactName: string): Promise<ArtifactMedia[]> {
  const response = await fetch(
    `${API_BASE_URL}/media?artifact=${encodeURIComponent(artifactName)}&reviewed_only=true`,
  );
  if (!response.ok) throw new Error("暂时无法读取文物关联媒体。");
  const assets = (await response.json()) as Omit<ArtifactMedia, "url">[];
  return Promise.all(
    assets.map(async (asset) => {
      const urlResponse = await fetch(`${API_BASE_URL}/media/${asset.id}/download-url`);
      if (!urlResponse.ok) throw new Error("暂时无法获取文物媒体地址。");
      const download = (await urlResponse.json()) as { url: string };
      return { ...asset, url: download.url };
    }),
  );
}

export async function getSystemReadiness(): Promise<SystemReadinessResponse> {
  const response = await fetch(`${API_BASE_URL}/system/readiness`);
  if (!response.ok) {
    throw new Error("暂时无法读取系统状态，请检查后端服务。");
  }
  return response.json() as Promise<SystemReadinessResponse>;
}

export type GameAudioClue = {
  id: string;
  artifact_name: string | null;
  original_filename: string;
  url: string;
};

export async function getGameAudioClue(): Promise<GameAudioClue | null> {
  const mediaResponse = await fetch(
    `${API_BASE_URL}/media?artifact=${encodeURIComponent("唐崖土司牌坊")}&media_type=audio&reviewed_only=true`,
  );
  if (!mediaResponse.ok) throw new Error("暂时无法读取馆藏声音线索。");
  const media = (await mediaResponse.json()) as Array<{
    id: string;
    artifact_name: string | null;
    original_filename: string;
  }>;
  const asset = media[0];
  if (!asset) return null;

  const urlResponse = await fetch(`${API_BASE_URL}/media/${asset.id}/download-url`);
  if (!urlResponse.ok) throw new Error("暂时无法获取馆藏声音地址。");
  const download = (await urlResponse.json()) as { url: string };
  return { ...asset, url: download.url };
}
