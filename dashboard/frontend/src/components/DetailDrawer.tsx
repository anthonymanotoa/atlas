import * as Dialog from "@radix-ui/react-dialog";
import { Check, Copy, Download, ExternalLink, FileText, Plus, Search, Send, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type JobDetail, type Learning, type SocialMention } from "../api";
import { STATE_ES, copy, fitTone, freshLabel, langLabel, pct, salaryLabel } from "../lib";

const KIND_ES: Record<string, string> = {
  cover_letter: "Carta de presentación",
  cold_email: "Email en frío",
  recruiter: "Mensaje a reclutador",
  hiring_manager: "Mensaje a hiring manager",
  referral_ask: "Pedido de referido",
  linkedin_note: "Nota de LinkedIn",
  follow_up: "Follow-up",
  breakup: "Cierre cordial",
};

function Ledger({ d }: { d: JobDetail }) {
  const cv = d.cv_versions[0];
  const rows = [
    {
      ok: !!cv,
      on: "CV adaptado",
      off: "CV pendiente",
      detail: cv
        ? `cobertura ${pct(cv.keyword_coverage)} · ${cv.parse_ok ? "ATS ✓" : "revisar formato"}`
        : "",
    },
    {
      ok: d.messages.length > 0,
      on: `${d.messages.length} mensajes redactados`,
      off: "Sin borradores",
      detail: "",
    },
    {
      ok: d.job.state === "ready" || d.job.applied_at != null,
      on: "Listo para enviar",
      off: "Aún en preparación",
      detail: "",
    },
  ];
  return (
    <div className="card p-3 space-y-2">
      {rows.map((r, i) => (
        <div key={i} className="flex items-center gap-2 text-sm">
          <span
            className="w-4 h-4 rounded-full flex items-center justify-center text-[10px]"
            style={{
              background: r.ok ? "var(--color-done)" : "var(--color-panel2)",
              color: "#000",
            }}
          >
            {r.ok ? <Check size={11} /> : ""}
          </span>
          <span className={r.ok ? "" : "text-[var(--color-muted)]"}>{r.ok ? r.on : r.off}</span>
          {r.detail && (
            <span className="text-[0.72rem] text-[var(--color-faint)]">· {r.detail}</span>
          )}
        </div>
      ))}
    </div>
  );
}

function MessageCard({ m }: { m: JobDetail["messages"][number] }) {
  const [done, setDone] = useState(false);
  const [sent, setSent] = useState(m.state === "sent");
  return (
    <div className="card p-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">{KIND_ES[m.kind] || m.kind}</div>
        <span className="chip !px-1.5">
          {m.channel} · {m.language}
        </span>
      </div>
      {m.subject && (
        <div className="text-[0.78rem] text-[var(--color-muted)] mt-1">Asunto: {m.subject}</div>
      )}
      <pre className="text-[0.8rem] whitespace-pre-wrap mt-2 text-[var(--color-fg)] font-sans max-h-44 overflow-auto">
        {m.body}
      </pre>
      <div className="flex gap-2 mt-2">
        <button
          className="btn !py-1 !px-2 text-xs"
          onClick={async () => {
            await copy((m.subject ? `${m.subject}\n\n` : "") + m.body);
            setDone(true);
            setTimeout(() => setDone(false), 1200);
          }}
        >
          {done ? <Check size={13} /> : <Copy size={13} />} {done ? "Copiado" : "Copiar"}
        </button>
        <button
          className="btn !py-1 !px-2 text-xs"
          disabled={sent}
          onClick={async () => {
            await api.markSent(m.id);
            setSent(true);
          }}
        >
          <Send size={13} /> {sent ? "Enviado" : "Marcar enviado"}
        </button>
      </div>
    </div>
  );
}

// P2-C: supervised social signal. Atlas queues a search + prepares queries; the human
// runs the LinkedIn/X lookup in their own Chrome and saves what they confirm. No auto-contact.
function SocialSearch({ jobId }: { jobId: string }) {
  const [mentions, setMentions] = useState<SocialMention[]>([]);
  const [queries, setQueries] = useState<Record<string, string> | null>(null);
  const [form, setForm] = useState({ recruiter_name: "", recruiter_linkedin: "", source_url: "" });
  const refresh = () => api.socialMentions(jobId).then((r) => setMentions(r.mentions));
  useEffect(() => {
    refresh();
  }, [jobId]); // eslint-disable-line react-hooks/exhaustive-deps
  const g = (q: string) => `https://www.google.com/search?q=${encodeURIComponent(q)}`;
  async function start() {
    setQueries((await api.startSocialSearch(jobId)).queries);
  }
  async function save() {
    if (!form.recruiter_name && !form.source_url) return;
    await api.addSocialMention(jobId, { platform: "linkedin", ...form });
    setForm({ recruiter_name: "", recruiter_linkedin: "", source_url: "" });
    refresh();
  }
  return (
    <div>
      <div className="mb-2 text-sm font-semibold">Señal social (LinkedIn / X)</div>
      <div className="card space-y-2 p-3 text-sm">
        <div className="text-[0.78rem] text-[var(--color-muted)]">
          Búsqueda supervisada en tu navegador — Atlas no contacta a nadie por ti.
        </div>
        <button className="btn !py-1 text-xs" onClick={start}>
          <Search size={13} /> Buscar reclutador
        </button>
        {queries && (
          <div className="flex flex-col gap-1 text-xs">
            <a
              className="text-[var(--color-accent)]"
              target="_blank"
              rel="noreferrer"
              href={g(queries.linkedin_recruiters)}
            >
              · LinkedIn — reclutadores ↗
            </a>
            <a
              className="text-[var(--color-accent)]"
              target="_blank"
              rel="noreferrer"
              href={g(queries.linkedin_posts)}
            >
              · LinkedIn — posts de la vacante ↗
            </a>
            <a
              className="text-[var(--color-accent)]"
              target="_blank"
              rel="noreferrer"
              href={g(queries.x)}
            >
              · X / Twitter ↗
            </a>
          </div>
        )}
        {mentions.map((m) => (
          <div key={m.id} className="border-t border-[var(--color-border)] pt-2">
            <b>{m.recruiter_name || m.post_title || "Mención"}</b>{" "}
            {m.platform && <span className="chip !px-1.5">{m.platform}</span>}
            {m.recruiter_linkedin && (
              <a
                className="ml-2 text-xs text-[var(--color-accent)]"
                target="_blank"
                rel="noreferrer"
                href={m.recruiter_linkedin}
              >
                LinkedIn ↗
              </a>
            )}
            {m.source_url && (
              <a
                className="ml-2 text-xs text-[var(--color-accent)]"
                target="_blank"
                rel="noreferrer"
                href={m.source_url}
              >
                fuente ↗
              </a>
            )}
          </div>
        ))}
        <div className="flex flex-col gap-1 pt-1">
          <input
            className="btn !justify-start text-xs"
            placeholder="Nombre del reclutador"
            value={form.recruiter_name}
            onChange={(e) => setForm({ ...form, recruiter_name: e.target.value })}
          />
          <input
            className="btn !justify-start text-xs"
            placeholder="URL de LinkedIn del reclutador"
            value={form.recruiter_linkedin}
            onChange={(e) => setForm({ ...form, recruiter_linkedin: e.target.value })}
          />
          <div className="flex gap-2">
            <input
              className="btn !justify-start flex-1 text-xs"
              placeholder="URL fuente (post)"
              value={form.source_url}
              onChange={(e) => setForm({ ...form, source_url: e.target.value })}
            />
            <button className="btn !py-1 text-xs" onClick={save}>
              <Plus size={13} /> Guardar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// P2-D: record a HUMAN-confirmed outcome → feeds the per-company learning loop.
function RecordOutcome({ jobId, onSaved }: { jobId: string; onSaved: () => void }) {
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
    setTimeout(() => setSaved(false), 1500);
    onSaved();
  }
  return (
    <div>
      <div className="mb-2 text-sm font-semibold">Registrar resultado</div>
      <div className="card space-y-2 p-3 text-sm">
        <div className="flex flex-wrap gap-2">
          <select
            className="btn !py-1 text-xs"
            value={state}
            onChange={(e) => setState(e.target.value)}
          >
            <option value="rejected">Rechazado</option>
            <option value="responded">Respondieron</option>
            <option value="interviewed">Entrevista</option>
            <option value="offer">Oferta</option>
            <option value="ghosted">Sin respuesta</option>
          </select>
          <select
            className="btn !py-1 text-xs"
            value={recruiterSource}
            onChange={(e) => setRecruiterSource(e.target.value)}
          >
            <option value="">Origen…</option>
            <option value="referral">Referido</option>
            <option value="recruiter">Reclutador</option>
            <option value="cold">En frío</option>
            <option value="inbound">Inbound</option>
          </select>
          <input
            className="btn !justify-start w-24 text-xs"
            placeholder="Días resp."
            value={responseDays}
            onChange={(e) => setResponseDays(e.target.value.replace(/\D/g, ""))}
          />
          <button className="btn !py-1 text-xs" onClick={save}>
            {saved ? "Guardado ✓" : "Guardar"}
          </button>
        </div>
        <div className="text-[0.72rem] text-[var(--color-faint)]">
          Alimenta la memoria de Atlas (qué empresas convierten y cómo). Tú confirmas; el brain
          nunca lo inventa.
        </div>
      </div>
    </div>
  );
}

function CompanyInsights({ learnings }: { learnings?: Learning[] }) {
  if (!learnings || learnings.length === 0) return null;
  return (
    <div>
      <div className="mb-2 text-sm font-semibold">🧠 Lo aprendido de esta empresa</div>
      <div className="card space-y-1 p-3 text-sm">
        {learnings.map((l) => (
          <div key={l.id}>
            {l.observation}{" "}
            <span className="text-[0.72rem] text-[var(--color-faint)]">
              · confianza {Math.round(l.confidence * 100)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function DetailDrawer({
  jobId,
  onClose,
  onChanged,
}: {
  jobId: string | null;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [d, setD] = useState<JobDetail | null>(null);
  useEffect(() => {
    if (jobId) {
      setD(null);
      api.job(jobId).then(setD);
    }
  }, [jobId]);

  async function prep() {
    if (!jobId) return;
    await api.prep(jobId); // language auto-picked from the posting (es offer → ES, else EN)
    api.job(jobId).then(setD);
    onChanged();
  }
  async function markApplied() {
    if (!jobId) return;
    await api.markApplied(jobId);
    api.job(jobId).then(setD);
    onChanged();
  }

  return (
    <Dialog.Root open={!!jobId} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 backdrop-blur-[2px] z-40" />
        <Dialog.Content
          className="fixed right-0 top-0 h-full w-full max-w-[540px] z-50 bg-[var(--color-bg)] border-l border-[var(--color-border)] overflow-y-auto"
          style={{ animation: "fadeUp 0.2s ease" }}
        >
          {!d ? (
            <div className="p-6 text-[var(--color-muted)]">Cargando…</div>
          ) : (
            <div className="p-5 space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <Dialog.Title className="text-lg font-semibold leading-snug">
                    {d.job.title}
                  </Dialog.Title>
                  <div className="text-[var(--color-muted)]">{d.job.company}</div>
                </div>
                <Dialog.Close className="btn !p-2">
                  <X size={16} />
                </Dialog.Close>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                <span className="chip font-semibold" style={{ color: fitTone(d.job.fit_score) }}>
                  fit {d.job.fit_score ?? "—"}
                </span>
                <span className="chip">{STATE_ES[d.job.state] || d.job.state}</span>
                {d.job.is_remote === 1 && <span className="chip">Remoto</span>}
                {salaryLabel(d.job) && (
                  <span className="chip" title="Salario publicado">
                    💰 {salaryLabel(d.job)}
                  </span>
                )}
                {d.job.language && (
                  <span className="chip uppercase">{langLabel(d.job.language)}</span>
                )}
                {(d.job.posted_days ?? d.job.age_days) != null && (
                  <span className="chip">{freshLabel(d.job.posted_days ?? d.job.age_days)}</span>
                )}
                {(d.job.apply_url || d.job.url) && (
                  <a
                    href={d.job.apply_url || d.job.url}
                    target="_blank"
                    rel="noreferrer"
                    className="btn !py-1 !px-2 text-xs"
                  >
                    <ExternalLink size={13} /> Postular
                  </a>
                )}
              </div>

              {d.job.knockout_flags && d.job.knockout_flags.length > 0 && (
                <div className="card p-3 text-sm" style={{ borderColor: "var(--color-pending)" }}>
                  ⚑ <b>Filtros del puesto:</b> {d.job.knockout_flags.join(", ")}
                </div>
              )}

              <Ledger d={d} />

              {d.referrals.length > 0 && (
                <div className="card p-3" style={{ borderColor: "var(--color-accent2)" }}>
                  <div className="text-sm font-medium" style={{ color: "var(--color-accent2)" }}>
                    🤝 Referido disponible (prioriza esto)
                  </div>
                  {d.referrals.map((r) => (
                    <div key={r.id} className="text-sm mt-1">
                      <b>{r.name}</b> — {r.title || ""} @ {r.company}
                      {r.linkedin_url && (
                        <a
                          href={r.linkedin_url}
                          target="_blank"
                          rel="noreferrer"
                          className="ml-2 text-[var(--color-accent)] text-xs"
                        >
                          LinkedIn ↗
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {d.cv_versions[0] && (
                <div className="flex gap-2">
                  {d.cv_versions[0].path_pdf && (
                    <a
                      href={api.cvDownload(d.job.id, d.cv_versions[0].id, "pdf")}
                      className="btn btn-accent flex-1 justify-center"
                    >
                      <FileText size={15} /> CV PDF <Download size={14} />
                    </a>
                  )}
                  <a
                    href={api.cvDownload(d.job.id, d.cv_versions[0].id, "docx")}
                    className="btn flex-1 justify-center"
                  >
                    <FileText size={15} /> CV DOCX <Download size={14} />
                  </a>
                </div>
              )}

              <div>
                <div className="text-sm font-semibold mb-2">Mensajes — qué enviar</div>
                <div className="space-y-2">
                  {d.messages.length === 0 && (
                    <button className="btn w-full justify-center" onClick={prep}>
                      Generar borradores
                    </button>
                  )}
                  {d.messages.map((m) => (
                    <MessageCard key={m.id} m={m} />
                  ))}
                </div>
              </div>

              <CompanyInsights learnings={d.learnings} />

              <SocialSearch jobId={d.job.id} />

              <RecordOutcome
                jobId={d.job.id}
                onSaved={() => {
                  api.job(d.job.id).then(setD);
                  onChanged();
                }}
              />

              <div className="flex gap-2 pt-2">
                <button className="btn flex-1 justify-center" onClick={markApplied}>
                  Marcar como aplicado
                </button>
                <button className="btn flex-1 justify-center" onClick={prep}>
                  Re-preparar
                </button>
              </div>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
