import { useState } from "react";
import { askQuestion } from "../api";
import type { DocumentOut, QueryResponse } from "../types";

interface Turn {
  question: string;
  response: QueryResponse;
}

export function ChatPanel({
  documents,
  indexedCount,
}: {
  documents: DocumentOut[];
  indexedCount: number;
}) {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q || loading) return;
    setError(null);
    setLoading(true);
    try {
      const response = await askQuestion(q);
      setTurns((prev) => [{ question: q, response }, ...prev]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel chat">
      <form className="chat__form" onSubmit={submit}>
        <input
          type="text"
          value={question}
          placeholder={
            indexedCount === 0
              ? "Upload & index a document first…"
              : "Ask a question about your documents…"
          }
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button type="submit" disabled={loading || !question.trim()}>
          {loading ? "Thinking…" : "Ask"}
        </button>
      </form>

      {indexedCount === 0 && documents.length > 0 && (
        <p className="muted">Documents are still indexing — hang tight.</p>
      )}
      {error && <p className="error">{error}</p>}

      <div className="chat__turns">
        {turns.map((turn, i) => (
          <Answer key={turns.length - i} turn={turn} />
        ))}
      </div>
    </section>
  );
}

function Answer({ turn }: { turn: Turn }) {
  const { response: r } = turn;
  return (
    <article className="answer">
      <p className="answer__question">{turn.question}</p>
      <p className="answer__text">{r.answer}</p>

      <div className="answer__meta">
        {r.cache_hit ? (
          <span className="chip chip--cache" title={`similarity ${r.similarity ?? ""}`}>
            cache hit{r.similarity ? ` · ${(r.similarity * 100).toFixed(0)}%` : ""}
          </span>
        ) : (
          <span className="chip">{r.model}</span>
        )}
        <span className="chip">{r.latency_ms.toFixed(0)} ms</span>
        {!r.cache_hit && <span className="chip">{r.total_tokens} tok</span>}
        {!r.cache_hit && (
          <span className="chip">${r.estimated_cost_usd.toFixed(6)}</span>
        )}
        {r.context_relevance != null && (
          <span className="chip" title="mean retrieval similarity">
            ctx {(r.context_relevance * 100).toFixed(0)}%
          </span>
        )}
      </div>

      {r.citations.length > 0 && (
        <div className="citations">
          <h4>Sources</h4>
          {r.citations.map((c) => (
            <details
              key={c.chunk_id}
              className={`citation ${c.cited ? "citation--cited" : ""}`}
            >
              <summary>
                <span className="citation__marker">[{c.marker}]</span>
                <span className="citation__file">
                  {c.filename}
                  {c.page ? ` · p.${c.page}` : ""}
                </span>
                <span className="citation__score">{(c.score * 100).toFixed(0)}%</span>
                {c.cited && <span className="citation__used">cited</span>}
              </summary>
              <p className="citation__content">{c.content}</p>
            </details>
          ))}
        </div>
      )}
    </article>
  );
}
