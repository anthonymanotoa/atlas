import { ExternalLink } from "lucide-react";
import type { Action } from "../api";
import { ACTION_META } from "../lib";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { CelebrateIcon, actionIcon } from "./ui/icons";

export function NeedsAction({
  actions,
  onOpen,
}: {
  actions: Action[];
  onOpen: (id: string) => void;
}) {
  if (actions.length === 0) {
    return (
      <Card className="fade-up flex flex-col items-center gap-1.5 px-5 py-8 text-center">
        <div className="grid size-11 place-items-center rounded-full bg-success/15 text-success">
          <CelebrateIcon className="size-5" />
        </div>
        <div className="text-h3 font-semibold">Todo al día</div>
        <div className="text-sm text-muted-foreground">No hay nada pendiente ahora mismo.</div>
      </Card>
    );
  }
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center gap-2">
        <h2 className="text-caption text-muted-foreground uppercase">Acciones para hoy</h2>
        <Badge variant="secondary">{actions.length}</Badge>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-1">
        {actions.map((a, i) => {
          const tone = (ACTION_META[a.type] || { tone: "var(--color-muted)" }).tone;
          const Icon = actionIcon(a.type);
          return (
            <Card
              key={`${a.job_id}-${i}`}
              onClick={() => onOpen(a.job_id)}
              style={{ borderLeftColor: tone, borderLeftWidth: 3, animationDelay: `${i * 40}ms` }}
              className="fade-up min-w-[290px] max-w-[290px] cursor-pointer p-4 transition-[transform,box-shadow,border-color] duration-[120ms] ease-[var(--ease-out)] hover:-translate-y-0.5 hover:shadow-[var(--shadow-md)]"
            >
              <div className="flex items-center gap-2 text-sm font-medium" style={{ color: tone }}>
                <span
                  className="grid size-6 place-items-center rounded-md"
                  style={{ background: `color-mix(in oklch, ${tone} 16%, transparent)` }}
                >
                  <Icon className="size-3.5" />
                </span>
                <span>{a.label}</span>
              </div>
              <div className="mt-2 truncate text-[0.95rem] font-medium text-foreground">
                {a.title}
              </div>
              <div className="text-[0.8rem] text-muted-foreground">{a.company}</div>
              {a.link && (
                <Button
                  asChild
                  variant="ghost"
                  size="sm"
                  className="mt-2.5 h-7 px-2 text-xs text-muted-foreground"
                >
                  <a
                    href={a.link}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <ExternalLink className="size-3.5" /> Abrir
                  </a>
                </Button>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
