import { Check, Copy, Send } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api, type JobDetail } from "../../api";
import { copy } from "../../lib";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";

// eslint-disable-next-line react-refresh/only-export-components -- shared with Task 8 consumers
export const KIND_ES: Record<string, string> = {
  cover_letter: "Carta de presentación",
  cold_email: "Email en frío",
  recruiter: "Mensaje a reclutador",
  hiring_manager: "Mensaje a hiring manager",
  referral_ask: "Pedido de referido",
  linkedin_note: "Nota de LinkedIn",
  follow_up: "Follow-up",
  breakup: "Cierre cordial",
};

export function MessageCard({ m }: { m: JobDetail["messages"][number] }) {
  const [done, setDone] = useState(false);
  const [sent, setSent] = useState(m.state === "sent");
  return (
    <Card className="p-3.5">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-medium">{KIND_ES[m.kind] || m.kind}</div>
        <Badge variant="secondary">
          {m.channel} · {m.language}
        </Badge>
      </div>
      {m.subject && (
        <div className="mt-1 text-[0.78rem] text-muted-foreground">Asunto: {m.subject}</div>
      )}
      <pre className="mt-2 max-h-44 overflow-auto rounded-lg bg-background/60 p-2.5 font-sans text-[0.8rem] whitespace-pre-wrap text-foreground">
        {m.body}
      </pre>
      <div className="mt-2.5 flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={async () => {
            await copy((m.subject ? `${m.subject}\n\n` : "") + m.body);
            setDone(true);
            toast.success("Copiado al portapapeles");
            setTimeout(() => setDone(false), 1200);
          }}
        >
          {done ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}{" "}
          {done ? "Copiado" : "Copiar"}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={sent}
          onClick={async () => {
            await api.markSent(m.id);
            setSent(true);
            toast.success("Mensaje marcado como enviado");
          }}
        >
          <Send className="size-3.5" /> {sent ? "Enviado" : "Marcar enviado"}
        </Button>
      </div>
    </Card>
  );
}
