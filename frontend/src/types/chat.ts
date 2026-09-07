export interface ChatRequest {
  session_id: string;
  message: string;
}

export interface Citation {
  source_type: "internal" | "external";
  id: string;
  document_id?: string | null;
  chunk_id?: string | null;
  title: string;
  url?: string | null;
  excerpt?: string | null;
}

export interface MediaItem {
  id: string;
  type: "image" | "video" | "audio" | string;
  url: string;
}

export interface ChatResponse {
  session_id: string;
  answer: string;
  intent: string;
  answer_scope: "internal_only" | "internal_plus_general" | "external_search" | "insufficient_evidence";
  unverified_extension?: string | null;
  evidence_status: "sufficient" | "insufficient" | "conflicting";
  reason_codes: string[];
  notice?: string | null;
  citations: Citation[];
  media: MediaItem[];
}

export interface ConversationMessage {
  id: string;
  sequence: number;
  role: "user" | "assistant" | string;
  content: string;
  citations: Citation[];
  media: MediaItem[];
  created_at: string;
}

export interface ConversationHistoryResponse {
  session_id: string;
  source: "redis" | "postgresql" | string;
  messages: ConversationMessage[];
}
