import { useCallback, useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getMetrics } from "../api";
import type { Metrics } from "../types";

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="kpi">
      <div className="kpi__value">{value}</div>
      <div className="kpi__label">{label}</div>
      {hint && <div className="kpi__hint">{hint}</div>}
    </div>
  );
}

const pct = (v: number | null) => (v == null ? "—" : `${(v * 100).toFixed(0)}%`);

export function MetricsDashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setMetrics(await getMetrics());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load metrics");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (error) return <p className="error">{error}</p>;
  if (!metrics) return <p className="muted">Loading metrics…</p>;

  const latencyData = [
    { name: "p50", ms: metrics.latency.p50_ms },
    { name: "p95", ms: metrics.latency.p95_ms },
    { name: "p99", ms: metrics.latency.p99_ms },
    { name: "max", ms: metrics.latency.max_ms },
  ];

  const scoreData = [
    { name: "faithfulness", value: metrics.scores.faithfulness_avg },
    { name: "answer rel.", value: metrics.scores.answer_relevance_avg },
    { name: "context rel.", value: metrics.scores.context_relevance_avg },
  ].filter((s) => s.value != null) as { name: string; value: number }[];

  return (
    <section className="panel dashboard">
      <div className="dashboard__head">
        <h2>Observability</h2>
        <button className="link-btn" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>

      <div className="kpis">
        <Kpi label="Total queries" value={String(metrics.total_queries)} />
        <Kpi
          label="Cache hit rate"
          value={pct(metrics.cache_hit_rate)}
          hint={`${metrics.cache_hits} hits · ${metrics.cache_size} cached`}
        />
        <Kpi label="Latency p95" value={`${metrics.latency.p95_ms.toFixed(0)} ms`} />
        <Kpi
          label="Total cost"
          value={`$${metrics.total_cost_usd.toFixed(4)}`}
          hint={`${metrics.total_tokens.toLocaleString()} tokens`}
        />
        <Kpi label="Faithfulness" value={pct(metrics.scores.faithfulness_avg)} />
        <Kpi
          label="Indexed"
          value={String(metrics.documents_indexed)}
          hint={`${metrics.chunks_indexed} chunks`}
        />
      </div>

      <div className="charts">
        <div className="chart-card">
          <h3>Latency (ms)</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={latencyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="ms" fill="#4f46e5" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <h3>Quality scores</h3>
          {scoreData.length === 0 ? (
            <p className="muted">
              No eval scores yet. Run the evaluation suite or ask some questions.
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={scoreData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                <XAxis dataKey="name" />
                <YAxis domain={[0, 1]} />
                <Tooltip formatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {scoreData.map((_, i) => (
                    <Cell key={i} fill={["#10b981", "#3b82f6", "#f59e0b"][i % 3]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="chart-card chart-card--wide">
          <h3>Query volume by day</h3>
          {metrics.volume_by_day.length === 0 ? (
            <p className="muted">No queries recorded yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={metrics.volume_by_day}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                <XAxis dataKey="day" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </section>
  );
}
