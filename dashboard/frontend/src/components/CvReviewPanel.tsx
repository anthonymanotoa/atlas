import { Check, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { type CvReviewFlag } from "../api";
import { useApplyCvReviewEdit, useCvReviews, useResolveCvReviewFlag } from "../hooks/useCvReviews";
import { IntentConfirmDialog } from "./IntentConfirmDialog";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Separator } from "./ui/separator";

// Etiquetas en español de las 4 categorías obligatorias de la crítica (spec §7.2).
const CRITIQUE_ES: Record<string, string> = {
  missed_keywords: "Keywords desaprovechados",
  company_angles: "Ángulos específicos de la empresa",
  reframing: "Reframing accionable",
  tone_register: "Tono y registro",
};

// El backtrack test clasifica cada bullet reformulado: OK (defendible) / Flag (defendible con
// cuidado) / Never (indefendible, el reviewer ya lo rechazó). Cada clasificación tiene su tono.
const FLAG_VARIANT: Record<CvReviewFlag["classification"], "success" | "warning" | "destructive"> =
  {
    OK: "success",
    Flag: "warning",
    Never: "destructive",
  };

// F4 §7.2: la revisión LLM del CV/carta para ESTA vacante. La web muestra la crítica, aplica los
// edits uno a uno (cada uno re-renderiza el CV) y resuelve los flags (mantener/suavizar/eliminar).
// Todo el trabajo LLM lo hizo el brain — aquí solo se leen resultados y se disparan acciones $0.
export function CvReviewPanel({ jobId }: { jobId: string }) {
  const reviewsQ = useCvReviews(jobId);
  const applyEdit = useApplyCvReviewEdit(jobId);
  const resolveFlag = useResolveCvReviewFlag(jobId);
  const review = reviewsQ.data?.reviews[0];

  function onApplyEdit(index: number) {
    if (!review) return;
    applyEdit.mutate(
      { id: review.id, index },
      {
        onSuccess: () => toast.success("Edit aplicado — CV re-renderizado"),
        onError: (e) => toast.error(String(e)),
      },
    );
  }

  function onResolveFlag(index: number, action: "keep" | "soften" | "drop") {
    if (!review) return;
    resolveFlag.mutate(
      { id: review.id, index, action },
      {
        onSuccess: () =>
          toast.success(
            action === "keep"
              ? "Bullet conservado"
              : action === "soften"
                ? "Bullet suavizado — CV re-renderizado"
                : "Bullet eliminado — CV re-renderizado",
          ),
        onError: (e) => toast.error(String(e)),
      },
    );
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <div className="text-caption uppercase text-muted-foreground">Revisión LLM del CV</div>
        <IntentConfirmDialog
          buttonLabel="Pedir revisión"
          title="Revisión de CV/carta (hiring-manager proxy)"
          what="Un reviewer LLM con contexto fresco critica tu CV y tus mensajes para ESTA vacante, investiga la empresa en la web y pasa cada reframe por el backtrack test."
          produces="Edits aplicables uno a uno, crítica en 4 categorías y flags para resolver (mantener / suavizar / eliminar)."
          where="En esta misma sección, tras correr el brain."
          type="cv_review"
          jobId={jobId}
        />
      </div>
      {!review && (
        <Card className="p-3.5 text-sm text-muted-foreground">
          Sin revisiones todavía. Pide una y corre el brain.
        </Card>
      )}
      {review && (
        <Card className="space-y-3 p-3.5 text-sm">
          {Object.entries(CRITIQUE_ES).map(([k, label]) => (
            <div key={k}>
              <div className="text-caption font-medium uppercase text-muted-foreground">
                {label}
              </div>
              <ul className="mt-1 list-disc pl-4">
                {(review.critique[k] || []).map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          ))}

          {review.edits.length > 0 && (
            <>
              <Separator />
              <div className="text-caption font-medium uppercase text-muted-foreground">
                Edits propuestos
              </div>
              {review.edits.map((e, i) => (
                <div key={i} className="rounded-md bg-secondary/50 p-2.5">
                  <Badge variant="secondary">{e.file}</Badge>
                  <div className="mt-1 line-through opacity-60">{e.old_string}</div>
                  <div>{e.new_string}</div>
                  <div className="mt-1 text-muted-foreground">{e.reason}</div>
                  <Button
                    className="mt-1.5"
                    variant="secondary"
                    size="sm"
                    disabled={!!e.applied || applyEdit.isPending}
                    onClick={() => onApplyEdit(i)}
                  >
                    {e.applied ? <Check className="size-3.5" /> : <Wand2 className="size-3.5" />}
                    {e.applied ? "Aplicado" : "Aplicar"}
                  </Button>
                </div>
              ))}
            </>
          )}

          {review.flags.length > 0 && (
            <>
              <Separator />
              <div className="text-caption font-medium uppercase text-muted-foreground">
                Flags (backtrack test)
              </div>
              {review.flags.map((f, i) => (
                <div key={i} className="rounded-md bg-secondary/50 p-2.5">
                  <Badge variant={FLAG_VARIANT[f.classification]}>{f.classification}</Badge>
                  <div className="mt-1">{f.bullet}</div>
                  <div className="mt-1 text-muted-foreground">{f.reason}</div>
                  {f.softened && <div className="mt-1 italic">Suave: {f.softened}</div>}
                  {f.classification === "Flag" && !f.resolution ? (
                    <div className="mt-1.5 flex gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={resolveFlag.isPending}
                        onClick={() => onResolveFlag(i, "keep")}
                      >
                        Mantener
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={!f.softened || resolveFlag.isPending}
                        onClick={() => onResolveFlag(i, "soften")}
                      >
                        Suavizar
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={resolveFlag.isPending}
                        onClick={() => onResolveFlag(i, "drop")}
                      >
                        Eliminar
                      </Button>
                    </div>
                  ) : (
                    f.resolution && (
                      <div className="mt-1 text-muted-foreground">Resuelto: {f.resolution}</div>
                    )
                  )}
                </div>
              ))}
            </>
          )}
        </Card>
      )}
    </div>
  );
}
