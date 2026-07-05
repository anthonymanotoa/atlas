import { CheckCircle2, RefreshCw, Sparkles } from "lucide-react";
import { api, type OnboardingStatus } from "../api";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card } from "./ui/card";

const SEV: Record<string, { variant: "destructive" | "warning" | "secondary"; label: string }> = {
  high: { variant: "destructive", label: "Alta" },
  med: { variant: "warning", label: "Media" },
  low: { variant: "secondary", label: "Baja" },
};

// Domain-aware checklist: when the backend knows the repositioning target we name it,
// otherwise we fall back to neutral phrasing so no persona is hardcoded.
function linkedinChecklist(target: string): string[] {
  const titular = target
    ? `Titular orientado a ${target} (no solo tu área genérica).`
    : "Titular orientado a tu rol objetivo (no solo tu área genérica).";
  const acercaDe = target
    ? `Sección 'Acerca de' con tu propuesta de valor y foco en ${target}.`
    : "Sección 'Acerca de' con tu propuesta de valor y tu foco profesional.";
  return [
    titular,
    acercaDe,
    "Experiencia con logros cuantificados (mismos que el CV).",
    "Activa 'Open to work' (visible solo para reclutadores).",
    "Skills y aptitudes alineadas con el CV.",
  ];
}

// P1-G: the first step is adapting the CV + LinkedIn. The board stays hidden until
// the user marks onboarding complete for the active profile. The login (profile
// selector) already exists in the header.
export function OnboardingGate({
  status,
  onComplete,
  onRefresh,
}: {
  status: OnboardingStatus;
  onComplete: () => void;
  onRefresh: () => void;
}) {
  const { audit, cv_present } = status;
  const highs = audit.summary.high;
  // "hacia <target_label>" when the profile has a repositioning target, else neutral.
  const target = (status.target_label || "").trim();
  const towardLabel = target ? `hacia ${target}` : "hacia tu rol objetivo";
  const checklist = linkedinChecklist(target);

  async function complete() {
    await api.completeOnboarding();
    onComplete();
  }

  return (
    <div className="fade-up mx-auto max-w-[760px] py-8">
      {/* hero */}
      <div className="mb-6 flex flex-col items-center text-center">
        <div className="mb-4 grid size-12 place-items-center rounded-2xl bg-primary text-lg font-bold text-primary-foreground shadow-[var(--shadow-md)]">
          A
        </div>
        <h1 className="text-display">Primer paso: adapta tu CV y tu LinkedIn</h1>
        <p className="mt-2 max-w-[52ch] text-sm text-muted-foreground">
          Antes de empezar a buscar, dejá listo tu CV maestro y tu perfil de LinkedIn. Cuando estén,
          marcá este paso como completo y se desbloquea el tablero.
        </p>
      </div>

      <Card className="p-5">
        {!cv_present && (
          <Card className="mb-4 border-warning/50 bg-warning/5 p-3 text-sm">
            No encontré tu <code className="font-mono text-warning">master_cv.yaml</code>. Copiá el
            ejemplo y completalo:{" "}
            <code className="font-mono text-muted-foreground">
              profiles/&lt;perfil&gt;/profile/master_cv.yaml
            </code>
            .
          </Card>
        )}

        <div className="flex items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2 text-sm font-semibold">
            <span>Auditoría del CV</span>
            <Badge variant="destructive">{audit.summary.high} altas</Badge>
            <Badge variant="warning">{audit.summary.med} medias</Badge>
            <Badge variant="secondary">{audit.summary.low} bajas</Badge>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onRefresh}
            title="Re-evaluar tras editar el CV"
          >
            <RefreshCw className="size-3.5" /> Re-evaluar
          </Button>
        </div>

        <div className="mt-3 space-y-2.5">
          {audit.findings.length === 0 && (
            <div className="flex items-center gap-2 text-sm text-success">
              <CheckCircle2 className="size-4" /> Sin hallazgos. ¡Tu CV se ve bien!
            </div>
          )}
          {audit.findings.map((f, i) => {
            const sev = SEV[f.severity] || SEV.low;
            return (
              <div key={i} className="flex gap-2.5 text-sm">
                <Badge variant={sev.variant} className="mt-0.5 shrink-0">
                  {sev.label}
                </Badge>
                <div>
                  <span className="text-muted-foreground">[{f.area}]</span> {f.message}
                  <div className="mt-0.5 text-[0.8rem] text-muted-foreground">→ {f.suggestion}</div>
                </div>
              </div>
            );
          })}
        </div>

        <Card className="mt-5 border-[color-mix(in_oklch,var(--accent2)_50%,var(--border))] bg-[color-mix(in_oklch,var(--accent2)_8%,transparent)] p-3.5 text-sm">
          <div
            className="flex items-center gap-1.5 font-medium"
            style={{ color: "var(--accent2)" }}
          >
            <Sparkles className="size-4" /> Mejora guiada con IA
          </div>
          <div className="mt-1.5 text-muted-foreground">
            Corré <code className="font-mono">atlas advise</code> y usá la guía{" "}
            <b className="text-foreground">cv-linkedin-advisor</b> (
            <code className="font-mono">advisor/cv_linkedin_advisor.md</code>) en Claude para
            reposicionar tu CV y LinkedIn {towardLabel} de forma veraz. Aplicá los cambios en tu{" "}
            <code className="font-mono">master_cv.yaml</code> y volvé a “Re-evaluar”.
          </div>
        </Card>

        <div className="mt-5">
          <div className="mb-2 text-sm font-semibold">Checklist de LinkedIn</div>
          <ul className="space-y-1.5">
            {checklist.map((item) => (
              <li key={item} className="flex items-start gap-2 text-sm text-muted-foreground">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success/70" />
                {item}
              </li>
            ))}
          </ul>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button onClick={complete}>Completar onboarding y empezar</Button>
          {highs > 0 && (
            <span className="text-[0.8rem] text-destructive">
              Hay {highs} hallazgo(s) de prioridad alta — revisalos antes si puedes.
            </span>
          )}
        </div>
      </Card>
    </div>
  );
}
