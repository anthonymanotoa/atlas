import { RotateCcw, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import type { Job } from "../api";
import { Board } from "../components/Board";
import { FilterBar, type Filters } from "../components/FilterBar";
import { IntentConfirmDialog } from "../components/IntentConfirmDialog";
import { NeedsAction } from "../components/NeedsAction";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { CvTemplateIcon, DowntimeIcon } from "../components/ui/icons";
import { ErrorState, LoadingState } from "../components/ui/states";
import { useBoard, useSetJobState } from "../hooks/useBoard";
import { useOverview } from "../hooks/useOverview";

export function PipelinePage() {
  const navigate = useNavigate();
  const overviewQ = useOverview();
  const boardQ = useBoard();
  const setJobState = useSetJobState();
  const [showDismissed, setShowDismissed] = useState(false);
  const [filters, setFilters] = useState<Filters>({
    onlySalary: false,
    language: "",
    maxAgeDays: 0,
  });

  const jobs = useMemo(() => boardQ.data?.jobs ?? {}, [boardQ.data]);
  const columns = boardQ.data?.columns ?? [];
  const dismissed = boardQ.data?.dismissed ?? [];
  const shortlistIds = useMemo(() => (jobs.shortlisted ?? []).map((j) => j.id), [jobs]);
  const actions = overviewQ.data?.needs_action ?? [];
  const ov = overviewQ.data?.overview;

  const allJobs = Object.values(jobs).flat();
  const languages = Array.from(
    new Set(allJobs.map((j) => j.language).filter((l): l is string => !!l)),
  ).sort();
  const filteredJobs = useMemo(() => {
    const out: Record<string, Job[]> = {};
    for (const c of Object.keys(jobs)) {
      out[c] = jobs[c].filter((j) => {
        const age = j.posted_days ?? j.age_days;
        return (
          (!filters.onlySalary || j.salary_visible) &&
          (!filters.language || j.language === filters.language) &&
          (!filters.maxAgeDays || age == null || age <= filters.maxAgeDays)
        );
      });
    }
    return out;
  }, [jobs, filters]);

  const open = (id: string) => navigate(`/jobs/${id}`);
  const move = (jobId: string, to: string) => setJobState.mutate({ id: jobId, state: to });

  function dismiss(jobId: string, from: string) {
    setJobState.mutate(
      { id: jobId, state: "dismissed" },
      {
        onSuccess: () =>
          toast.success("Vacante descartada", {
            description: "No volverá a aparecer en tu tablero.",
            action: {
              label: "Deshacer",
              onClick: () => setJobState.mutate({ id: jobId, state: from }),
            },
          }),
      },
    );
  }

  function restore(jobId: string) {
    setJobState.mutate(
      { id: jobId, state: "shortlisted" },
      { onSuccess: () => toast.success("Vacante restaurada a Preseleccionados") },
    );
  }

  if (boardQ.isPending || overviewQ.isPending) return <LoadingState rows={4} />;
  if (boardQ.isError) return <ErrorState onRetry={() => boardQ.refetch()} />;

  return (
    <>
      {ov?.cv_template_findings && ov.cv_template_findings.length > 0 ? (
        <Card className="mb-4 flex items-center gap-2 border-destructive/50 bg-destructive/10 p-3 text-sm">
          <CvTemplateIcon className="size-4 shrink-0 text-destructive" />
          Tu CV master es la plantilla — nada de lo generado es enviable. Completa tu CV real y
          corre <code className="font-mono">atlas cv promote</code>.
        </Card>
      ) : null}

      {ov?.downtime_hours ? (
        <Card className="mb-4 flex items-center gap-2 border-warning/50 p-3 text-sm">
          <DowntimeIcon className="size-4 shrink-0 text-warning" />
          Estuve sin correr ~{Math.round(ov.downtime_hours)}h. Revisa que el Mac esté despierto y
          Claude Desktop abierto.
        </Card>
      ) : null}

      <div className="mb-6">
        <NeedsAction actions={actions} onOpen={open} />
      </div>

      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <FilterBar filters={filters} setFilters={setFilters} languages={languages} />
        {shortlistIds.length > 0 && (
          <IntentConfirmDialog
            buttonLabel="Verificar legitimidad"
            title="Legitimidad del shortlist (Block G)"
            what="El brain evalúa cada vacante preseleccionada con una tabla de señales ponderadas (edad del posting, especificidad técnica, dominio, coherencia) e investiga brevemente cada empresa."
            produces="Un tier alta/media/baja + notas de señales por vacante (observaciones, nunca acusaciones)."
            where="Como badge en cada card del tablero y en el detalle de la vacante."
            type="legitimacy_batch"
            payload={{ job_ids: shortlistIds }}
          />
        )}
      </div>
      <Board
        columns={columns}
        jobs={filteredJobs}
        onOpen={open}
        onMove={move}
        onDismiss={dismiss}
      />

      {dismissed.length > 0 && (
        <div className="mt-5">
          <button
            type="button"
            onClick={() => setShowDismissed((v) => !v)}
            className="inline-flex items-center gap-1.5 text-caption text-muted-foreground uppercase transition-colors hover:text-foreground"
          >
            <Trash2 className="size-3.5" />
            Descartadas ({dismissed.length}) {showDismissed ? "▾" : "▸"}
          </button>
          {showDismissed && (
            <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {dismissed.map((j) => (
                <Card key={j.id} className="flex items-center justify-between gap-2 p-3 text-sm">
                  <button type="button" onClick={() => open(j.id)} className="min-w-0 text-left">
                    <div className="truncate font-medium">{j.title}</div>
                    <div className="truncate text-xs text-muted-foreground">{j.company}</div>
                  </button>
                  <Button variant="secondary" size="sm" onClick={() => restore(j.id)}>
                    <RotateCcw className="size-3.5" /> Restaurar
                  </Button>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );
}
