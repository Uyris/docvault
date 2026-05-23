import { useRef, useState } from "react";
import { deleteDocument, uploadDocument } from "../api";
import type { DocStatus, DocumentOut } from "../types";

const STATUS_LABEL: Record<DocStatus, string> = {
  pending: "Queued",
  processing: "Indexing…",
  indexed: "Indexed",
  failed: "Failed",
};

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function DocumentsPanel({
  documents,
  onChange,
}: {
  documents: DocumentOut[];
  onChange: () => Promise<void>;
}) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setError(null);
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        await uploadDocument(file);
      }
      await onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteDocument(id);
      await onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  return (
    <section className="panel">
      <div className="uploader">
        <label className="uploader__drop">
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.txt,.md,.markdown"
            multiple
            disabled={uploading}
            onChange={(e) => void handleFiles(e.target.files)}
          />
          <strong>{uploading ? "Uploading…" : "Choose files to upload"}</strong>
          <span className="muted">PDF, TXT or Markdown · indexed in the background</span>
        </label>
      </div>

      {error && <p className="error">{error}</p>}

      {documents.length === 0 ? (
        <p className="muted empty">No documents yet. Upload one to start asking questions.</p>
      ) : (
        <table className="doc-table">
          <thead>
            <tr>
              <th>File</th>
              <th>Status</th>
              <th>Chunks</th>
              <th>Size</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {documents.map((d) => (
              <tr key={d.id}>
                <td className="doc-table__name" title={d.filename}>
                  {d.filename}
                </td>
                <td>
                  <span className={`status status--${d.status}`}>
                    {STATUS_LABEL[d.status]}
                  </span>
                  {d.status === "failed" && d.error ? (
                    <div className="error-detail" title={d.error}>
                      {d.error}
                    </div>
                  ) : null}
                </td>
                <td>{d.num_chunks}</td>
                <td>{humanSize(d.size_bytes)}</td>
                <td>
                  <button className="link-btn" onClick={() => void handleDelete(d.id)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
