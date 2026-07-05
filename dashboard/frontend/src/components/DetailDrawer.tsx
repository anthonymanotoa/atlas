import { Download, ExternalLink, FileText, FolderOpen, Loader2, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type JobDetail } from "../api";
import { STATE_ES, copy, fitTone, freshLabel, langLabel, pct, salaryLabel } from "../lib";
import { CompanyInsights } from "./job-detail/CompanyInsights";
import { JobOverview } from "./job-detail/JobOverview";
import { Ledger } from "./job-detail/Ledger";
import { MessageCard } from "./job-detail/MessageCard";
import { RecordOutcome } from "./job-detail/RecordOutcome";
import { SectionTitle } from "./job-detail/SectionTitle";
import { SocialSearch } from "./job-detail/SocialSearch";
import { InterviewPanel } from "./InterviewPanel";
import { Badge } from "./ui/badge";
import { Button, buttonVariants } from "./ui/button";
import { Card } from "./ui/card";
import { KnockoutIcon, MatchIcon, ReferralIcon, SalaryIcon } from "./ui/icons";
import { ScoreRing } from "./ui/score-ring";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "./ui/sheet";
import { Skeleton } from "./ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";

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
  const [preparing, setPreparing] = useState(false);
  const [applying, setApplying] = useState(false);
  useEffect(() => {
    if (jobId) {
      setD(null);
      api.job(jobId).then(setD);
    }
  }, [jobId]);

  async function prep() {
    if (!jobId || preparing) return;
    setPreparing(true);
    const tid = toast.loading("Preparando tu CV y mensajes…", {
      description: "Adapto el CV a esta oferta (ATS-safe) y redacto los mensajes.",
    });
    try {
      const r = await api.prep(jobId); // language auto-picked (es offer → ES, else EN)
      setD(await api.job(jobId));
      onChanged();
      toast.success("CV y mensajes listos", {
        id: tid,
        description: `Cobertura ${pct(r.coverage)} · ${r.parse_ok ? "ATS ✓" : "revisar formato"}`,
      });
    } catch {
      toast.error("No se pudo preparar", { id: tid, description: "Reintenta en un momento." });
    } finally {
      setPreparing(false);
    }
  }
  async function markApplied() {
    if (!jobId || applying) return;
    setApplying(true);
    try {
      await api.markApplied(jobId);
      setD(await api.job(jobId));
      onChanged();
      toast.success("Marcado como aplicado");
    } catch {
      toast.error("No se pudo marcar como aplicado");
    } finally {
      setApplying(false);
    }
  }
  async function dismiss() {
    if (!jobId) return;
    const prev = d?.job.state || "shortlisted";
    onClose();
    await api.setState(jobId, "dismissed");
    onChanged();
    toast.success("Vacante descartada", {
      description: "No volverá a aparecer en tu tablero.",
      action: {
        label: "Deshacer",
        onClick: async () => {
          await api.setState(jobId, prev);
          onChanged();
        },
      },
    });
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
                      <ExternalLink className="size-3.5" /> Abrir oferta
                    </a>
                  </Button>
                )}
              </div>

              {/* Todo lo necesario para decidir, antes de postular */}
              <JobOverview job={d.job} />

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
                    style={{ color: "var(--accent2)" }}
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
                <div className="space-y-1.5">
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
                  <button
                    type="button"
                    onClick={async () => {
                      const l = await api.cvLibrary();
                      await copy(l.dir);
                      toast.success("Ruta de tu carpeta de CVs copiada", { description: l.dir });
                    }}
                    className="flex items-center gap-1.5 text-[0.72rem] text-muted-foreground transition-colors hover:text-foreground"
                  >
                    <FolderOpen className="size-3.5" /> También se guarda en tu carpeta de CVs (por
                    empresa) · copiar ruta
                  </button>
                </div>
              )}

              <div>
                <SectionTitle>Mensajes — qué enviar</SectionTitle>
                <div className="space-y-2">
                  {d.messages.length === 0 && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="secondary"
                          className="w-full"
                          onClick={prep}
                          disabled={preparing}
                        >
                          {preparing && <Loader2 className="size-4 animate-spin" />}
                          {preparing ? "Generando…" : "Generar borradores"}
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
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="ghost" size="icon" onClick={dismiss} aria-label="Descartar">
                    <Trash2 className="size-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Descartar — no me interesa (se puede deshacer)</TooltipContent>
              </Tooltip>
              <Button
                variant="secondary"
                className="flex-1"
                onClick={markApplied}
                disabled={applying}
              >
                {applying && <Loader2 className="size-4 animate-spin" />}
                {applying ? "Marcando…" : "Marcar como aplicado"}
              </Button>
              <Button className="flex-1" onClick={prep} disabled={preparing}>
                {preparing && <Loader2 className="size-4 animate-spin" />}
                {preparing ? "Preparando…" : "Re-preparar"}
              </Button>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
