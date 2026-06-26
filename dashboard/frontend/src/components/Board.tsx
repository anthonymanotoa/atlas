import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  useDraggable,
  useDroppable,
  type DragEndEvent,
} from "@dnd-kit/core";
import { MapPin, Users, X } from "lucide-react";
import type { Job } from "../api";
import { COLUMN_ES, ageLabel, cn, fitTone, freshLabel, langLabel, salaryLabel } from "../lib";
import { Badge } from "./ui/badge";
import { KnockoutIcon, MatchIcon, SalaryIcon } from "./ui/icons";
import { ScoreRing } from "./ui/score-ring";

function monogram(company: string): string {
  return (company || "·").trim().charAt(0).toUpperCase();
}

function JobCard({
  job,
  column,
  onOpen,
  onDismiss,
}: {
  job: Job;
  column: string;
  onOpen: (id: string) => void;
  onDismiss?: (id: string, from: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: job.id,
    data: { from: column },
  });
  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`, zIndex: 50 }
    : undefined;
  const remote = job.is_remote === 1 ? "Remoto" : job.is_remote === 0 ? "No remoto" : "Remoto?";
  const sal = salaryLabel(job);
  const posted = job.posted_days ?? job.age_days;
  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      onClick={() => !isDragging && onOpen(job.id)}
      className={cn(
        "group relative mb-2 cursor-grab rounded-xl border border-border bg-card px-3 py-2.5 shadow-[var(--shadow-sm),var(--highlight-top)] transition-[transform,box-shadow,border-color] duration-[120ms] ease-[var(--ease-out)] select-none active:cursor-grabbing",
        isDragging
          ? "scale-[1.02] rotate-[0.6deg] opacity-90 shadow-[var(--shadow-lg)] ring-1 ring-primary"
          : "hover:-translate-y-0.5 hover:border-[color-mix(in_oklch,var(--primary)_45%,var(--border))] hover:shadow-[var(--shadow-md)]",
      )}
    >
      {onDismiss && (
        <button
          type="button"
          aria-label="Descartar"
          title="Descartar — no me interesa"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => {
            e.stopPropagation();
            onDismiss(job.id, column);
          }}
          className="absolute top-1.5 right-1.5 z-20 grid size-6 place-items-center rounded-md bg-background/80 text-muted-foreground opacity-0 backdrop-blur transition-[opacity,color,background-color] group-hover:opacity-100 hover:bg-destructive/15 hover:text-destructive focus-visible:opacity-100"
        >
          <X className="size-3.5" />
        </button>
      )}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="line-clamp-2 pr-6 text-[0.9rem] leading-snug font-medium">
            {job.title}
          </div>
          <div className="mt-1 flex items-center gap-1.5 text-[0.8rem] text-muted-foreground">
            <span className="grid size-4 shrink-0 place-items-center rounded bg-secondary text-[0.6rem] font-semibold text-foreground">
              {monogram(job.company)}
            </span>
            <span className="truncate">{job.company}</span>
          </div>
        </div>
        <ScoreRing value={job.fit_score} tone={fitTone(job.fit_score)} size={36} />
      </div>
      <div className="mt-2.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[0.7rem] text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <MapPin className="size-3" /> {remote}
        </span>
        {posted != null && <span title={freshLabel(posted)}>· {ageLabel(posted)}</span>}
        {job.language && (
          <Badge variant="secondary" className="px-1.5 py-0 text-[0.62rem] uppercase">
            {langLabel(job.language)}
          </Badge>
        )}
        {sal && (
          <span className="inline-flex items-center gap-1" title="Salario publicado">
            <SalaryIcon className="size-3" /> {sal}
          </span>
        )}
        {job.match_score != null && (
          <span
            className="inline-flex items-center gap-1 tabular-nums"
            title="Match CV↔oferta (cobertura de keywords)"
            style={{ color: fitTone(job.match_score) }}
          >
            <MatchIcon className="size-3" /> {job.match_score}%
          </span>
        )}
        {job.knockout_flags && job.knockout_flags.length > 0 && (
          <span
            className="inline-flex items-center text-warning"
            title="Filtros del puesto (p. ej. requisitos de elegibilidad)"
          >
            <KnockoutIcon className="size-3" />
          </span>
        )}
        {job.sources && job.sources.length > 1 && (
          <span className="inline-flex items-center gap-1">
            <Users className="size-3" />
            {job.sources.length}
          </span>
        )}
      </div>
    </div>
  );
}

function Column({
  id,
  jobs,
  onOpen,
  onDismiss,
}: {
  id: string;
  jobs: Job[];
  onOpen: (id: string) => void;
  onDismiss?: (id: string, from: string) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id });
  return (
    <div className="flex max-w-[268px] min-w-[268px] flex-col">
      <div className="sticky top-0 z-10 mb-2 flex items-center gap-2 px-1">
        <span className="text-caption text-muted-foreground uppercase">{COLUMN_ES[id] || id}</span>
        <Badge variant="secondary" className="px-1.5 py-0">
          {jobs.length}
        </Badge>
      </div>
      <div
        ref={setNodeRef}
        className={cn(
          "min-h-[120px] flex-1 rounded-xl p-1.5 transition-colors",
          isOver
            ? "bg-secondary/50 ring-1 ring-dashed ring-primary"
            : "bg-transparent ring-1 ring-transparent",
        )}
      >
        {jobs.length === 0 ? (
          <div className="px-2 py-8 text-center text-[0.75rem] text-muted-foreground/60">vacío</div>
        ) : (
          jobs.map((j) => (
            <JobCard key={j.id} job={j} column={id} onOpen={onOpen} onDismiss={onDismiss} />
          ))
        )}
      </div>
    </div>
  );
}

export function Board({
  columns,
  jobs,
  onOpen,
  onMove,
  onDismiss,
}: {
  columns: string[];
  jobs: Record<string, Job[]>;
  onOpen: (id: string) => void;
  onMove: (jobId: string, to: string) => void;
  onDismiss?: (id: string, from: string) => void;
}) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  function handleEnd(e: DragEndEvent) {
    const { active, over } = e;
    if (!over) return;
    const from = (active.data.current as { from?: string })?.from;
    if (over.id !== from) onMove(String(active.id), String(over.id));
  }
  return (
    <DndContext sensors={sensors} onDragEnd={handleEnd}>
      <div className="flex gap-3 overflow-x-auto pb-3">
        {columns.map((c) => (
          <Column key={c} id={c} jobs={jobs[c] || []} onOpen={onOpen} onDismiss={onDismiss} />
        ))}
      </div>
    </DndContext>
  );
}
