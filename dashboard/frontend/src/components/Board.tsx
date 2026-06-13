import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  useDraggable,
  useDroppable,
  type DragEndEvent,
} from "@dnd-kit/core";
import { Banknote, MapPin, Users } from "lucide-react";
import type { Job } from "../api";
import { COLUMN_ES, ageLabel, cn, fitTone, freshLabel, langLabel, salaryLabel } from "../lib";

function JobCard({
  job,
  column,
  onOpen,
}: {
  job: Job;
  column: string;
  onOpen: (id: string) => void;
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
        "card px-3 py-2.5 mb-2 cursor-grab active:cursor-grabbing select-none transition",
        isDragging ? "opacity-60 shadow-2xl" : "hover:border-[var(--color-accent)]",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="text-[0.9rem] font-medium leading-snug line-clamp-2">{job.title}</div>
        <span
          className="chip shrink-0 !px-2 font-semibold"
          style={{ color: fitTone(job.fit_score), borderColor: fitTone(job.fit_score) }}
        >
          {job.fit_score ?? "—"}
        </span>
      </div>
      <div className="text-[0.8rem] text-[var(--color-muted)] mt-1 truncate">{job.company}</div>
      <div className="flex items-center gap-x-2 gap-y-1 mt-2 text-[0.7rem] text-[var(--color-faint)] flex-wrap">
        <span className="inline-flex items-center gap-1">
          <MapPin size={11} /> {remote}
        </span>
        {posted != null && <span title={freshLabel(posted)}>· {ageLabel(posted)}</span>}
        {job.language && (
          <span className="chip !px-1.5 !py-0 uppercase">{langLabel(job.language)}</span>
        )}
        {sal && (
          <span className="inline-flex items-center gap-1" title="Salario publicado">
            <Banknote size={11} /> {sal}
          </span>
        )}
        {job.match_score != null && (
          <span
            title="Match CV↔oferta (cobertura de keywords)"
            style={{ color: fitTone(job.match_score) }}
          >
            🎯 {job.match_score}%
          </span>
        )}
        {job.knockout_flags && job.knockout_flags.length > 0 && (
          <span
            title="Filtros del puesto (clearance/ciudadanía)"
            className="text-[var(--color-pending)]"
          >
            ⚑
          </span>
        )}
        {job.sources && job.sources.length > 1 && (
          <span className="inline-flex items-center gap-1">
            <Users size={11} />
            {job.sources.length}
          </span>
        )}
      </div>
    </div>
  );
}

function Column({ id, jobs, onOpen }: { id: string; jobs: Job[]; onOpen: (id: string) => void }) {
  const { setNodeRef, isOver } = useDroppable({ id });
  return (
    <div className="flex flex-col min-w-[260px] max-w-[260px]">
      <div className="flex items-center gap-2 px-1 mb-2">
        <span className="text-[0.8rem] font-semibold uppercase tracking-wide text-[var(--color-muted)]">
          {COLUMN_ES[id] || id}
        </span>
        <span className="chip !px-1.5">{jobs.length}</span>
      </div>
      <div
        ref={setNodeRef}
        className={cn(
          "flex-1 rounded-xl p-1.5 transition min-h-[120px]",
          isOver ? "bg-[var(--color-panel2)] ring-1 ring-[var(--color-accent)]" : "bg-transparent",
        )}
      >
        {jobs.length === 0 ? (
          <div className="text-[0.75rem] text-[var(--color-faint)] px-2 py-6 text-center">
            vacío
          </div>
        ) : (
          jobs.map((j) => <JobCard key={j.id} job={j} column={id} onOpen={onOpen} />)
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
}: {
  columns: string[];
  jobs: Record<string, Job[]>;
  onOpen: (id: string) => void;
  onMove: (jobId: string, to: string) => void;
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
          <Column key={c} id={c} jobs={jobs[c] || []} onOpen={onOpen} />
        ))}
      </div>
    </DndContext>
  );
}
