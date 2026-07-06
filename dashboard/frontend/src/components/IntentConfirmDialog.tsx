import { Sparkles } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { useEnqueueIntent } from "../hooks/useIntents";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "./ui/dialog";

type Props = {
  buttonLabel: string;
  title: string;
  what: string; // qué hace
  produces: string; // qué producirá
  where: string; // dónde aparecerá el resultado
  type: string;
  jobId?: string;
  payload?: Record<string, unknown>;
  onQueued?: (intentId: string) => void;
};

// Todo botón LLM de la web pasa por aquí: explica qué hace, qué produce y dónde aparecerá,
// y deja claro que NO corre ahora — queda en la cola del brain (guided handoff, $0). Al encolar,
// useEnqueueIntent invalida la cola, así que el panel Tareas del Brain se actualiza solo.
export function IntentConfirmDialog({
  buttonLabel,
  title,
  what,
  produces,
  where,
  type,
  jobId,
  payload,
  onQueued,
}: Props) {
  const [open, setOpen] = useState(false);
  const enqueue = useEnqueueIntent();

  async function queue() {
    try {
      const r = await enqueue.mutateAsync({ type, payload, jobId });
      toast.success("Encolado. Corre el brain para ejecutarlo (panel Tareas del Brain).");
      onQueued?.(r.id);
      setOpen(false);
    } catch (e) {
      toast.error(String(e));
    }
  }

  return (
    <>
      <Button variant="secondary" size="sm" onClick={() => setOpen(true)}>
        <Sparkles className="size-3.5" /> {buttonLabel}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription asChild>
            <div className="space-y-2 text-sm">
              <p>
                <b className="font-medium text-foreground">Qué hace:</b> {what}
              </p>
              <p>
                <b className="font-medium text-foreground">Qué produce:</b> {produces}
              </p>
              <p>
                <b className="font-medium text-foreground">Dónde aparece:</b> {where}
              </p>
              <p className="text-muted-foreground">
                No corre ahora: queda en la cola del brain. Para ejecutarla, abre Claude Code en{" "}
                <code className="font-mono">~/dev/personal/atlas</code> y di{" "}
                <code className="font-mono">corre atlas</code>.
              </p>
            </div>
          </DialogDescription>
          <div className="mt-2 flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button size="sm" disabled={enqueue.isPending} onClick={queue}>
              Encolar para el brain
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
