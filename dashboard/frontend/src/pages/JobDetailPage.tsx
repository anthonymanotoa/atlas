import {
  ArrowLeft,
  Download,
  ExternalLink,
  FileText,
  FolderOpen,
  Loader2,
  Trash2,
} from "lucide-react";
import type * as React from "react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { api } from "../api";
import { CvReviewPanel } from "../components/CvReviewPanel";
import { IntentConfirmDialog } from "../components/IntentConfirmDialog";
import { CompanyInsights } from "../components/job-detail/CompanyInsights";
import { JobOverview } from "../components/job-detail/JobOverview";
import { Ledger } from "../components/job-detail/Ledger";
import { MessageCard } from "../components/job-detail/MessageCard";
import { RecordOutcome } from "../components/job-detail/RecordOutcome";
import { ScoreBreakdown } from "../components/job-detail/ScoreBreakdown";
import { SectionTitle } from "../components/job-detail/SectionTitle";
import { SocialSearch } from "../components/job-detail/SocialSearch";
import { InterviewPanel } from "../components/InterviewPanel";
import { GeoBadge, LegitimacyBadge, RepostBadge } from "../components/JobBadges";
import { Badge } from "../components/ui/badge";
import { Button, buttonVariants } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { MatchIcon, ReferralIcon, SalaryIcon } from "../components/ui/icons";
import { ScoreRing } from "../components/ui/score-ring";
import { Skeleton } from "../components/ui/skeleton";
import { ErrorState } from "../components/ui/states";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "../components/ui/tooltip";
import { useJob, useMarkApplied, usePrepJob } from "../hooks/useJob";
import { useSetJobState } from "../hooks/useBoard";
import { STATE_ES, copy, fitTone, freshLabel, langLabel, pct, salaryLabel } from "../lib";

export function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const jobQ = useJob(id);
  const prep = usePrepJob();
  const markApplied = useMarkApplied();
  const setJobState = useSetJobState();

  if (jobQ.isPending) {
    return (
      <div className="mx-auto max-w-[860px] space-y-4">
        <Skeleton className="h-7 w-2/3" />
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (jobQ.isError || !jobQ.data) {
    return (
      <div className="mx-auto max-w-[860px]">
        <ErrorState title="No se pudo cargar la vacante" onRetry={() => jobQ.refetch()} />
      </div>
    );
  }

  const d = jobQ.data;
  const jobId = d.job.id;

  function doPrep() {
    if (prep.isPending) return;
    const tid = toast.loading("Preparando tu CV y mensajes…", {
      description: "Adapto el CV a esta oferta (ATS-safe) y redacto los mensajes.",
    });
    prep.mutate(
      { id: jobId },
      {
        onSuccess: (r) =>
          toast.success("CV y mensajes listos", {
            id: tid,
            description: `Cobertura ${pct(r.coverage)} · ${r.parse_ok ? "ATS ✓" : "revisar formato"}`,
          }),
        onError: () =>
          toast.error("No se pudo preparar", { id: tid, description: "Reintenta en un momento." }),
      },
    );
  }

  function doMarkApplied() {
    if (markApplied.isPending) return;
    markApplied.mutate(jobId, {
      onSuccess: () => toast.success("Marcado como aplicado"),
      onError: () => toast.error("No se pudo marcar como aplicado"),
    });
  }

  function doDismiss() {
    const prev = d.job.state || "shortlisted";
    setJobState.mutate(
      { id: jobId, state: "dismissed" },
      {
        onSuccess: () => {
          toast.success("Vacante descartada", {
            description: "No volverá a aparecer en tu tablero.",
            action: {
              label: "Deshacer",
              onClick: () => setJobState.mutate({ id: jobId, state: prev }),
            },
          });
          navigate("/pipeline");
        },
      },
    );
  }

  const cv = d.cv_versions[0];

  return (
    <div className="mx-auto max-w-[860px]">
      {/* header */}
      <button
        type="button"
        onClick={() => navigate("/pipeline")}
        className="mb-3 inline-flex items-center gap-1.5 text-[0.8rem] text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" /> Volver al pipeline
      </button>
      <div className="flex items-start gap-3">
        <ScoreRing value={d.job.fit_score} tone={fitTone(d.job.fit_score)} />
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-h1">{d.job.title}</h1>
          <div className="text-sm text-muted-foreground">{d.job.company}</div>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
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
        <GeoBadge job={d.job} />
        <RepostBadge job={d.job} />
        <LegitimacyBadge job={d.job} />
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
          <Badge variant="secondary">{freshLabel(d.job.posted_days ?? d.job.age_days)}</Badge>
        )}
        {(d.job.apply_url || d.job.url) && (
          <Button asChild variant="ghost" size="sm" className="h-7 px-2 text-xs">
            <a href={d.job.apply_url || d.job.url} target="_blank" rel="noreferrer">
              <ExternalLink className="size-3.5" /> Abrir oferta
            </a>
          </Button>
        )}
      </div>

      {/* tabs */}
      <Tabs defaultValue="resumen" className="mt-4">
        <TabsList>
          <TabsTrigger value="resumen">Resumen</TabsTrigger>
          <TabsTrigger value="cv">CV</TabsTrigger>
          <TabsTrigger value="mensajes">Mensajes</TabsTrigger>
          <TabsTrigger value="entrevistas">Entrevistas</TabsTrigger>
          <TabsTrigger value="research">Research</TabsTrigger>
        </TabsList>

        <TabsContent value="resumen" className="mt-4 space-y-4">
          <ScoreBreakdown job={d.job} />
          <JobOverview job={d.job} />
          {d.job.missing_keywords && d.job.missing_keywords.length > 0 && (
            <Card className="p-3.5 text-sm">
              <div className="mb-2 flex items-center gap-1.5 font-medium">
                <MatchIcon className="size-4 text-muted-foreground" /> Keywords de la oferta que tu
                CV no evidencia
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
          <CompanyInsights learnings={d.learnings} />
        </TabsContent>

        <TabsContent value="cv" className="mt-4 space-y-4">
          {cv ? (
            <div className="space-y-1.5">
              <div className="text-sm text-muted-foreground">
                Cobertura {pct(cv.keyword_coverage)} · {cv.parse_ok ? "ATS ✓" : "revisar formato"}
              </div>
              <div className="flex gap-2">
                {cv.path_pdf && (
                  <a
                    href={api.cvDownload(jobId, cv.id, "pdf")}
                    className={buttonVariants({ className: "flex-1" })}
                  >
                    <FileText className="size-4" /> CV PDF <Download className="size-3.5" />
                  </a>
                )}
                <a
                  href={api.cvDownload(jobId, cv.id, "docx")}
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
          ) : (
            <Card className="p-4 text-sm text-muted-foreground">
              Aún no hay CV adaptado para esta oferta — usa “Re-preparar” (abajo) para generarlo.
            </Card>
          )}
          <CvReviewPanel jobId={jobId} />
        </TabsContent>

        <TabsContent value="mensajes" className="mt-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <SectionTitle>Mensajes — qué enviar</SectionTitle>
            <IntentConfirmDialog
              buttonLabel="Carta personalizada"
              title="Carta de presentación personalizada (LLM)"
              what="El brain investiga la empresa en la web y redacta una carta específica para esta vacante, con tu voz (reglas anti-slop) y solo hechos de tu CV."
              produces="Un borrador nuevo tipo 'Carta de presentación' (variante brain)."
              where="Aquí, en la lista de mensajes, tras correr el brain."
              type="cover_letter"
              jobId={jobId}
            />
          </div>
          <div className="space-y-2">
            {d.messages.length === 0 && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="secondary"
                    className="w-full"
                    onClick={doPrep}
                    disabled={prep.isPending}
                  >
                    {prep.isPending && <Loader2 className="size-4 animate-spin" />}
                    {prep.isPending ? "Generando…" : "Generar borradores"}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  Adapta tu CV a esta oferta (ATS-safe) y redacta los mensajes de contacto. Reordena
                  solo lo que ya está en tu CV — nunca inventa. Determinista, sin IA.
                </TooltipContent>
              </Tooltip>
            )}
            {d.messages.map((m) => (
              <MessageCard key={m.id} m={m} />
            ))}
          </div>
        </TabsContent>

        <TabsContent value="entrevistas" className="mt-4">
          <InterviewPanel jobId={jobId} />
        </TabsContent>

        <TabsContent value="research" className="mt-4 space-y-4">
          <SocialSearch jobId={jobId} />
          <RecordOutcome jobId={jobId} onSaved={() => jobQ.refetch()} />
        </TabsContent>
      </Tabs>

      {/* barra de acciones */}
      <div className="sticky bottom-0 z-10 mt-6 flex gap-2 border-t border-border bg-background/85 py-3 backdrop-blur-xl">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" onClick={doDismiss} aria-label="Descartar">
              <Trash2 className="size-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Descartar — no me interesa (se puede deshacer)</TooltipContent>
        </Tooltip>
        <Button
          variant="secondary"
          className="flex-1"
          onClick={doMarkApplied}
          disabled={markApplied.isPending}
        >
          {markApplied.isPending && <Loader2 className="size-4 animate-spin" />}
          {markApplied.isPending ? "Marcando…" : "Marcar como aplicado"}
        </Button>
        <Button className="flex-1" onClick={doPrep} disabled={prep.isPending}>
          {prep.isPending && <Loader2 className="size-4 animate-spin" />}
          {prep.isPending ? "Preparando…" : "Re-preparar"}
        </Button>
      </div>
    </div>
  );
}
