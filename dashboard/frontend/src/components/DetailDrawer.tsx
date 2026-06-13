import * as Dialog from "@radix-ui/react-dialog";
import { Check, Copy, Download, ExternalLink, FileText, Send, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type JobDetail } from "../api";
import { STATE_ES, copy, fitTone, pct } from "../lib";

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
    await api.prep(jobId, "en");
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
