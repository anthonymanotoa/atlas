import { AnalyticsStrip } from "../components/AnalyticsStrip";
import type { ConversionRow, RateRow, Recommendation } from "../api";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/states";
import { useAnalytics, useApplyRec } from "../hooks/useAnalytics";
import { useOverview } from "../hooks/useOverview";
import { pct } from "../lib";
import { toast } from "sonner";

// F3 §6.2 — la analítica rica: además del strip/embudo del overview, consume GET /api/analytics
// (funnel con tasas, piso empírico de score, conversión por dimensión, tiempos de respuesta y
// recomendaciones accionables). Barras CSS deterministas, sin dependencia de charting. $0.

function Bar({ value, max }: { value: number; max: number }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
      <div
        className="h-full rounded-full bg-primary transition-[width] duration-[var(--dur-slow)] ease-[var(--ease-out)]"
        style={{ width: `${max > 0 ? Math.max((value / max) * 100, 3) : 0}%` }}
      />
    </div>
  );
}

function ConversionBreakdown({ title, rows }: { title: string; rows: ConversionRow[] }) {
  const max = Math.max(...rows.map((r) => r.applied), 1);
  return (
    <Card className="p-4">
      <div className="mb-3 text-caption text-muted-foreground uppercase">{title}</div>
      {rows.length === 0 ? (
        <div className="text-[0.78rem] text-muted-foreground">Sin aplicaciones todavía.</div>
      ) : (
        <ul className="space-y-2.5">
          {rows.map((r) => (
            <li key={r.key}>
              <div className="mb-1 flex items-center justify-between gap-2 text-[0.78rem]">
                <span className="truncate font-medium">{r.key}</span>
                <span className="shrink-0 text-muted-foreground tabular-nums">
                  {r.applied} apl · {pct(r.response_rate)} resp
                </span>
              </div>
              <Bar value={r.applied} max={max} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

// Task 19 — calibración de outcomes: a diferencia de ConversionBreakdown, cada fila puede
// venir con muestra insuficiente (n<5); ahí se muestra "n=X, aún sin señal" en vez de un %
// que induciría a error (0% con 1 muestra no es lo mismo que 0% con 20).
function RateBreakdown({ title, rows }: { title: string; rows: RateRow[] }) {
  const max = Math.max(...rows.map((r) => r.applied), 1);
  return (
    <Card className="p-4">
      <div className="mb-3 text-caption text-muted-foreground uppercase">{title}</div>
      {rows.length === 0 ? (
        <div className="text-[0.78rem] text-muted-foreground">Sin aplicaciones atribuibles todavía.</div>
      ) : (
        <ul className="space-y-2.5">
          {rows.map((r) => (
            <li key={r.key}>
              <div className="mb-1 flex items-center justify-between gap-2 text-[0.78rem]">
                <span className="truncate font-medium">{r.key}</span>
                <span className="shrink-0 text-muted-foreground tabular-nums">
                  {r.insufficient
                    ? `n=${r.n}, aún sin señal`
                    : `${r.applied} apl · ${pct(r.response_rate)} resp`}
                </span>
              </div>
              <Bar value={r.applied} max={max} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function RecCard({ rec }: { rec: Recommendation }) {
  const applyRec = useApplyRec();
  const actionable = rec.action_type !== "none";
  return (
    <Card className="flex items-start justify-between gap-3 p-3.5">
      <div className="min-w-0 text-[0.82rem]">{rec.text}</div>
      {actionable && (
        <Button
          variant="secondary"
          size="sm"
          className="shrink-0"
          disabled={applyRec.isPending}
          onClick={() =>
            applyRec.mutate(rec, {
              onSuccess: (r) => toast.success(`Aplicado: ${r.applied}`),
              onError: () => toast.error("No se pudo aplicar la recomendación"),
            })
          }
        >
          Aplicar
        </Button>
      )}
    </Card>
  );
}

export function AnalyticsPage() {
  const overviewQ = useOverview();
  const analyticsQ = useAnalytics();

  if (overviewQ.isPending) return <LoadingState rows={3} />;
  if (overviewQ.isError) return <ErrorState onRetry={() => overviewQ.refetch()} />;
  if (!overviewQ.data) return null;

  const ov = overviewQ.data.overview;
  const a = analyticsQ.data;
  const funnelMax = a ? Math.max(...a.funnel.map((f) => f.count), 1) : 1;

  return (
    <>
      <h1 className="mb-4 text-h1">Analítica</h1>
      <AnalyticsStrip ov={ov} />

      {ov.total_jobs === 0 && ov.funnel.length === 0 && (
        <div className="mt-4">
          <EmptyState
            title="Sin datos todavía"
            description="Corre una búsqueda para poblar el embudo."
          />
        </div>
      )}

      {analyticsQ.isError && (
        <div className="mt-4">
          <ErrorState
            title="No se pudo cargar la analítica detallada"
            onRetry={() => analyticsQ.refetch()}
          />
        </div>
      )}

      {a && (
        <div className="mt-6 flex flex-col gap-6">
          {/* Funnel con tasas de conversión vs etapa previa */}
          <Card className="p-4">
            <div className="mb-3 flex items-center justify-between">
              <div className="text-caption text-muted-foreground uppercase">
                Embudo con conversión
              </div>
              {a.score_floor != null && (
                <Badge variant="info" className="tabular-nums">
                  piso de score: {a.score_floor.toFixed(0)}
                </Badge>
              )}
            </div>
            <ul className="space-y-2.5">
              {a.funnel.map((f) => (
                <li key={f.stage}>
                  <div className="mb-1 flex items-center justify-between gap-2 text-[0.78rem]">
                    <span className="font-medium">{f.stage}</span>
                    <span className="shrink-0 text-muted-foreground tabular-nums">
                      {f.count}
                      {f.rate != null ? ` · ${pct(f.rate)} vs previa` : ""}
                    </span>
                  </div>
                  <Bar value={f.count} max={funnelMax} />
                </li>
              ))}
            </ul>
            {a.score_floor == null && (
              <div className="mt-2 text-[0.72rem] text-muted-foreground">
                Piso de score: aún sin resultados positivos para calcularlo.
              </div>
            )}
          </Card>

          {/* Conversión por dimensión */}
          <div className="grid gap-4 lg:grid-cols-2">
            <ConversionBreakdown title="Por fuente" rows={a.by_source} />
            <ConversionBreakdown title="Por ATS" rows={a.by_ats} />
            <ConversionBreakdown title="Por política remota" rows={a.by_remote_policy} />
            <ConversionBreakdown title="Por término de rol" rows={a.by_role_term} />
          </div>

          {/* Calibración de outcomes (Task 19): qué canal y qué variante de CV consiguen
              respuesta de verdad — con la misma disciplina de muestra mínima que el resto. */}
          <div className="grid gap-4 lg:grid-cols-2">
            <RateBreakdown title="Por canal de outreach" rows={a.response_rate_by_channel} />
            <RateBreakdown title="Por versión de CV" rows={a.response_rate_by_cv_version} />
          </div>

          {/* Tiempos de respuesta */}
          <Card className="p-4">
            <div className="mb-3 text-caption text-muted-foreground uppercase">
              Tiempos de respuesta
            </div>
            {a.response_times.n === 0 ? (
              <div className="text-[0.78rem] text-muted-foreground">
                Sin respuestas registradas todavía.
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <div className="text-2xl font-semibold tabular-nums">
                    {a.response_times.avg_days ?? "—"}
                  </div>
                  <div className="text-[0.7rem] text-muted-foreground">días promedio</div>
                </div>
                <div>
                  <div className="text-2xl font-semibold tabular-nums">
                    {a.response_times.median_days ?? "—"}
                  </div>
                  <div className="text-[0.7rem] text-muted-foreground">mediana</div>
                </div>
                <div>
                  <div className="text-2xl font-semibold tabular-nums">
                    {a.response_times.p90_days ?? "—"}
                  </div>
                  <div className="text-[0.7rem] text-muted-foreground">
                    p90 (n={a.response_times.n})
                  </div>
                </div>
              </div>
            )}
          </Card>

          {/* Recomendaciones accionables */}
          <section>
            <div className="mb-2 flex items-center gap-2">
              <h2 className="text-h3">Recomendaciones</h2>
              {a.recommendations.length > 0 && (
                <Badge variant="secondary" className="tabular-nums">
                  {a.recommendations.length}
                </Badge>
              )}
            </div>
            {a.recommendations.length === 0 ? (
              <div className="text-[0.78rem] text-muted-foreground">
                Sin recomendaciones — los umbrales se disparan solo con muestra suficiente.
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {a.recommendations.map((rec) => (
                  <RecCard key={rec.id} rec={rec} />
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </>
  );
}
