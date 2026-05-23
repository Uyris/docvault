// Thin API client. Uses same-origin relative paths by default (dev proxy /
// nginx handle routing to the backend); override with VITE_API_BASE for a
// separately-deployed backend.

import type { DocumentOut, Metrics, QueryResponse } from "./types";

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export async function listDocuments(): Promise<DocumentOut[]> {
  return handle(await fetch(`${BASE}/api/documents`));
}

export async function uploadDocument(file: File): Promise<{ document: DocumentOut }> {
  const form = new FormData();
  form.append("file", file);
  return handle(await fetch(`${BASE}/api/documents`, { method: "POST", body: form }));
}

export async function deleteDocument(id: string): Promise<void> {
  const res = await fetch(`${BASE}/api/documents/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete (${res.status})`);
}

export async function askQuestion(
  question: string,
  documentIds?: string[],
): Promise<QueryResponse> {
  return handle(
    await fetch(`${BASE}/api/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        document_ids: documentIds && documentIds.length ? documentIds : null,
      }),
    }),
  );
}

export async function getMetrics(): Promise<Metrics> {
  return handle(await fetch(`${BASE}/api/metrics`));
}
