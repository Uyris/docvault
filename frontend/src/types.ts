// Mirrors the backend Pydantic schemas (app/schemas).

export type DocStatus = "pending" | "processing" | "indexed" | "failed";

export interface DocumentOut {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: DocStatus;
  error: string | null;
  num_chunks: number;
  num_chars: number;
  created_at: string;
}

export interface Citation {
  marker: number;
  cited: boolean;
  document_id: string;
  filename: string;
  chunk_id: string;
  page: number | null;
  char_start: number;
  char_end: number;
  score: number;
  content: string;
}

export interface QueryResponse {
  answer: string;
  citations: Citation[];
  cache_hit: boolean;
  similarity: number | null;
  latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  model: string;
  num_contexts: number;
  context_relevance: number | null;
  query_log_id: string | null;
}

export interface Metrics {
  total_queries: number;
  cache_hits: number;
  cache_hit_rate: number;
  total_cost_usd: number;
  avg_cost_per_query_usd: number;
  total_tokens: number;
  latency: {
    avg_ms: number;
    p50_ms: number;
    p95_ms: number;
    p99_ms: number;
    max_ms: number;
  };
  scores: {
    faithfulness_avg: number | null;
    answer_relevance_avg: number | null;
    context_relevance_avg: number | null;
  };
  volume_by_day: { day: string; count: number }[];
  documents_indexed: number;
  chunks_indexed: number;
  cache_size: number;
  generated_at: string;
}
