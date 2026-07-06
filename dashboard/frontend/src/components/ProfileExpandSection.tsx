import { Check } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import type { ProfileExpandItem } from "../api";
import { useApplyProfileExpansion, useProfileExpansions } from "../hooks/useProfileExpansions";
import { IntentConfirmDialog } from "./IntentConfirmDialog";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Checkbox } from "./ui/checkbox";
import { ErrorState, LoadingState } from "./ui/states";

const TARGET_ES: Record<ProfileExpandItem["target"], string> = {
  skills: "Skill",
  experience_highlight: "Highlight",
  project: "Proyecto",
  certification: "Certificación",
};

// El value puede ser un string (skill) o un objeto ({name}/{highlight}/…). Etiqueta legible.
function itemLabel(it: ProfileExpandItem): string {
  if (typeof it.value === "string") return it.value;
  const v = (it.value ?? {}) as Record<string, unknown>;
  return String(v.name ?? v.highlight ?? JSON.stringify(v));
}

// F4 §7.2 profile_expand: revisión con confirmación POR ÍTEM del borrador de expansión del perfil.
// El brain propuso adiciones con fuente anotada; aquí el usuario marca cuáles aplicar y solo esas
// se escriben al master CV (aditivo, idempotente). El escaneo lo hizo el brain offline ($0).
export function ProfileExpandSection() {
  const expansionsQ = useProfileExpansions();
  const applyMut = useApplyProfileExpansion();
  const [picked, setPicked] = useState<Set<number>>(new Set());

  const exp = expansionsQ.data?.expansions[0] ?? null;

  function toggle(i: number) {
    setPicked((s) => {
      const n = new Set(s);
      if (n.has(i)) n.delete(i);
      else n.add(i);
      return n;
    });
  }

  function applyPicked() {
    if (!exp || picked.size === 0) return;
    applyMut.mutate(
      { id: exp.id, indices: [...picked] },
      {
        onSuccess: (r) => {
          toast.success(`Aplicados ${r.applied}, ya existían ${r.skipped_existing}.`);
          setPicked(new Set());
        },
        onError: (e) => toast.error(String(e)),
      },
    );
  }

  const scanButton = (
    <IntentConfirmDialog
      buttonLabel="Escanear y proponer"
      title="Expandir perfil desde GitHub / portfolio / certs"
      what="El brain escanea tu GitHub, tu portfolio y los syllabi oficiales de tus certs para encontrar evidencia que aún no está en tu CV. Todo aditivo y con fuente anotada."
      produces="Un borrador de adiciones que confirmas una por una antes de que toquen tu CV."
      where="Aquí, en Ajustes, tras correr el brain."
      type="profile_expand"
    />
  );

  return (
    <section>
      <div className="mb-1 flex items-center justify-between gap-2">
        <div className="text-sm font-semibold">Expandir perfil</div>
        {scanButton}
      </div>
      <div className="mb-3 text-[0.75rem] text-muted-foreground">
        Adiciones a tu CV que el brain encontró en fuentes públicas (GitHub, portfolio, certs).
        Confirma cada una antes de que se escriba en tu perfil.
      </div>

      {expansionsQ.isPending && <LoadingState rows={2} />}
      {expansionsQ.isError && <ErrorState onRetry={() => expansionsQ.refetch()} />}

      {expansionsQ.isSuccess && !exp && (
        <Card className="p-3.5 text-[0.8rem] text-muted-foreground">
          Sin propuestas. Pide un escaneo y corre el brain para generarlas.
        </Card>
      )}

      {exp && (
        <Card className="space-y-2 p-3.5">
          {exp.items.map((it, i) => {
            const cbId = `expand-item-${exp.id}-${i}`;
            return (
              <div
                key={cbId}
                className="flex items-start gap-2.5 rounded-md bg-secondary/50 p-2.5 text-[0.8rem]"
              >
                <Checkbox
                  id={cbId}
                  className="mt-0.5"
                  disabled={!!it.applied}
                  checked={it.applied || picked.has(i)}
                  onCheckedChange={() => toggle(i)}
                />
                <label htmlFor={cbId} className="min-w-0 cursor-pointer select-none">
                  <span className="mr-1.5 align-middle">
                    <Badge variant="secondary">{TARGET_ES[it.target]}</Badge>
                  </span>
                  <span className="font-medium">{itemLabel(it)}</span>
                  <div className="mt-0.5 break-words text-muted-foreground">
                    Fuente: {it.source}
                  </div>
                  {it.applied && (
                    <div className="mt-0.5 flex items-center gap-1 text-success">
                      <Check className="size-3.5" /> Aplicado
                    </div>
                  )}
                </label>
              </div>
            );
          })}
          <Button
            size="sm"
            disabled={picked.size === 0 || applyMut.isPending}
            onClick={applyPicked}
          >
            Aplicar seleccionados ({picked.size})
          </Button>
        </Card>
      )}
    </section>
  );
}
