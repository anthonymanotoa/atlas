import { Check } from "lucide-react";
import type { JobDetail } from "../../api";
import { pct } from "../../lib";
import { Card } from "../ui/card";

export function Ledger({ d }: { d: JobDetail }) {
  const cv = d.cv_versions[0];
  const rows = [
    {
      ok: !!cv,
      on: "CV adaptado",
      off: "CV pendiente",
      detail: cv
        ? `cobertura ${pct(cv.keyword_coverage)} · ${cv.parse_ok ? "ATS ✓" : "revisar formato"}`
        : "",
    },
    {
      ok: d.messages.length > 0,
      on: `${d.messages.length} mensajes redactados`,
      off: "Sin borradores",
      detail: "",
    },
    {
      ok: d.job.state === "ready" || d.job.applied_at != null,
      on: "Listo para enviar",
      off: "Aún en preparación",
      detail: "",
    },
  ];
  return (
    <Card className="space-y-2 p-3.5">
      {rows.map((r, i) => (
        <div key={i} className="flex items-center gap-2 text-sm">
          <span
            className={`grid size-4 place-items-center rounded-full ${
              r.ok ? "bg-success text-success-foreground" : "bg-secondary text-muted-foreground"
            }`}
          >
            {r.ok ? <Check className="size-3" strokeWidth={3} /> : null}
          </span>
          <span className={r.ok ? "" : "text-muted-foreground"}>{r.ok ? r.on : r.off}</span>
          {r.detail && <span className="text-[0.72rem] text-muted-foreground">· {r.detail}</span>}
        </div>
      ))}
    </Card>
  );
}
