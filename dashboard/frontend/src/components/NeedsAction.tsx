import { ExternalLink } from "lucide-react";
import type { Action } from "../api";
import { ACTION_META } from "../lib";

export function NeedsAction({
  actions,
  onOpen,
}: {
  actions: Action[];
  onOpen: (id: string) => void;
}) {
  if (actions.length === 0) {
    return (
      <div className="card px-5 py-6 text-center fade-up">
        <div className="text-lg">🎉 Todo al día</div>
        <div className="text-[var(--color-muted)] text-sm mt-1">
          No hay nada pendiente ahora mismo.
        </div>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold tracking-wide">Acciones para hoy</h2>
        <span className="chip">{actions.length}</span>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-1">
        {actions.map((a, i) => {
          const meta = ACTION_META[a.type] || { icon: "•", tone: "var(--color-muted)" };
          return (
            <div
              key={`${a.job_id}-${i}`}
              className="card px-4 py-3 min-w-[290px] max-w-[290px] fade-up cursor-pointer hover:border-[var(--color-accent)] transition"
              style={{ borderLeft: `3px solid ${meta.tone}` }}
              onClick={() => onOpen(a.job_id)}
            >
              <div
                className="flex items-center gap-2 text-sm font-medium"
                style={{ color: meta.tone }}
              >
                <span>{meta.icon}</span>
                <span>{a.label}</span>
              </div>
              <div className="text-[0.95rem] mt-1.5 truncate font-medium">{a.title}</div>
              <div className="text-[0.8rem] text-[var(--color-muted)]">{a.company}</div>
              {a.link && (
                <a
                  href={a.link}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="btn mt-2 !py-1 !px-2 text-xs"
                >
                  <ExternalLink size={13} /> Abrir
                </a>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
