import { Check } from "lucide-react";
import type { Job } from "../../api";
import { Card } from "../ui/card";
import { KnockoutIcon } from "../ui/icons";

// §4.3 spec v2: transparencia de score — render legible de los factores que
// score_job ya produce (fit_reasons + knockout_flags). Sin lógica nueva.
export function ScoreBreakdown({ job }: { job: Job }) {
  const reasons = job.fit_reasons ?? [];
  const knockouts = job.knockout_flags ?? [];
  if (job.fit_score == null && reasons.length === 0 && knockouts.length === 0) return null;
  return (
    <Card className="p-3.5 text-sm">
      <div className="mb-2 text-caption text-muted-foreground uppercase">
        Por qué {job.fit_score ?? "—"}
      </div>
      {reasons.length === 0 && knockouts.length === 0 ? (
        <div className="text-muted-foreground">
          Esta vacante aún no tiene desglose guardado — vuelve a correr “Buscar” para recalcularlo.
        </div>
      ) : (
        <ul className="space-y-1.5">
          {reasons.map((r) => (
            <li key={r} className="flex items-start gap-2">
              <Check className="mt-0.5 size-3.5 shrink-0 text-success" strokeWidth={3} />
              <span>{r}</span>
            </li>
          ))}
          {knockouts.map((k) => (
            <li key={k} className="flex items-start gap-2 text-warning">
              <KnockoutIcon className="mt-0.5 size-3.5 shrink-0" />
              <span>{k}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
