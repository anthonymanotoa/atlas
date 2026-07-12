import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import type { Message, Referral } from "../../api";
import { copy } from "../../lib";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { ReferralIcon } from "../ui/icons";
import { SectionTitle } from "./SectionTitle";

// notes packs "[brain_research] confidence=<low|medium|high>; <reasoning>"
// (engine.intents._write_contact_discovery). Parsed here, never trusted blindly — if the
// shape ever changes upstream this just shows no confidence badge instead of breaking.
const CONFIDENCE = /confidence=(\w+)/;
const CONFIDENCE_VARIANT: Record<string, "success" | "warning" | "secondary"> = {
  high: "success",
  medium: "warning",
  low: "secondary",
};

function confidenceOf(notes?: string): string | null {
  const m = notes ? CONFIDENCE.exec(notes) : null;
  return m ? m[1] : null;
}

function reasoningOf(notes?: string): string | null {
  if (!notes) return null;
  const idx = notes.indexOf("; ");
  return idx === -1 ? null : notes.slice(idx + 2);
}

// Task 15: contactos que el brain descubrió/corroboró para esta empresa (contact_discovery
// intent) — candidatos a revisar, nunca contactados automáticamente. `draftMessage` es el
// borrador "referral_or_intro" que el mismo intent puede haber redactado (Task 15's
// _write_contact_discovery), si lo hubo.
export function SuggestedContacts({
  contacts,
  draftMessage,
}: {
  contacts: Referral[];
  draftMessage?: Message;
}) {
  const [copied, setCopied] = useState(false);
  if (contacts.length === 0) return null;
  return (
    <div>
      <SectionTitle>
        <span className="inline-flex items-center gap-1.5">
          <ReferralIcon className="size-3.5" /> Contactos sugeridos
        </span>
      </SectionTitle>
      <Card className="space-y-3 p-3.5 text-sm">
        <div className="text-[0.78rem] text-muted-foreground">
          Candidatos encontrados por el brain — revísalos antes de contactar, Atlas nunca escribe
          por ti.
        </div>
        {contacts.map((c) => {
          const confidence = confidenceOf(c.notes);
          const reasoning = reasoningOf(c.notes);
          return (
            <div key={c.id} className="rounded-md bg-secondary/50 p-2.5">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <b>{c.name}</b> {c.title && <span>— {c.title}</span>}
                </div>
                {confidence && (
                  <Badge variant={CONFIDENCE_VARIANT[confidence] ?? "secondary"}>
                    confianza {confidence}
                  </Badge>
                )}
              </div>
              {reasoning && <div className="mt-1 text-muted-foreground">{reasoning}</div>}
              {c.linkedin_url && (
                <a
                  href={c.linkedin_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-block text-xs text-primary hover:underline"
                >
                  LinkedIn ↗
                </a>
              )}
            </div>
          );
        })}
        {draftMessage && (
          <Button
            variant="secondary"
            size="sm"
            onClick={async () => {
              await copy(
                (draftMessage.subject ? `${draftMessage.subject}\n\n` : "") + draftMessage.body,
              );
              setCopied(true);
              toast.success("Copiado al portapapeles");
              setTimeout(() => setCopied(false), 1200);
            }}
          >
            {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}{" "}
            {copied ? "Copiado" : "Copiar borrador de mensaje"}
          </Button>
        )}
      </Card>
    </div>
  );
}
