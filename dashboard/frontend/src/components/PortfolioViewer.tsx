import { ExternalLink, Plus, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Peer, type Portfolio } from "../api";

// P3-F: local portfolio generation + preview (never auto-published) + peer references
// captured during supervised research.
export function PortfolioViewer() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [peers, setPeers] = useState<Peer[]>([]);
  const [github, setGithub] = useState(false);
  const [busy, setBusy] = useState(false);
  const [peerForm, setPeerForm] = useState({ peer_name: "", peer_portfolio_url: "", notes: "" });

  const load = () => {
    api.portfolioLatest().then((r) => setPortfolio(r.portfolio));
    api.peers().then((r) => setPeers(r.peers));
  };
  useEffect(() => {
    load();
  }, []);

  async function generate() {
    setBusy(true);
    try {
      await api.generatePortfolio(github);
      load();
    } finally {
      setBusy(false);
    }
  }
  async function addPeer() {
    if (!peerForm.peer_name) return;
    await api.addPeer(peerForm);
    setPeerForm({ peer_name: "", peer_portfolio_url: "", notes: "" });
    api.peers().then((r) => setPeers(r.peers));
  }

  return (
    <div className="space-y-5">
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold tracking-wide">Mi portafolio (local)</h2>
          <div className="flex items-center gap-2 text-xs">
            <label className="flex cursor-pointer items-center gap-1">
              <input
                type="checkbox"
                checked={github}
                onChange={(e) => setGithub(e.target.checked)}
              />
              Incluir GitHub
            </label>
            <button className="btn !py-1" onClick={generate} disabled={busy}>
              <RefreshCw size={13} /> {busy ? "Generando…" : "Generar"}
            </button>
            {portfolio && (
              <a
                className="btn !py-1"
                href={api.portfolioPreviewUrl(portfolio.id)}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink size={13} /> Abrir
              </a>
            )}
          </div>
        </div>
        {portfolio ? (
          <iframe
            title="portfolio"
            src={api.portfolioPreviewUrl(portfolio.id)}
            className="h-[60vh] w-full rounded-xl border border-[var(--color-border)] bg-white"
          />
        ) : (
          <div className="card p-4 text-sm text-[var(--color-muted)]">
            Aún no generaste un portafolio. Pulsa “Generar” (se crea local, no se publica).
          </div>
        )}
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold tracking-wide">
          Portafolios de referencia (peers)
        </h2>
        <div className="card space-y-2 p-3 text-sm">
          <div className="text-[0.78rem] text-[var(--color-muted)]">
            Investiga peers en tu navegador (supervisado) y guarda los mejores como referencia.
          </div>
          {peers.map((p) => (
            <div key={p.id} className="border-t border-[var(--color-border)] pt-2">
              <b>{p.peer_name}</b>
              {p.peer_portfolio_url && (
                <a
                  className="ml-2 text-xs text-[var(--color-accent)]"
                  target="_blank"
                  rel="noreferrer"
                  href={p.peer_portfolio_url}
                >
                  portafolio ↗
                </a>
              )}
              {p.notes && <div className="text-[0.8rem] text-[var(--color-muted)]">{p.notes}</div>}
            </div>
          ))}
          <div className="flex flex-wrap gap-2 pt-1">
            <input
              className="btn !justify-start flex-1 text-xs"
              placeholder="Nombre del peer"
              value={peerForm.peer_name}
              onChange={(e) => setPeerForm({ ...peerForm, peer_name: e.target.value })}
            />
            <input
              className="btn !justify-start flex-1 text-xs"
              placeholder="URL portafolio"
              value={peerForm.peer_portfolio_url}
              onChange={(e) => setPeerForm({ ...peerForm, peer_portfolio_url: e.target.value })}
            />
            <button className="btn !py-1 text-xs" onClick={addPeer}>
              <Plus size={13} /> Guardar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
