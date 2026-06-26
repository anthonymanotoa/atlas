import { CalendarPlus, FileText, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Interview } from "../api";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { ScrollArea } from "./ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Separator } from "./ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";

// Round values stay stable (the backend/prep keys on them), but each gets a human label so the
// selector doesn't expose raw enum keys. `system_design` is a software-specific stage; it's
// offered alongside the generic rounds rather than presented as universal — `other` covers the rest.
const ROUNDS: { value: string; label: string }[] = [
  { value: "phone", label: "Telefónica / screening" },
  { value: "technical", label: "Técnica / específica del rol" },
  { value: "system_design", label: "Diseño de sistemas (software)" },
  { value: "hiring_manager", label: "Hiring manager" },
  { value: "final", label: "Final" },
  { value: "other", label: "Otra" },
];
const ROUND_LABEL: Record<string, string> = Object.fromEntries(
  ROUNDS.map((r) => [r.value, r.label]),
);

// P3-E: manual interview entry + per-interviewer capture + deterministic prep doc.
// Interviewer research is supervised (open the LinkedIn URL yourself); we just store it.
export function InterviewPanel({ jobId }: { jobId: string }) {
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [date, setDate] = useState("");
  const [round, setRound] = useState("phone");
  const [prep, setPrep] = useState<Record<number, string>>({});
  const refresh = () => api.interviews(jobId).then((r) => setInterviews(r.interviews));
  useEffect(() => {
    refresh();
  }, [jobId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function addInterview() {
    await api.addInterview(jobId, { scheduled_at: date || undefined, round });
    setDate("");
    refresh();
  }
  async function genPrep(id: number) {
    const r = await api.genPrep(id);
    setPrep((p) => ({ ...p, [id]: r.markdown }));
    refresh();
  }

  return (
    <div>
      <div className="mb-2 text-caption text-muted-foreground uppercase">Entrevistas</div>
      <Card className="space-y-3 p-3.5 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <Input
            type="date"
            className="h-8 w-auto text-xs"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
          <Select value={round} onValueChange={setRound}>
            <SelectTrigger size="sm" className="w-auto">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ROUNDS.map((r) => (
                <SelectItem key={r.value} value={r.value}>
                  {r.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="secondary" size="sm" onClick={addInterview}>
            <CalendarPlus className="size-3.5" /> Agregar
          </Button>
        </div>

        {interviews.length === 0 && (
          <div className="text-[0.78rem] text-muted-foreground">Sin entrevistas agendadas.</div>
        )}

        {interviews.map((iv) => (
          <div key={iv.id}>
            <Separator className="mb-2" />
            <div className="flex items-center justify-between">
              <div>
                <b>{(iv.round && ROUND_LABEL[iv.round]) || iv.round || "entrevista"}</b>{" "}
                <span className="text-muted-foreground">{iv.scheduled_at || "sin fecha"}</span>
              </div>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="secondary" size="sm" onClick={() => genPrep(iv.id)}>
                    <FileText className="size-3.5" /> Generar prep
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  Genera el doc de preparación: preguntas probables (conductuales + específicas del
                  rol), temas a repasar (gaps del JD) y tu evidencia STAR real. Sale de tu CV + la
                  oferta.
                </TooltipContent>
              </Tooltip>
            </div>
            <InterviewerEditor
              interviewId={iv.id}
              onAdded={refresh}
              interviewers={iv.interviewers}
            />
            {prep[iv.id] && (
              <ScrollArea className="mt-2 max-h-60 rounded-lg bg-background/60">
                <pre className="p-2.5 font-mono text-[0.76rem] whitespace-pre-wrap text-foreground">
                  {prep[iv.id]}
                </pre>
              </ScrollArea>
            )}
          </div>
        ))}
      </Card>
    </div>
  );
}

function InterviewerEditor({
  interviewId,
  interviewers,
  onAdded,
}: {
  interviewId: number;
  interviewers?: Interview["interviewers"];
  onAdded: () => void;
}) {
  const [name, setName] = useState("");
  const [linkedin, setLinkedin] = useState("");
  async function add() {
    if (!name) return;
    await api.addInterviewer(interviewId, { name, linkedin_url: linkedin || undefined });
    setName("");
    setLinkedin("");
    onAdded();
  }
  return (
    <div className="mt-1.5">
      {(interviewers || []).map((p) => (
        <div key={p.id} className="text-[0.8rem]">
          • {p.name}
          {p.title ? ` · ${p.title}` : ""}
          {p.linkedin_url && (
            <a
              className="ml-2 text-xs text-primary hover:underline"
              target="_blank"
              rel="noreferrer"
              href={p.linkedin_url}
            >
              LinkedIn ↗
            </a>
          )}
        </div>
      ))}
      <div className="mt-1.5 flex gap-2">
        <Input
          className="h-8 flex-1 text-xs"
          placeholder="Entrevistador"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Input
          className="h-8 flex-1 text-xs"
          placeholder="URL LinkedIn"
          value={linkedin}
          onChange={(e) => setLinkedin(e.target.value)}
        />
        <Button variant="secondary" size="icon-sm" onClick={add}>
          <Plus className="size-3.5" />
        </Button>
      </div>
    </div>
  );
}
