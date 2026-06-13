import type { Overview } from "../api";
import { pct } from "../lib";

function Metric({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: string;
}) {
  return (
    <div className="card px-4 py-3 min-w-[150px] flex-1">
      <div className="text-[0.72rem] uppercase tracking-wide text-[var(--color-faint)]">
        {label}
      </div>
      <div className="text-2xl font-semibold mt-1" style={{ color: tone }}>
        {value}
      </div>
      {sub && <div className="text-[0.72rem] text-[var(--color-muted)] mt-0.5">{sub}</div>}
    </div>
  );
}

export function AnalyticsStrip({ ov }: { ov: Overview }) {
  const inPipeline =
    (ov.counts.shortlisted || 0) +
    (ov.counts.tailored || 0) +
    (ov.counts.ready || 0) +
    (ov.counts.applied || 0) +
    (ov.counts.responded || 0) +
    (ov.counts.interview || 0);

  const rr = ov.response_rate;
  const rrBand =
    rr == null
      ? "aún sin datos"
      : rr >= 0.1
        ? "fuerte (≥10%)"
        : rr >= 0.02
          ? "típico 2–5%"
          : "bajo";

  const max = Math.max(...ov.funnel.map((f) => f.count), 1);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-3 flex-wrap">
        <Metric
          label="En pipeline"
          value={String(inPipeline)}
          sub={`${ov.total_jobs} descubiertos`}
        />
        <Metric
          label="Listos para enviar"
          value={String(ov.ready)}
          tone="var(--color-action)"
          sub="revisa y envía"
        />
        <Metric label="Tasa de respuesta" value={pct(rr)} sub={rrBand} tone="var(--color-done)" />
        <Metric
          label="Aplicaciones"
          value={String(ov.applied)}
          sub={`entrevistas: ${ov.counts.interview || 0}`}
        />
      </div>
      <div className="card px-4 py-3">
        <div className="text-[0.72rem] uppercase tracking-wide text-[var(--color-faint)] mb-2">
          Embudo
        </div>
        <div className="flex items-end gap-2 h-16">
          {ov.funnel.map((f) => (
            <div
              key={f.stage}
              className="flex-1 flex flex-col items-center gap-1"
              title={`${f.stage}: ${f.count}`}
            >
              <div className="text-[0.7rem] text-[var(--color-muted)]">{f.count}</div>
              <div
                className="w-full rounded-t-md transition-all"
                style={{
                  height: `${Math.max((f.count / max) * 100, 4)}%`,
                  background: "linear-gradient(180deg, var(--color-accent), var(--color-accent2))",
                  opacity: 0.55 + 0.45 * (f.count / max),
                }}
              />
              <div className="text-[0.6rem] text-[var(--color-faint)] truncate w-full text-center">
                {f.stage}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
