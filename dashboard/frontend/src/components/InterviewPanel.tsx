import { CalendarPlus, FileText, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Interview } from "../api";

const ROUNDS = ["phone", "technical", "system_design", "hiring_manager", "final", "other"];

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
      <div className="mb-2 text-sm font-semibold">Entrevistas</div>
      <div className="card space-y-3 p-3 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="date"
            className="btn !justify-start text-xs"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
          <select
            className="btn !py-1 text-xs"
            value={round}
            onChange={(e) => setRound(e.target.value)}
          >
            {ROUNDS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <button className="btn !py-1 text-xs" onClick={addInterview}>
            <CalendarPlus size={13} /> Agregar
          </button>
        </div>

        {interviews.length === 0 && (
          <div className="text-[0.78rem] text-[var(--color-faint)]">Sin entrevistas agendadas.</div>
        )}

        {interviews.map((iv) => (
          <div key={iv.id} className="border-t border-[var(--color-border)] pt-2">
            <div className="flex items-center justify-between">
              <div>
                <b>{iv.round || "entrevista"}</b>{" "}
                <span className="text-[var(--color-faint)]">{iv.scheduled_at || "sin fecha"}</span>
              </div>
              <button className="btn !py-1 text-xs" onClick={() => genPrep(iv.id)}>
                <FileText size={13} /> Generar prep
              </button>
            </div>
            <InterviewerEditor
              interviewId={iv.id}
              onAdded={refresh}
              interviewers={iv.interviewers}
            />
            {prep[iv.id] && (
              <pre className="mt-2 max-h-60 overflow-auto whitespace-pre-wrap rounded bg-[var(--color-panel2)] p-2 font-sans text-[0.76rem] text-[var(--color-fg)]">
                {prep[iv.id]}
              </pre>
            )}
          </div>
        ))}
      </div>
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
    <div className="mt-1">
      {(interviewers || []).map((p) => (
        <div key={p.id} className="text-[0.8rem]">
          • {p.name}
          {p.title ? ` · ${p.title}` : ""}
          {p.linkedin_url && (
            <a
              className="ml-2 text-xs text-[var(--color-accent)]"
              target="_blank"
              rel="noreferrer"
              href={p.linkedin_url}
            >
              LinkedIn ↗
            </a>
          )}
        </div>
      ))}
      <div className="mt-1 flex gap-2">
        <input
          className="btn !justify-start flex-1 text-xs"
          placeholder="Entrevistador"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="btn !justify-start flex-1 text-xs"
          placeholder="URL LinkedIn"
          value={linkedin}
          onChange={(e) => setLinkedin(e.target.value)}
        />
        <button className="btn !py-1 text-xs" onClick={add}>
          <Plus size={13} />
        </button>
      </div>
    </div>
  );
}
