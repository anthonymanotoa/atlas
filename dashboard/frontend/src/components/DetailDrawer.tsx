import { Check, Copy, Download, ExternalLink, FileText, Plus, Search, Send } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type JobDetail, type Learning, type SocialMention } from "../api";
import { STATE_ES, copy, fitTone, freshLabel, langLabel, pct, salaryLabel } from "../lib";
import { InterviewPanel } from "./InterviewPanel";
import { Badge } from "./ui/badge";
import { Button, buttonVariants } from "./ui/button";
import { Card } from "./ui/card";
import { InsightsIcon, KnockoutIcon, MatchIcon, ReferralIcon, SalaryIcon } from "./ui/icons";
import { Input } from "./ui/input";
import { ScoreRing } from "./ui/score-ring";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Separator } from "./ui/separator";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "./ui/sheet";
import { Skeleton } from "./ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";

const KIND_ES: Record<string, string> = {
  cover_letter: "Carta de presentación",
  cold_email: "Email en frío",
  recruiter: "Mensaje a reclutador",
  hiring_manager: "Mensaje a hiring manager",
  referral_ask: "Pedido de referido",
  linkedin_note: "Nota de LinkedIn",
  follow_up: "Follow-up",
  breakup: "Cierre cordial",
};

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <div className="mb-2 text-caption text-muted-foreground uppercase">{children}</div>;
}

function Ledger({ d }: { d: JobDetail }) {
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

function MessageCard({ m }: { m: JobDetail["messages"][number] }) {
  const [done, setDone] = useState(false);
  const [sent, setSent] = useState(m.state === "sent");
  return (
    <Card className="p-3.5">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-medium">{KIND_ES[m.kind] || m.kind}</div>
        <Badge variant="secondary">
          {m.channel} · {m.language}
        </Badge>
      </div>
      {m.subject && (
        <div className="mt-1 text-[0.78rem] text-muted-foreground">Asunto: {m.subject}</div>
      )}
      <pre className="mt-2 max-h-44 overflow-auto rounded-lg bg-background/60 p-2.5 font-sans text-[0.8rem] whitespace-pre-wrap text-foreground">
        {m.body}
      </pre>
      <div className="mt-2.5 flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={async () => {
            await copy((m.subject ? `${m.subject}\n\n` : "") + m.body);
            setDone(true);
            toast.success("Copiado al portapapeles");
            setTimeout(() => setDone(false), 1200);
          }}
        >
          {done ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}{" "}
          {done ? "Copiado" : "Copiar"}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={sent}
          onClick={async () => {
            await api.markSent(m.id);
            setSent(true);
            toast.success("Mensaje marcado como enviado");
          }}
        >
          <Send className="size-3.5" /> {sent ? "Enviado" : "Marcar enviado"}
        </Button>
      </div>
    </Card>
  );
}

// P2-C: supervised social signal. Atlas queues a search + prepares queries; the human
// runs the LinkedIn/X lookup in their own Chrome and saves what they confirm. No auto-contact.
function SocialSearch({ jobId }: { jobId: string }) {
  const [mentions, setMentions] = useState<SocialMention[]>([]);
  const [queries, setQueries] = useState<Record<string, string> | null>(null);
  const [form, setForm] = useState({ recruiter_name: "", recruiter_linkedin: "", source_url: "" });
  const refresh = () => api.socialMentions(jobId).then((r) => setMentions(r.mentions));
  useEffect(() => {
    refresh();
  }, [jobId]); // eslint-disable-line react-hooks/exhaustive-deps
  const g = (q: string) => `https://www.google.com/search?q=${encodeURIComponent(q)}`;
  async function start() {
    setQueries((await api.startSocialSearch(jobId)).queries);
  }
  async function save() {
    if (!form.recruiter_name && !form.source_url) return;
    await api.addSocialMention(jobId, { platform: "linkedin", ...form });
    setForm({ recruiter_name: "", recruiter_linkedin: "", source_url: "" });
    refresh();
    toast.success("Mención guardada");
  }
  return (
    <div>
      <SectionTitle>Señal social (LinkedIn / X)</SectionTitle>
      <Card className="space-y-2.5 p-3.5 text-sm">
        <div className="text-[0.78rem] text-muted-foreground">
          Búsqueda supervisada en tu navegador — Atlas no contacta a nadie por ti.
        </div>
        <Button variant="secondary" size="sm" onClick={start}>
          <Search className="size-3.5" /> Buscar reclutador
        </Button>
        {queries && (
          <div className="flex flex-col gap-1 text-xs">
            <a
              className="text-primary hover:underline"
              target="_blank"
              rel="noreferrer"
              href={g(queries.linkedin_recruiters)}
            >
              · LinkedIn — reclutadores ↗
            </a>
            <a
              className="text-primary hover:underline"
              target="_blank"
              rel="noreferrer"
              href={g(queries.linkedin_posts)}
            >
              · LinkedIn — posts de la vacante ↗
            </a>
            <a
              className="text-primary hover:underline"
              target="_blank"
              rel="noreferrer"
              href={g(queries.x)}
            >
              · X / Twitter ↗
            </a>
          </div>
        )}
        {mentions.map((m) => (
          <div key={m.id}>
            <Separator className="mb-2" />
            <b>{m.recruiter_name || m.post_title || "Mención"}</b>{" "}
            {m.platform && <Badge variant="secondary">{m.platform}</Badge>}
            {m.recruiter_linkedin && (
              <a
                className="ml-2 text-xs text-primary hover:underline"
                target="_blank"
                rel="noreferrer"
                href={m.recruiter_linkedin}
              >
                LinkedIn ↗
              </a>
            )}
            {m.source_url && (
              <a
                className="ml-2 text-xs text-primary hover:underline"
                target="_blank"
                rel="noreferrer"
                href={m.source_url}
              >
                fuente ↗
              </a>
            )}
          </div>
        ))}
        <div className="flex flex-col gap-1.5 pt-1">
          <Input
            className="h-8 text-xs"
            placeholder="Nombre del reclutador"
            value={form.recruiter_name}
            onChange={(e) => setForm({ ...form, recruiter_name: e.target.value })}
          />
          <Input
            className="h-8 text-xs"
            placeholder="URL de LinkedIn del reclutador"
            value={form.recruiter_linkedin}
            onChange={(e) => setForm({ ...form, recruiter_linkedin: e.target.value })}
          />
          <div className="flex gap-2">
            <Input
              className="h-8 flex-1 text-xs"
              placeholder="URL fuente (post)"
              value={form.source_url}
              onChange={(e) => setForm({ ...form, source_url: e.target.value })}
            />
            <Button variant="secondary" size="sm" onClick={save}>
              <Plus className="size-3.5" /> Guardar
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}

// P2-D: record a HUMAN-confirmed outcome → feeds the per-company learning loop.
function RecordOutcome({ jobId, onSaved }: { jobId: string; onSaved: () => void }) {
  const [state, setState] = useState("rejected");
  const [recruiterSource, setRecruiterSource] = useState("");
  const [responseDays, setResponseDays] = useState("");
  const [saved, setSaved] = useState(false);
  async function save() {
    await api.recordOutcome(jobId, {
      final_state: state,
      recruiter_source: recruiterSource || null,
      response_days: responseDays ? Number(responseDays) : null,
      offer_made: state === "offer",
    });
    setSaved(true);
    toast.success("Resultado registrado");
    setTimeout(() => setSaved(false), 1500);
    onSaved();
  }
  return (
    <div>
      <SectionTitle>Registrar resultado</SectionTitle>
      <Card className="space-y-2.5 p-3.5 text-sm">
        <div className="flex flex-wrap gap-2">
          <Select value={state} onValueChange={setState}>
            <SelectTrigger size="sm" className="w-auto">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="rejected">Rechazado</SelectItem>
              <SelectItem value="responded">Respondieron</SelectItem>
              <SelectItem value="interviewed">Entrevista</SelectItem>
              <SelectItem value="offer">Oferta</SelectItem>
              <SelectItem value="ghosted">Sin respuesta</SelectItem>
            </SelectContent>
          </Select>
          <Select value={recruiterSource || undefined} onValueChange={(v) => setRecruiterSource(v)}>
            <SelectTrigger size="sm" className="w-auto">
              <SelectValue placeholder="Origen…" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="referral">Referido</SelectItem>
              <SelectItem value="recruiter">Reclutador</SelectItem>
              <SelectItem value="cold">En frío</SelectItem>
              <SelectItem value="inbound">Inbound</SelectItem>
            </SelectContent>
          </Select>
          <Input
            className="h-8 w-24 text-xs"
            placeholder="Días resp."
            value={responseDays}
            onChange={(e) => setResponseDays(e.target.value.replace(/\D/g, ""))}
          />
          <Button variant="secondary" size="sm" onClick={save}>
            {saved ? "Guardado ✓" : "Guardar"}
          </Button>
        </div>
        <div className="text-[0.72rem] text-muted-foreground">
          Alimenta la memoria de Atlas (qué empresas convierten y cómo). Tú confirmas; el brain
          nunca lo inventa.
        </div>
      </Card>
    </div>
  );
}

function CompanyInsights({ learnings }: { learnings?: Learning[] }) {
  if (!learnings || learnings.length === 0) return null;
  return (
    <div>
      <SectionTitle>
        <span className="inline-flex items-center gap-1.5">
          <InsightsIcon className="size-3.5" /> Lo aprendido de esta empresa
        </span>
      </SectionTitle>
      <Card className="space-y-1.5 p-3.5 text-sm">
        {learnings.map((l) => (
          <div key={l.id}>
            {l.observation}{" "}
            <span className="text-[0.72rem] text-muted-foreground">
              · confianza {Math.round(l.confidence * 100)}%
            </span>
          </div>
        ))}
      </Card>
    </div>
  );
}

export function DetailDrawer({
  jobId,
  onClose,
  onChanged,
}: {
  jobId: string | null;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [d, setD] = useState<JobDetail | null>(null);
  useEffect(() => {
    if (jobId) {
      setD(null);
      api.job(jobId).then(setD);
    }
  }, [jobId]);

  async function prep() {
    if (!jobId) return;
    await api.prep(jobId); // language auto-picked from the posting (es offer → ES, else EN)
    api.job(jobId).then(setD);
    onChanged();
  }
  async function markApplied() {
    if (!jobId) return;
    await api.markApplied(jobId);
    api.job(jobId).then(setD);
    onChanged();
    toast.success("Marcado como aplicado");
  }

  return (
    <Sheet open={!!jobId} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="gap-0 p-0 sm:max-w-[560px]">
        {!d ? (
          <div className="space-y-4 p-5">
            <Skeleton className="h-7 w-2/3" />
            <Skeleton className="h-4 w-1/3" />
            <div className="flex gap-2">
              <Skeleton className="h-6 w-16" />
              <Skeleton className="h-6 w-16" />
              <Skeleton className="h-6 w-20" />
            </div>
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : (
          <>
            {/* sticky header */}
            <div className="sticky top-0 z-10 border-b border-border bg-background/85 px-5 py-4 backdrop-blur-xl">
              <div className="flex items-start gap-3 pr-8">
                <ScoreRing
                  value={d.job.fit_score}
                  tone={fitTone(d.job.fit_score)}
                  centerClassName="bg-background"
                />
                <div className="min-w-0">
                  <SheetTitle className="truncate">{d.job.title}</SheetTitle>
                  <SheetDescription className="text-foreground/70">
                    {d.job.company}
                  </SheetDescription>
                </div>
              </div>
            </div>

            {/* scrollable body */}
            <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
              <div className="flex flex-wrap items-center gap-2">
                {d.job.match_score != null && (
                  <Badge
                    variant="score"
                    style={{ "--tone": fitTone(d.job.match_score) } as React.CSSProperties}
                    title="Match CV↔oferta: cobertura ponderada de las keywords de la vacante"
                  >
                    match {d.job.match_score}%
                  </Badge>
                )}
                <Badge variant="secondary">{STATE_ES[d.job.state] || d.job.state}</Badge>
                {d.job.is_remote === 1 && <Badge variant="secondary">Remoto</Badge>}
                {salaryLabel(d.job) && (
                  <Badge variant="secondary" title="Salario publicado">
                    <SalaryIcon /> {salaryLabel(d.job)}
                  </Badge>
                )}
                {d.job.language && (
                  <Badge variant="secondary" className="uppercase">
                    {langLabel(d.job.language)}
                  </Badge>
                )}
                {(d.job.posted_days ?? d.job.age_days) != null && (
                  <Badge variant="secondary">
                    {freshLabel(d.job.posted_days ?? d.job.age_days)}
                  </Badge>
                )}
                {(d.job.apply_url || d.job.url) && (
                  <Button asChild variant="ghost" size="sm" className="h-7 px-2 text-xs">
                    <a href={d.job.apply_url || d.job.url} target="_blank" rel="noreferrer">
                      <ExternalLink className="size-3.5" /> Postular
                    </a>
                  </Button>
                )}
              </div>

              {d.job.knockout_flags && d.job.knockout_flags.length > 0 && (
                <Card className="flex items-start gap-2 border-warning/50 bg-warning/5 p-3 text-sm">
                  <KnockoutIcon className="mt-0.5 size-4 shrink-0 text-warning" />
                  <div>
                    <b>Filtros del puesto:</b> {d.job.knockout_flags.join(", ")}
                  </div>
                </Card>
              )}

              {d.job.missing_keywords && d.job.missing_keywords.length > 0 && (
                <Card className="p-3.5 text-sm">
                  <div className="mb-2 flex items-center gap-1.5 font-medium">
                    <MatchIcon className="size-4 text-muted-foreground" /> Keywords de la oferta que
                    tu CV no evidencia
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {d.job.missing_keywords.slice(0, 12).map((k) => (
                      <Badge key={k} variant="outline">
                        {k}
                      </Badge>
                    ))}
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    Agrégalas a tu CV solo si realmente las tienes (nunca inventes).
                  </div>
                </Card>
              )}

              <Ledger d={d} />

              {d.referrals.length > 0 && (
                <Card className="border-[color-mix(in_oklch,var(--accent2)_50%,var(--border))] bg-[color-mix(in_oklch,var(--accent2)_8%,transparent)] p-3.5">
                  <div
                    className="flex items-center gap-1.5 text-sm font-medium"
                    style={{ color: "var(--color-accent2)" }}
                  >
                    <ReferralIcon className="size-4" /> Referido disponible (prioriza esto)
                  </div>
                  {d.referrals.map((r) => (
                    <div key={r.id} className="mt-1 text-sm">
                      <b>{r.name}</b> — {r.title || ""} @ {r.company}
                      {r.linkedin_url && (
                        <a
                          href={r.linkedin_url}
                          target="_blank"
                          rel="noreferrer"
                          className="ml-2 text-xs text-primary hover:underline"
                        >
                          LinkedIn ↗
                        </a>
                      )}
                    </div>
                  ))}
                </Card>
              )}

              {d.cv_versions[0] && (
                <div className="flex gap-2">
                  {d.cv_versions[0].path_pdf && (
                    <a
                      href={api.cvDownload(d.job.id, d.cv_versions[0].id, "pdf")}
                      className={buttonVariants({ className: "flex-1" })}
                    >
                      <FileText className="size-4" /> CV PDF <Download className="size-3.5" />
                    </a>
                  )}
                  <a
                    href={api.cvDownload(d.job.id, d.cv_versions[0].id, "docx")}
                    className={buttonVariants({ variant: "secondary", className: "flex-1" })}
                  >
                    <FileText className="size-4" /> CV DOCX <Download className="size-3.5" />
                  </a>
                </div>
              )}

              <div>
                <SectionTitle>Mensajes — qué enviar</SectionTitle>
                <div className="space-y-2">
                  {d.messages.length === 0 && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button variant="secondary" className="w-full" onClick={prep}>
                          Generar borradores
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>
                        Adapta tu CV a esta oferta (ATS-safe) y redacta los mensajes de contacto.
                        Reordena solo lo que ya está en tu CV — nunca inventa. Determinista, sin IA.
                      </TooltipContent>
                    </Tooltip>
                  )}
                  {d.messages.map((m) => (
                    <MessageCard key={m.id} m={m} />
                  ))}
                </div>
              </div>

              <CompanyInsights learnings={d.learnings} />

              <SocialSearch jobId={d.job.id} />

              <InterviewPanel jobId={d.job.id} />

              <RecordOutcome
                jobId={d.job.id}
                onSaved={() => {
                  api.job(d.job.id).then(setD);
                  onChanged();
                }}
              />
            </div>

            {/* sticky footer */}
            <div className="sticky bottom-0 z-10 flex gap-2 border-t border-border bg-background/85 px-5 py-3 backdrop-blur-xl">
              <Button variant="secondary" className="flex-1" onClick={markApplied}>
                Marcar como aplicado
              </Button>
              <Button className="flex-1" onClick={prep}>
                Re-preparar
              </Button>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
