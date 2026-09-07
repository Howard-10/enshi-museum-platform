export interface SystemReadinessResponse {
  retrieval_mode: string;
  external_model_calls_enabled: boolean;
  vector_search_enabled: boolean;
  chat_generation_enabled: boolean;
  reranker_enabled: boolean;
  web_search_enabled: boolean;
  web_search_provider: string;
  web_search_monthly_request_limit: number;
  web_search_max_requests_per_answer: number;
  web_search_allowed_domains: string[];
  missing_embedding_fields: string[];
  missing_chat_fields: string[];
  missing_reranker_fields: string[];
  documents: number;
  child_chunks: number;
  catalog_artifacts: number;
  media_assets: number;
  approved_document_links: number;
}
