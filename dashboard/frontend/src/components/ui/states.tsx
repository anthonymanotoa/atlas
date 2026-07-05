import type { LucideIcon } from "lucide-react";
import { CircleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Button } from "./button";
import { Card } from "./card";
import { Skeleton } from "./skeleton";

// Estados compartidos de página (spec v2 §4.3): skeletons y mensajes accionables
// consistentes en todas las vistas. Componer SIEMPRE estos, no ad-hoc.

export function LoadingState({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-3", className)} aria-busy="true">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className={i === 0 ? "h-24 w-full" : "h-16 w-full"} />
      ))}
    </div>
  );
}

export function ErrorState({
  title = "No se pudo cargar",
  description = "Revisa que el backend esté corriendo (scripts/run.sh) y reintenta.",
  onRetry,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
}) {
  return (
    <Card className="flex flex-col items-center gap-2 px-5 py-8 text-center">
      <div className="grid size-11 place-items-center rounded-full bg-destructive/15 text-destructive">
        <CircleAlert className="size-5" />
      </div>
      <div className="text-h3 font-semibold">{title}</div>
      <div className="max-w-[48ch] text-sm text-muted-foreground">{description}</div>
      {onRetry && (
        <Button variant="secondary" size="sm" className="mt-2" onClick={onRetry}>
          Reintentar
        </Button>
      )}
    </Card>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <Card className="flex flex-col items-center gap-1.5 px-5 py-8 text-center">
      {Icon && (
        <div className="grid size-11 place-items-center rounded-full bg-secondary text-muted-foreground">
          <Icon className="size-5" />
        </div>
      )}
      <div className="text-h3 font-semibold">{title}</div>
      {description && <div className="text-sm text-muted-foreground">{description}</div>}
      {action && <div className="mt-2">{action}</div>}
    </Card>
  );
}
