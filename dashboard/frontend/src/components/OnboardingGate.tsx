import { CheckCircle2, RefreshCw } from "lucide-react";
import { api, type OnboardingStatus } from "../api";

const SEV: Record<string, { tone: string; label: string }> = {
  high: { tone: "var(--color-danger)", label: "Alta" },
  med: { tone: "var(--color-pending)", label: "Media" },
  low: { tone: "var(--color-faint)", label: "Baja" },
};

const LINKEDIN_CHECKLIST = [
  "Titular orientado a IA/ML (no solo 'Data').",
  "Sección 'Acerca de' con tu propuesta de valor y foco en IA.",
  "Experiencia con logros cuantificados (mismos que el CV).",
  "Activa 'Open to work' (visible solo para reclutadores).",
  "Skills y aptitudes alineadas con el CV.",
];

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

  async function complete() {
    await api.completeOnboarding();
    onComplete();
  }

  return (
    <div className="mx-auto max-w-[760px] py-6">
      <div className="card p-5">
        <h2 className="text-lg font-semibold">Primer paso: adapta tu CV y tu LinkedIn</h2>
        <p className="mt-1 text-sm text-[var(--color-muted)]">
          Antes de empezar a buscar, dejá listo tu CV maestro y tu perfil de LinkedIn. Cuando estén,
          marcá este paso como completo y se desbloquea el tablero.
        </p>

        {!cv_present && (
          <div className="card mt-4 p-3 text-sm" style={{ borderColor: "var(--color-pending)" }}>
            No encontré tu <code>master_cv.yaml</code>. Copiá el ejemplo y completalo:
            <code> profiles/&lt;perfil&gt;/profile/master_cv.yaml</code>.
          </div>
        )}

        <div className="mt-5 flex items-center justify-between">
          <div className="text-sm font-semibold">
            Auditoría del CV —{" "}
            <span style={{ color: SEV.high.tone }}>{audit.summary.high} altas</span> ·{" "}
            <span style={{ color: SEV.med.tone }}>{audit.summary.med} medias</span> ·{" "}
            {audit.summary.low} bajas
          </div>
          <button
            className="btn !py-1 text-xs"
            onClick={onRefresh}
            title="Re-evaluar tras editar el CV"
          >
            <RefreshCw size={13} /> Re-evaluar
          </button>
        </div>

        <div className="mt-2 space-y-1.5">
          {audit.findings.length === 0 && (
            <div className="text-sm text-[var(--color-done)]">
              Sin hallazgos. ¡Tu CV se ve bien!
            </div>
          )}
          {audit.findings.map((f, i) => (
            <div key={i} className="text-sm">
              <span
                className="chip !px-1.5 !py-0 mr-2"
                style={{ color: (SEV[f.severity] || SEV.low).tone }}
              >
                {(SEV[f.severity] || SEV.low).label}
              </span>
              <span className="text-[var(--color-faint)]">[{f.area}]</span> {f.message}
              <div className="ml-1 text-[0.78rem] text-[var(--color-muted)]">→ {f.suggestion}</div>
            </div>
          ))}
        </div>

        <div className="card mt-5 p-3 text-sm" style={{ borderColor: "var(--color-accent2)" }}>
          <div className="font-medium" style={{ color: "var(--color-accent2)" }}>
            Mejora guiada con IA
          </div>
          <div className="mt-1 text-[var(--color-muted)]">
            Corré <code>atlas advise</code> y usá la guía <b>cv-linkedin-advisor</b> (
            <code>advisor/cv_linkedin_advisor.md</code>) en Claude para reposicionar tu CV y
            LinkedIn hacia IA/ML de forma veraz. Aplicá los cambios en tu{" "}
            <code>master_cv.yaml</code> y volvé a “Re-evaluar”.
          </div>
        </div>

        <div className="mt-4">
          <div className="text-sm font-semibold mb-1">Checklist de LinkedIn</div>
          <ul className="space-y-1">
            {LINKEDIN_CHECKLIST.map((item) => (
              <li key={item} className="flex items-start gap-2 text-sm text-[var(--color-muted)]">
                <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-[var(--color-faint)]" />
                {item}
              </li>
            ))}
          </ul>
        </div>

        <div className="mt-6 flex items-center gap-3">
          <button className="btn btn-accent" onClick={complete}>
            Completar onboarding y empezar
          </button>
          {highs > 0 && (
            <span className="text-[0.78rem]" style={{ color: SEV.high.tone }}>
              Hay {highs} hallazgo(s) de prioridad alta — revisalos antes si puedes.
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
