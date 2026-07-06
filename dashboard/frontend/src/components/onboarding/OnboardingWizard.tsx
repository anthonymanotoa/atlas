import { ArrowLeft, ArrowRight, Check, FileUp, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api, type CriteriaConfig, type OnboardingStatus } from "../../api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Checkbox } from "../ui/checkbox";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Switch } from "../ui/switch";

const REGION_OPTIONS = [
  { id: "worldwide", label: "Mundial (remotos sin restricción)" },
  { id: "latam", label: "Latinoamérica" },
  { id: "na", label: "Norteamérica" },
  { id: "eu", label: "Europa" },
  { id: "apac", label: "Asia-Pacífico" },
];
const LANGUAGE_OPTIONS = ["en", "es", "de", "fr", "pt"];
const STEPS = [
  "Tu perfil",
  "País y regiones",
  "Tipo de trabajo",
  "Salario e idiomas",
  "Tu CV",
  "Fuentes iniciales",
];

const listToText = (xs: string[] | undefined): string => (xs || []).join(", ");
const textToList = (s: string): string[] =>
  s
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);

// F2: per-profile onboarding wizard (replaces OnboardingGate). Everything configurable —
// nothing hardcoded per candidate. Writes criteria.md via PUT /api/criteria on finish, then
// renames the profile and marks onboarding complete so AppShell's gate unlocks the board.
export function OnboardingWizard({
  status,
  onDone,
}: {
  status: OnboardingStatus;
  onDone: () => void;
}) {
  const [step, setStep] = useState(0);
  const [criteria, setCriteria] = useState<CriteriaConfig | null>(null);
  const [prose, setProse] = useState("");
  const [label, setLabel] = useState("");
  const [rolesText, setRolesText] = useState("");
  const [onsiteText, setOnsiteText] = useState("");
  const [draft, setDraft] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [saving, setSaving] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.criteria().then((r) => {
      setCriteria(r.criteria);
      setProse(r.prose);
      setRolesText(listToText(r.criteria.roles));
      setOnsiteText(listToText(r.criteria.onsite_locations));
    });
    api.profiles().then((p) => {
      setLabel(p.profiles.find((x) => x.id === p.active)?.label || "");
    });
  }, []);

  if (!criteria) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">Cargando tu perfil…</div>
    );
  }

  const set = (patch: Partial<CriteriaConfig>) => setCriteria({ ...criteria, ...patch });
  const toggleIn = (key: "acceptable_regions" | "languages", value: string) => {
    const xs = (criteria[key] as string[]) || [];
    set({ [key]: xs.includes(value) ? xs.filter((x) => x !== value) : [...xs, value] });
  };

  async function importFile(file: File) {
    setImporting(true);
    try {
      const r = await api.importCv(file);
      setDraft(r.draft);
      toast.success("CV importado — borrador creado para tu revisión");
    } catch {
      toast.error("No se pudo importar el CV (usa PDF o DOCX con texto)");
    } finally {
      setImporting(false);
    }
  }

  async function finish() {
    if (!criteria) return;
    setSaving(true);
    try {
      await api.saveCriteria(
        { ...criteria, roles: textToList(rolesText), onsite_locations: textToList(onsiteText) },
        prose,
      );
      if (label.trim()) await api.renameProfile(status.profile, label.trim());
      await api.completeOnboarding();
      toast.success("Perfil configurado — ¡a buscar!");
      onDone();
    } catch {
      toast.error("No se pudo guardar la configuración");
    } finally {
      setSaving(false);
    }
  }

  const last = step === STEPS.length - 1;

  return (
    <div className="fade-up mx-auto max-w-[720px] py-8">
      {/* progress */}
      <div className="mb-6 flex items-center justify-center gap-2">
        {STEPS.map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <div
              className={
                "grid size-6 place-items-center rounded-full text-[0.7rem] font-semibold " +
                (i < step
                  ? "bg-primary text-primary-foreground"
                  : i === step
                    ? "bg-secondary text-foreground ring-1 ring-primary"
                    : "bg-secondary text-muted-foreground")
              }
              title={s}
            >
              {i < step ? <Check className="size-3.5" /> : i + 1}
            </div>
            {i < STEPS.length - 1 && <div className="h-px w-6 bg-border" />}
          </div>
        ))}
      </div>

      <Card className="p-6">
        <h1 className="mb-1 text-h3 font-semibold">{STEPS[step]}</h1>

        {step === 0 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Cómo te llamas y en qué industria buscas. El dominio define el vocabulario del motor
              (roles, seniority, CV) y viene del pack elegido al crear el perfil.
            </p>
            <div className="space-y-1.5">
              <Label htmlFor="wiz-label">Nombre del perfil</Label>
              <Input
                id="wiz-label"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="Tu nombre"
              />
            </div>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Dominio:</span>
              <Badge variant="secondary">{status.domain || "data"}</Badge>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Muchos remotos exigen residir en un país/región. Con tu país, Atlas penaliza (sin
              ocultar) los que no te aplican — p. ej. “Remote — US only”.
            </p>
            <div className="space-y-1.5">
              <Label htmlFor="wiz-country">País de residencia (código ISO-2)</Label>
              <Input
                id="wiz-country"
                className="max-w-[160px] font-mono lowercase"
                value={criteria.candidate_country}
                onChange={(e) => set({ candidate_country: e.target.value.trim().toLowerCase() })}
                placeholder="ec, mx, es…"
                maxLength={2}
              />
              <p className="text-[0.75rem] text-muted-foreground">
                Vacío = sin penalización geográfica.
              </p>
            </div>
            <div className="space-y-2">
              <Label>Regiones que también te sirven</Label>
              {REGION_OPTIONS.map((r) => (
                <Label key={r.id} className="flex cursor-pointer items-center gap-2 font-normal">
                  <Checkbox
                    checked={(criteria.acceptable_regions || []).includes(r.id)}
                    onCheckedChange={() => toggleIn("acceptable_regions", r.id)}
                  />
                  {r.label}
                </Label>
              ))}
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="wiz-roles">Roles objetivo (separados por coma)</Label>
              <Input
                id="wiz-roles"
                value={rolesText}
                onChange={(e) => setRolesText(e.target.value)}
                placeholder="data engineer, analytics engineer"
              />
            </div>
            <Label className="flex cursor-pointer items-center gap-2 font-normal">
              <Switch
                checked={criteria.remote_required}
                onCheckedChange={(v) => set({ remote_required: Boolean(v) })}
              />
              Solo trabajos 100% remotos
            </Label>
            <div className="space-y-1.5">
              <Label htmlFor="wiz-onsite">Ubicaciones aceptables para presencial (coma)</Label>
              <Input
                id="wiz-onsite"
                value={onsiteText}
                onChange={(e) => setOnsiteText(e.target.value)}
                placeholder="quito, guayaquil, ec"
              />
              <p className="text-[0.75rem] text-muted-foreground">
                Vacío = sin filtro presencial. Los remotos nunca se filtran por esto.
              </p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="wiz-years">Años de experiencia reales</Label>
              <Input
                id="wiz-years"
                type="number"
                min={0}
                className="max-w-[120px] tabular-nums"
                value={criteria.candidate_years || 0}
                onChange={(e) => set({ candidate_years: Number(e.target.value) || 0 })}
              />
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="wiz-salary">Salario mínimo anual (USD, 0 = sin piso)</Label>
              <Input
                id="wiz-salary"
                type="number"
                min={0}
                className="max-w-[180px] tabular-nums"
                value={criteria.salary_floor_usd || 0}
                onChange={(e) => set({ salary_floor_usd: Number(e.target.value) || 0 })}
              />
            </div>
            <div className="space-y-2">
              <Label>Idiomas en los que aceptas ofertas</Label>
              <div className="flex flex-wrap gap-3">
                {LANGUAGE_OPTIONS.map((l) => (
                  <Label key={l} className="flex cursor-pointer items-center gap-1.5 font-normal">
                    <Checkbox
                      checked={(criteria.languages || []).includes(l)}
                      onCheckedChange={() => toggleIn("languages", l)}
                    />
                    <span className="uppercase">{l}</span>
                  </Label>
                ))}
              </div>
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Sube tu CV (PDF/DOCX). Atlas extrae el texto a un <b>borrador revisable</b> (
              <code className="font-mono">master_cv.draft.yaml</code>) — nunca escribe tu{" "}
              <code className="font-mono">master_cv.yaml</code> directo: lo mapeás y confirmás vos
              (con ayuda de Claude si querés).
            </p>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && importFile(e.target.files[0])}
            />
            <Button
              variant="secondary"
              disabled={importing}
              onClick={() => fileRef.current?.click()}
            >
              {importing ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <FileUp className="size-4" />
              )}
              {importing ? "Importando…" : "Subir CV (PDF/DOCX)"}
            </Button>
            {status.cv_present && !draft && (
              <p className="text-sm text-success">
                Ya tienes un master_cv.yaml — puedes saltar este paso.
              </p>
            )}
            {draft && (
              <Card className="max-h-56 overflow-auto p-3">
                <pre className="font-mono text-[0.7rem] whitespace-pre-wrap">{draft}</pre>
              </Card>
            )}
          </div>
        )}

        {step === 5 && (
          <div className="space-y-4 text-sm">
            <p className="text-muted-foreground">
              (Opcional) Las empresas que Atlas vigila directamente viven en{" "}
              <code className="font-mono">profiles/{status.profile}/config/companies.yaml</code>.
              Puedes editarlas ahora o después desde Ajustes; añadir empresas por URL llega en la
              Fase 3. Las fuentes públicas (job boards) ya vienen activas.
            </p>
            <p className="text-muted-foreground">
              Al finalizar se guardan tus criterios y se desbloquea el tablero.
            </p>
          </div>
        )}

        {/* footer nav */}
        <div className="mt-6 flex items-center justify-between">
          <Button variant="ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>
            <ArrowLeft className="size-4" /> Atrás
          </Button>
          {!last ? (
            <Button onClick={() => setStep(step + 1)}>
              Siguiente <ArrowRight className="size-4" />
            </Button>
          ) : (
            <Button disabled={saving} onClick={finish}>
              {saving ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
              Finalizar
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
