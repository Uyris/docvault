import { useCallback, useEffect, useState } from "react";
import { listDocuments } from "./api";
import { ChatPanel } from "./components/ChatPanel";
import { DocumentsPanel } from "./components/DocumentsPanel";
import { MetricsDashboard } from "./components/MetricsDashboard";
import type { DocumentOut } from "./types";

type Tab = "chat" | "documents" | "metrics";

const TABS: { id: Tab; label: string }[] = [
  { id: "chat", label: "Chat" },
  { id: "documents", label: "Documents" },
  { id: "metrics", label: "Metrics" },
];

export function App() {
  const [tab, setTab] = useState<Tab>("chat");
  const [documents, setDocuments] = useState<DocumentOut[]>([]);

  const refreshDocuments = useCallback(async () => {
    try {
      setDocuments(await listDocuments());
    } catch (err) {
      console.error("Failed to load documents", err);
    }
  }, []);

  useEffect(() => {
    void refreshDocuments();
  }, [refreshDocuments]);

  // Poll while any document is still indexing, then stop.
  useEffect(() => {
    const settling = documents.some(
      (d) => d.status === "pending" || d.status === "processing",
    );
    if (!settling) return;
    const id = setInterval(() => void refreshDocuments(), 2500);
    return () => clearInterval(id);
  }, [documents, refreshDocuments]);

  const indexedCount = documents.filter((d) => d.status === "indexed").length;

  return (
    <div className="app">
      <header className="app__header">
        <div>
          <h1>DocVault</h1>
          <p className="app__tagline">
            RAG with citations, semantic cache &amp; observability
          </p>
        </div>
        <nav className="tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={`tabs__btn ${tab === t.id ? "tabs__btn--active" : ""}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
              {t.id === "documents" && documents.length > 0 ? (
                <span className="badge">{documents.length}</span>
              ) : null}
            </button>
          ))}
        </nav>
      </header>

      <main className="app__main">
        {tab === "chat" && (
          <ChatPanel documents={documents} indexedCount={indexedCount} />
        )}
        {tab === "documents" && (
          <DocumentsPanel documents={documents} onChange={refreshDocuments} />
        )}
        {tab === "metrics" && <MetricsDashboard />}
      </main>

      <footer className="app__footer">
        <span>{indexedCount} document(s) indexed</span>
        <a href="/docs" target="_blank" rel="noreferrer">
          API docs ↗
        </a>
      </footer>
    </div>
  );
}
