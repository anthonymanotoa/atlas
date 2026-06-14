import { CheckCircle2, RefreshCw, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, type Finding } from "../api";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "./ui/dialog";
import { ScrollArea } from "./ui/scroll-area";

const SEV: Record<string, { variant: "destructive" | "warning" | "secondary"; label: string }> = {
  high: { variant: "destructive", label: "Alta" },
  med: { variant: "warning", label: "Media" },
  low: { variant: "secondary", label: "Baja" },
};

type Audit = { findings: Finding[]; summary: { high: number; med: number; low: number } };

// Persistent CV audit (the `atlas advise` engine) — same view as onboarding, but reachable
// any time from the header so you never need the terminal to re-check your CV.
export function CvAuditDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const [audit, setAudit] = useState<Audit | null>(null);
  const [cvPresent, setCvPresent] = useState(true);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.cvAudit();
      setAudit(r.audit);
      setCvPresent(r.cv_present);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88vh] max-w-[680px] gap-0 overflow-hidden p-0">
        <DialogHeader className="border-b border-border px-6 py-5">
          <DialogTitle className="text-h1">Auditoría de tu CV</DialogTitle>
          <DialogDescription>
            Score y recomendaciones sobre tu <code className="font-mono">master_cv.yaml</code> —
            mismo motor que <code className="font-mono">atlas advise</code>, sin terminal.
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="max-h-[calc(88vh-96px)]">
          <div className="space-y-4 px-6 py-5">
            {!cvPresent && (
              <Card className="border-warning/50 bg-warning/5 p-3 text-sm">
                No encontré tu <code className="font-mono text-warning">master_cv.yaml</code>.
                Copialo a{" "}
                <code className="font-mono text-muted-foreground">
                  profiles/&lt;perfil&gt;/profile/master_cv.yaml
                </code>{" "}
                (o importá uno con{" "}
                <code className="font-mono">atlas import-cv &lt;pdf/docx&gt;</code>) y volvé a
                “Re-evaluar”.
              </Card>
            )}

            <div className="flex items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                <span>Resumen</span>
                <Badge variant="destructive">{audit?.summary.high ?? 0} altas</Badge>
                <Badge variant="warning">{audit?.summary.med ?? 0} medias</Badge>
                <Badge variant="secondary">{audit?.summary.low ?? 0} bajas</Badge>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={load}
                disabled={loading}
                title="Re-evaluar tras editar el CV"
              >
                <RefreshCw className={`size-3.5 ${loading ? "animate-spin" : ""}`} /> Re-evaluar
              </Button>
            </div>

            <div className="space-y-2.5">
              {audit && audit.findings.length === 0 && (
                <div className="flex items-center gap-2 text-sm text-success">
                  <CheckCircle2 className="size-4" /> Sin hallazgos. ¡Tu CV se ve bien!
                </div>
              )}
              {audit?.findings.map((f, i) => {
                const sev = SEV[f.severity] || SEV.low;
                return (
                  <div key={i} className="flex gap-2.5 text-sm">
                    <Badge variant={sev.variant} className="mt-0.5 shrink-0">
                      {sev.label}
                    </Badge>
                    <div>
                      <span className="text-muted-foreground">[{f.area}]</span> {f.message}
                      <div className="mt-0.5 text-[0.8rem] text-muted-foreground">
                        → {f.suggestion}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <Card className="border-[color-mix(in_oklch,var(--accent2)_50%,var(--border))] bg-[color-mix(in_oklch,var(--accent2)_8%,transparent)] p-3.5 text-sm">
              <div
                className="flex items-center gap-1.5 font-medium"
                style={{ color: "var(--color-accent2)" }}
              >
                <Sparkles className="size-4" /> Cómo mejorarlo
              </div>
              <div className="mt-1.5 text-muted-foreground">
                Editá tu <code className="font-mono">master_cv.yaml</code> aplicando las sugerencias
                de arriba (usá solo hechos reales) y pulsá “Re-evaluar”. Para una mejora guiada
                IA-forward de CV + LinkedIn, usá la guía{" "}
                <b className="text-foreground">cv-linkedin-advisor</b> en Claude.
              </div>
            </Card>
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
