import { AlarmClock, Check, Copy, Send, Snowflake } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import type { ColdJob, Followup } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/states";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { useFollowups, useMarkFollowupSent } from "../hooks/useFollowups";
import { copy } from "../lib";

// F3 §6.1 — vista de follow-ups. Buckets deterministas que el engine sembró: cada toque trae su
// borrador pegable (Copiar) y un envío confirmado en dos pasos (Marcar enviado → Confirmar). El
// bucket COLD son jobs con la cadencia agotada (sin nada que enviar). $0, sin LLM.
const BUCKET_META: {
  key: "urgent" | "overdue" | "waiting";
  label: string;
  tone: "destructive" | "warning" | "info";
}[] = [
  { key: "urgent", label: "Urgentes", tone: "destructive" },
  { key: "overdue", label: "Vencidos", tone: "warning" },
  { key: "waiting", label: "En espera", tone: "info" },
];

function overdueLabel(f: Followup): string {
  const d = f.days_overdue;
  if (d == null) return "";
  if (d <= 0) return "aún no vence";
  return `vencido hace ${d.toFixed(1)}d`;
}

function FollowupCard({ f }: { f: Followup }) {
  const [copied, setCopied] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const markSent = useMarkFollowupSent();
  const draftText = (f.draft.subject ? `${f.draft.subject}\n\n` : "") + f.draft.body;

  async function onCopy() {
    await copy(draftText);
    setCopied(true);
    toast.success("Borrador copiado al portapapeles");
    setTimeout(() => setCopied(false), 1200);
  }

  function onMarkSent() {
    // Confirmación explícita en dos pasos (§6.1): el primer clic arma, el segundo envía.
    if (!confirming) {
      setConfirming(true);
      return;
    }
    markSent.mutate(f.id, {
      onSuccess: () => toast.success("Follow-up marcado como enviado"),
      onError: () => toast.error("No se pudo marcar como enviado"),
      onSettled: () => setConfirming(false),
    });
  }

  return (
    <Card className="p-3.5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">{f.title || "—"}</div>
          <div className="truncate text-[0.78rem] text-muted-foreground">{f.company || "—"}</div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <Badge variant="outline" className="tabular-nums">
            toque {f.touch_number ?? 1}
          </Badge>
          <span className="text-[0.7rem] text-muted-foreground tabular-nums">
            {overdueLabel(f)}
          </span>
        </div>
      </div>
      {f.draft.subject && (
        <div className="mt-2 text-[0.78rem] text-muted-foreground">Asunto: {f.draft.subject}</div>
      )}
      <pre className="mt-2 max-h-44 overflow-auto rounded-lg bg-background/60 p-2.5 font-sans text-[0.8rem] whitespace-pre-wrap text-foreground">
        {f.draft.body}
      </pre>
      <div className="mt-2.5 flex flex-wrap gap-2">
        <Button variant="secondary" size="sm" onClick={onCopy}>
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}{" "}
          {copied ? "Copiado" : "Copiar"}
        </Button>
        <Button
          variant={confirming ? "default" : "secondary"}
          size="sm"
          disabled={markSent.isPending}
          onClick={onMarkSent}
        >
          <Send className="size-3.5" /> {confirming ? "Confirmar envío" : "Marcar enviado"}
        </Button>
        {confirming && (
          <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>
            Cancelar
          </Button>
        )}
      </div>
    </Card>
  );
}

function ColdCard({ j }: { j: ColdJob }) {
  return (
    <Card className="flex items-center justify-between gap-2 p-3">
      <div className="min-w-0">
        <div className="truncate text-sm font-medium">{j.title || "—"}</div>
        <div className="truncate text-[0.78rem] text-muted-foreground">{j.company || "—"}</div>
      </div>
      <Badge variant="secondary" className="shrink-0 tabular-nums">
        {j.touches_done ?? 0} toques · sin respuesta
      </Badge>
    </Card>
  );
}

export function FollowupsPage() {
  const followupsQ = useFollowups();

  if (followupsQ.isPending) return <LoadingState rows={3} />;
  if (followupsQ.isError) return <ErrorState onRetry={() => followupsQ.refetch()} />;
  if (!followupsQ.data) return null;

  const b = followupsQ.data.buckets;
  const activeCount = b.urgent.length + b.overdue.length + b.waiting.length;
  const coldCount = b.cold.length;

  return (
    <>
      <h1 className="mb-1 text-h1">Follow-ups</h1>
      <p className="mb-4 max-w-[64ch] text-sm text-muted-foreground">
        Toques de seguimiento que la cadencia sembró — con su borrador pegable. Copia, envíalo por
        tu cuenta y márcalo enviado (con confirmación). Todo es determinista y $0.
      </p>

      {activeCount === 0 && coldCount === 0 ? (
        <EmptyState
          icon={AlarmClock}
          title="Sin follow-ups pendientes"
          description="Cuando apliques a una vacante, Atlas sembrará los toques de seguimiento aquí."
        />
      ) : (
        <div className="flex flex-col gap-6">
          {BUCKET_META.map(({ key, label, tone }) => {
            const rows = b[key];
            if (rows.length === 0) return null;
            return (
              <section key={key}>
                <div className="mb-2 flex items-center gap-2">
                  <h2 className="text-h3">{label}</h2>
                  <Badge variant={tone} className="tabular-nums">
                    {rows.length}
                  </Badge>
                </div>
                <div className="grid gap-3 lg:grid-cols-2">
                  {rows.map((f) => (
                    <FollowupCard key={f.id} f={f} />
                  ))}
                </div>
              </section>
            );
          })}

          {coldCount > 0 && (
            <section>
              <div className="mb-2 flex items-center gap-2">
                <Snowflake className="size-4 text-muted-foreground" />
                <h2 className="text-h3">Frías</h2>
                <Badge variant="secondary" className="tabular-nums">
                  {coldCount}
                </Badge>
              </div>
              <p className="mb-2 text-[0.78rem] text-muted-foreground">
                Cadencia agotada sin respuesta — nada más que enviar.
              </p>
              <div className="grid gap-2 lg:grid-cols-2">
                {b.cold.map((j) => (
                  <ColdCard key={j.job_id} j={j} />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </>
  );
}
