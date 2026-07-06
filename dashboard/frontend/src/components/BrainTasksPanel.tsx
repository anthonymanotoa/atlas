import { BrainCircuit, Check, Copy, RefreshCw } from "lucide-react";
import { useState } from "react";
import type { Intent } from "../api";
import { useIntents } from "../hooks/useIntents";
import { copy } from "../lib";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { ScrollArea } from "./ui/scroll-area";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "./ui/sheet";

// Etiqueta humana (ES) por tipo de intent. Fallback al type crudo si aparece uno nuevo.
// Local al panel (no se exporta): solo esta vista traduce el `type` del intent a copy de UI.
const INTENT_LABEL: Record<string, string> = {
  cv_review: "Revisión LLM de CV/carta",
  legitimacy_batch: "Legitimidad de vacantes",
  upskill_report: "Análisis de gaps (upskill)",
  interview_prep_deep: "Prep profundo de entrevista",
  profile_expand: "Expandir perfil",
  cover_letter: "Carta personalizada",
};

const STATUS_ES: Record<Intent["status"], string> = {
  pending: "pendiente",
  running: "en curso",
  done: "lista",
  error: "error",
};

const STATUS_VARIANT: Record<Intent["status"], "secondary" | "info" | "success" | "destructive"> = {
  pending: "secondary",
  running: "info",
  done: "success",
  error: "destructive",
};

// La ÚNICA frase que el usuario debe aprenderse (spec §7.1). El SKILL del brain hace el resto.
export const BRAIN_PHRASE = "Abre Claude Code en ~/dev/personal/atlas y di: corre atlas";

export function BrainTasksPanel() {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const q = useIntents();
  const rows = q.data?.intents ?? [];
  const pending = q.data?.pending ?? 0;

  async function copyPhrase() {
    await copy(BRAIN_PHRASE);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  }

  return (
    <>
      <Button
        variant="secondary"
        size="sm"
        aria-label="Tareas del Brain"
        onClick={() => setOpen(true)}
      >
        <BrainCircuit className="size-3.5" /> Tareas del Brain
        {pending > 0 && (
          <Badge className="ml-1 tabular-nums" aria-label={`${pending} pendientes`}>
            {pending}
          </Badge>
        )}
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent className="w-[420px] gap-0 p-5 sm:max-w-[420px]">
          <SheetTitle>Tareas del Brain</SheetTitle>
          <SheetDescription className="mt-1">
            Trabajos que necesitan LLM. La web solo los encola ($0): se ejecutan cuando corres el
            brain en Claude Code, y los resultados aparecen aquí y en cada vacante.
          </SheetDescription>

          <Card className="mt-4 space-y-2 p-3.5 text-sm">
            <div className="text-caption text-muted-foreground uppercase">Para ejecutarlas</div>
            <pre className="rounded-lg border border-border bg-secondary p-2.5 font-mono text-[0.78rem] whitespace-pre-wrap">
              {BRAIN_PHRASE}
            </pre>
            <Button variant="secondary" size="sm" onClick={copyPhrase}>
              {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}{" "}
              {copied ? "Copiado" : "Copiar instrucción"}
            </Button>
          </Card>

          <div className="mt-4 flex items-center justify-between">
            <div className="text-caption text-muted-foreground uppercase">Cola ({rows.length})</div>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Refrescar"
              onClick={() => q.refetch()}
            >
              <RefreshCw className={q.isFetching ? "size-3.5 animate-spin" : "size-3.5"} />
            </Button>
          </div>

          <ScrollArea className="mt-2 max-h-[55vh]">
            <div className="space-y-2 pr-2">
              {rows.length === 0 && (
                <div className="text-[0.8rem] text-muted-foreground">
                  Sin tareas. Encólalas desde los botones LLM de cada vacante.
                </div>
              )}
              {rows.map((it) => (
                <Card key={it.id} className="p-2.5 text-[0.8rem]">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{INTENT_LABEL[it.type] || it.type}</span>
                    <Badge variant={STATUS_VARIANT[it.status]}>{STATUS_ES[it.status]}</Badge>
                  </div>
                  <div className="mt-0.5 text-muted-foreground tabular-nums">
                    {it.job_id ? `Vacante ${it.job_id} · ` : ""}
                    {(it.created_at || "").slice(0, 16).replace("T", " ")}
                  </div>
                  {it.status === "done" && it.result_ref && (
                    <div className="mt-1 font-mono text-[0.74rem] text-muted-foreground">
                      → {it.result_ref}
                    </div>
                  )}
                  {it.error && (
                    <div className="mt-1 text-[0.76rem] text-destructive">⚠︎ {it.error}</div>
                  )}
                </Card>
              ))}
            </div>
          </ScrollArea>
        </SheetContent>
      </Sheet>
    </>
  );
}
