import type { UpskillHeatItem, UpskillReport } from "../api";
import { IntentConfirmDialog } from "./IntentConfirmDialog";
import { Badge } from "./ui/badge";
import { Card } from "./ui/card";

// Estados que la pasada 1 recorre por defecto al pedir el reporte (todo lo "en juego": lo que
// ya vas trabajando activamente). El backend valida que cada uno sea un estado real del pipeline.
const UPSKILL_STATES = ["shortlisted", "tailored", "drafted", "ready", "applied"];

// Sin librería de markdown (evitamos dependencias nuevas): un render mínimo suficiente para el
// plan de estudio del brain — títulos, listas y párrafos. El contenido es de confianza (lo
// escribe el brain, validado por apply_result antes de persistir), así que no hay riesgo de HTML
// inyectado: React ya escapa todo el texto.
function MiniMarkdown({ md }: { md: string }) {
  const lines = md.split("\n");
  return (
    <div className="space-y-1.5 text-sm leading-relaxed">
      {lines.map((ln, i) => {
        const key = `${i}-${ln.slice(0, 12)}`;
        if (ln.startsWith("### "))
          return (
            <h4 key={key} className="mt-3 font-semibold">
              {ln.slice(4)}
            </h4>
          );
        if (ln.startsWith("## "))
          return (
            <h3 key={key} className="text-h3 mt-4 font-semibold">
              {ln.slice(3)}
            </h3>
          );
        if (ln.startsWith("# "))
          return (
            <h2 key={key} className="text-h2 mt-2">
              {ln.slice(2)}
            </h2>
          );
        if (ln.startsWith("- "))
          return (
            <li key={key} className="ml-5 list-disc">
              {ln.slice(2)}
            </li>
          );
        if (!ln.trim()) return <div key={key} className="h-1" />;
        return <p key={key}>{ln}</p>;
      })}
    </div>
  );
}

// Severidad → variante semántica del Badge (tokens v2; nunca colores crudos):
// Critical=destructive, High=warning, Medium=info, Low=secondary.
const SEVERITY_VARIANT: Record<
  UpskillHeatItem["severity"],
  "destructive" | "warning" | "info" | "secondary"
> = {
  Critical: "destructive",
  High: "warning",
  Medium: "info",
  Low: "secondary",
};
const SEVERITY_ES: Record<UpskillHeatItem["severity"], string> = {
  Critical: "Crítico",
  High: "Alto",
  Medium: "Medio",
  Low: "Bajo",
};

// Botón para (re)pedir el análisis: encola un intent `upskill_report` para el brain ($0 — no
// corre ahora). Extraído para reusarlo en el header y en el estado vacío.
function RecalcButton() {
  return (
    <IntentConfirmDialog
      buttonLabel="Recalcular gaps"
      title="Análisis de upskilling (gap analysis)"
      what="El brain diffea las skills de tus vacantes contra tu CV (pesa más donde peor encajas), busca recursos actualizados en la web y arma un plan de estudio ordenado por dependencias."
      produces="Un reporte con heatmap de severidad y un plan de estudio priorizado, con diff vs el anterior."
      where="En esta misma vista, tras correr el brain."
      type="upskill_report"
      payload={{ states: UPSKILL_STATES }}
    />
  );
}

export function UpskillView({ report }: { report: UpskillReport | null }) {
  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-h1">Upskilling</h1>
          <p className="text-sm text-muted-foreground">
            Los gaps que más puertas te abrirían, ponderados por lo mal que encajas hoy.
          </p>
        </div>
        <RecalcButton />
      </div>

      {!report && (
        <Card className="p-4 text-sm text-muted-foreground">
          Aún no hay reporte. Pide uno con «Recalcular gaps» y corre el brain para generarlo.
        </Card>
      )}

      {report && (
        <>
          <Card className="p-4">
            <div className="text-caption mb-2 text-muted-foreground uppercase">Heatmap</div>
            <div className="flex flex-wrap gap-2">
              {report.heatmap.map((h, i) => (
                <Badge
                  key={`${i}-${h.skill}`}
                  variant={SEVERITY_VARIANT[h.severity]}
                  title={h.note}
                >
                  {h.skill} · {SEVERITY_ES[h.severity]}
                </Badge>
              ))}
              {report.heatmap.length === 0 && (
                <span className="text-sm text-muted-foreground">Sin skills marcadas.</span>
              )}
            </div>
          </Card>

          <Card className="p-4">
            <MiniMarkdown md={report.report_md} />
          </Card>

          <div className="text-caption text-muted-foreground">
            Generado {report.created_at.slice(0, 16).replace("T", " ")}
          </div>
        </>
      )}
    </div>
  );
}
