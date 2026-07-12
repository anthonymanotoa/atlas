import {
  Check,
  Clock,
  Copy,
  ExternalLink,
  Lightbulb,
  Plus,
  RefreshCw,
  Sparkles,
  Wand2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Peer, type Portfolio, type PortfolioResearch } from "../api";
import { copy } from "../lib";
import { IntentConfirmDialog } from "./IntentConfirmDialog";
import { Button, buttonVariants } from "./ui/button";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Separator } from "./ui/separator";
import { Switch } from "./ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";

const PATTERN_TITLES: Record<string, string> = {
  secciones: "Secciones (en orden)",
  como_mostrar_proyectos: "Cómo mostrar los proyectos",
  diseno: "Diseño",
  errores_a_evitar: "Errores a evitar",
};

// P3-F: local portfolio generation + the curated peer research + a personalized LLM prompt the
// user can paste into Claude/ChatGPT/Lovable to have their portfolio built. Atlas never builds
// the site for them — it gives them the examples + the brief.
export function PortfolioViewer() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [peers, setPeers] = useState<Peer[]>([]);
  const [research, setResearch] = useState<PortfolioResearch | null>(null);
  const [github, setGithub] = useState(false);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [peerForm, setPeerForm] = useState({ peer_name: "", peer_portfolio_url: "", notes: "" });

  const load = () => {
    api.portfolioLatest().then((r) => setPortfolio(r.portfolio));
    api.peers().then((r) => setPeers(r.peers));
    api.portfolioResearch().then(setResearch);
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
  async function copyPrompt() {
    if (!research) return;
    await copy(research.prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="space-y-7">
      {/* 1 — The brief: a ready-to-paste prompt to have an LLM build the portfolio */}
      <section>
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 className="flex items-center gap-1.5 text-caption text-muted-foreground uppercase">
            <Wand2 className="size-3.5" /> Tu portafolio en 1 paso — prompt para un LLM
          </h2>
          {research && (
            <Button size="sm" onClick={copyPrompt}>
              {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              {copied ? "Copiado" : "Copiar prompt"}
            </Button>
          )}
        </div>
        <Card className="p-4">
          <p className="mb-3 text-sm text-muted-foreground">
            No tienes que construirlo a mano. Copia este prompt —ya está personalizado con tu CV
            real— y pégalo en Claude, ChatGPT o Lovable. Te hará unas preguntas y te generará el
            sitio completo, listo para desplegar.
          </p>
          {research ? (
            <div className="max-h-72 overflow-auto rounded-lg border border-border bg-background/60">
              <pre className="p-3 font-mono text-[0.72rem] leading-relaxed whitespace-pre-wrap text-foreground/90">
                {research.prompt}
              </pre>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">Cargando…</div>
          )}
        </Card>
      </section>

      {/* 2 — Reference portfolios (researched + vetted), all in one place */}
      <section>
        <h2 className="mb-1 flex items-center gap-1.5 text-caption text-muted-foreground uppercase">
          <Sparkles className="size-3.5" /> Portafolios de referencia que revisé
        </h2>
        <p className="mb-3 text-sm text-muted-foreground">
          Investigué y filtré portafolios de gente con un perfil como el tuyo. Descarté los flojos o
          con links rotos. Estos son los buenos — ábrelos y fíjate en qué robar de cada uno.
        </p>
        {research && research.examples.length === 0 && (
          <Card className="p-4 text-sm text-muted-foreground">
            Todavía no hay portafolios de referencia curados para tu dominio. Mientras tanto, usa el
            prompt de arriba (ya personalizado con tu CV) y guarda abajo tus propias referencias.
          </Card>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          {(research?.examples || []).map((ex) => (
            <Card key={ex.url} className="flex flex-col gap-2 p-3.5">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-semibold">{ex.peer_name}</div>
                  <div className="mt-0.5 text-[0.78rem] text-muted-foreground">{ex.role_match}</div>
                </div>
                <a
                  className={buttonVariants({ variant: "secondary", size: "sm" })}
                  href={ex.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  <ExternalLink className="size-3.5" /> Abrir
                </a>
              </div>
              <div>
                <div className="mb-1 text-[0.68rem] tracking-wide text-muted-foreground uppercase">
                  Qué hace bien
                </div>
                <ul className="list-disc space-y-0.5 pl-4 text-[0.8rem] text-foreground/90">
                  {ex.key_strengths.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="mb-1 text-[0.68rem] tracking-wide text-muted-foreground uppercase">
                  Qué robar
                </div>
                <ul className="list-disc space-y-0.5 pl-4 text-[0.8rem] text-foreground/90">
                  {ex.what_to_steal.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* 3 — The cross-cutting playbook */}
      {research && Object.keys(research.patterns).length > 0 && (
        <section>
          <h2 className="mb-3 flex items-center gap-1.5 text-caption text-muted-foreground uppercase">
            <Lightbulb className="size-3.5" /> Qué hacen los mejores (el patrón)
          </h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {Object.entries(research.patterns).map(([key, items]) => (
              <Card key={key} className="p-3.5">
                <div className="mb-1.5 text-sm font-semibold">{PATTERN_TITLES[key] || key}</div>
                <ul className="list-disc space-y-1 pl-4 text-[0.8rem] text-foreground/90">
                  {items.map((it, i) => (
                    <li key={i}>{it}</li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* 4 — Optional: generate a quick local HTML portfolio from the CV */}
      <section>
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 className="text-caption text-muted-foreground uppercase">
            Borrador rápido desde tu CV (local)
          </h2>
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
                Renderiza tu CV maestro en un sitio HTML local (un borrador de arranque). Nunca se
                publica; queda solo en tu Mac. Para algo pulido, usa el prompt de arriba.
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
            className="h-[55vh] w-full rounded-xl border border-border bg-white"
          />
        ) : (
          <Card className="p-4 text-sm text-muted-foreground">
            Un borrador instantáneo a partir de tu CV. Pulsa “Generar” (local, no se publica).
          </Card>
        )}
      </section>

      {/* 5 — Save your own references + the living peer set the brain keeps fresh */}
      <section>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-caption text-muted-foreground uppercase">
            Mis referencias guardadas (+ research vivo del brain)
          </h2>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1 text-[0.72rem] text-muted-foreground">
              <Clock className="size-3" />
              {research?.last_reviewed_at
                ? `Última actualización: ${new Date(research.last_reviewed_at).toLocaleDateString("es")}`
                : "Sin research vivo todavía"}
            </span>
            <IntentConfirmDialog
              buttonLabel="Refrescar (encolar al brain)"
              title="Research de portafolios de referencia"
              what="El brain busca portafolios de referencia ACTUALES para tu dominio y rol objetivo — el set curado de arriba es una foto fija que envejece; esto la mantiene viva."
              produces="Peers nuevos (o actualizaciones de los ya vistos) en la lista de abajo, con fecha de research."
              where="En esta misma vista, tras correr el brain."
              type="portfolio_research"
            />
          </div>
        </div>
        <Card className="space-y-2.5 p-3.5 text-sm">
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
              {p.reviewed_at && (
                <span className="ml-2 text-[0.7rem] text-muted-foreground">
                  revisado {new Date(p.reviewed_at).toLocaleDateString("es")}
                </span>
              )}
              {p.notes && <div className="text-[0.8rem] text-muted-foreground">{p.notes}</div>}
            </div>
          ))}
          <div className="flex flex-wrap gap-2 pt-1">
            <Input
              className="h-8 flex-1 text-xs"
              placeholder="Nombre"
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
      </section>
    </div>
  );
}
