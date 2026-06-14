import { ExternalLink, Plus, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Peer, type Portfolio } from "../api";
import { Button, buttonVariants } from "./ui/button";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Separator } from "./ui/separator";
import { Switch } from "./ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";

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
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 className="text-caption text-muted-foreground uppercase">Mi portafolio (local)</h2>
          <div className="flex items-center gap-3 text-xs">
            <Label className="cursor-pointer font-normal text-muted-foreground">
              <Switch checked={github} onCheckedChange={(c) => setGithub(c === true)} />
              Incluir GitHub
            </Label>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="secondary" size="sm" onClick={generate} disabled={busy}>
                  <RefreshCw className="size-3.5" /> {busy ? "Generando…" : "Generar"}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                Renderiza tu CV maestro en un sitio de portafolio HTML local. Nunca se publica;
                queda solo en tu Mac. Determinista.
              </TooltipContent>
            </Tooltip>
            {portfolio && (
              <a
                className={buttonVariants({ variant: "secondary", size: "sm" })}
                href={api.portfolioPreviewUrl(portfolio.id)}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink className="size-3.5" /> Abrir
              </a>
            )}
          </div>
        </div>
        {portfolio ? (
          <iframe
            title="portfolio"
            src={api.portfolioPreviewUrl(portfolio.id)}
            className="h-[60vh] w-full rounded-xl border border-border bg-white"
          />
        ) : (
          <Card className="p-4 text-sm text-muted-foreground">
            Aún no generaste un portafolio. Pulsa “Generar” (se crea local, no se publica).
          </Card>
        )}
      </div>

      <div>
        <h2 className="mb-2 text-caption text-muted-foreground uppercase">
          Portafolios de referencia (peers)
        </h2>
        <Card className="space-y-2.5 p-3.5 text-sm">
          <div className="text-[0.78rem] text-muted-foreground">
            Investiga peers en tu navegador (supervisado) y guarda los mejores como referencia.
          </div>
          {peers.map((p) => (
            <div key={p.id}>
              <Separator className="mb-2" />
              <b>{p.peer_name}</b>
              {p.peer_portfolio_url && (
                <a
                  className="ml-2 text-xs text-primary hover:underline"
                  target="_blank"
                  rel="noreferrer"
                  href={p.peer_portfolio_url}
                >
                  portafolio ↗
                </a>
              )}
              {p.notes && <div className="text-[0.8rem] text-muted-foreground">{p.notes}</div>}
            </div>
          ))}
          <div className="flex flex-wrap gap-2 pt-1">
            <Input
              className="h-8 flex-1 text-xs"
              placeholder="Nombre del peer"
              value={peerForm.peer_name}
              onChange={(e) => setPeerForm({ ...peerForm, peer_name: e.target.value })}
            />
            <Input
              className="h-8 flex-1 text-xs"
              placeholder="URL portafolio"
              value={peerForm.peer_portfolio_url}
              onChange={(e) => setPeerForm({ ...peerForm, peer_portfolio_url: e.target.value })}
            />
            <Button variant="secondary" size="sm" onClick={addPeer}>
              <Plus className="size-3.5" /> Guardar
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
