import { useState } from "react";
import { toast } from "sonner";
import { api } from "../../api";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { SectionTitle } from "./SectionTitle";

// P2-D: record a HUMAN-confirmed outcome → feeds the per-company learning loop.
export function RecordOutcome({ jobId, onSaved }: { jobId: string; onSaved: () => void }) {
  const [state, setState] = useState("rejected");
  const [recruiterSource, setRecruiterSource] = useState("");
  const [responseDays, setResponseDays] = useState("");
  const [saved, setSaved] = useState(false);
  async function save() {
    await api.recordOutcome(jobId, {
      final_state: state,
      recruiter_source: recruiterSource || null,
      response_days: responseDays ? Number(responseDays) : null,
      offer_made: state === "offer",
    });
    setSaved(true);
    toast.success("Resultado registrado");
    setTimeout(() => setSaved(false), 1500);
    onSaved();
  }
  return (
    <div>
      <SectionTitle>Registrar resultado</SectionTitle>
      <Card className="space-y-2.5 p-3.5 text-sm">
        <div className="flex flex-wrap gap-2">
          <Select value={state} onValueChange={setState}>
            <SelectTrigger size="sm" className="w-auto">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="rejected">Rechazado</SelectItem>
              <SelectItem value="responded">Respondieron</SelectItem>
              <SelectItem value="interviewed">Entrevista</SelectItem>
              <SelectItem value="offer">Oferta</SelectItem>
              <SelectItem value="ghosted">Sin respuesta</SelectItem>
            </SelectContent>
          </Select>
          <Select value={recruiterSource || undefined} onValueChange={(v) => setRecruiterSource(v)}>
            <SelectTrigger size="sm" className="w-auto">
              <SelectValue placeholder="Origen…" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="referral">Referido</SelectItem>
              <SelectItem value="recruiter">Reclutador</SelectItem>
              <SelectItem value="cold">En frío</SelectItem>
              <SelectItem value="inbound">Inbound</SelectItem>
            </SelectContent>
          </Select>
          <Input
            className="h-8 w-24 text-xs"
            placeholder="Días resp."
            value={responseDays}
            onChange={(e) => setResponseDays(e.target.value.replace(/\D/g, ""))}
          />
          <Button variant="secondary" size="sm" onClick={save}>
            {saved ? "Guardado ✓" : "Guardar"}
          </Button>
        </div>
        <div className="text-[0.72rem] text-muted-foreground">
          Alimenta la memoria de Atlas (qué empresas convierten y cómo). Tú confirmas; el brain
          nunca lo inventa.
        </div>
      </Card>
    </div>
  );
}
