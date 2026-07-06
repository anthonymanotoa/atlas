import { Check, X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type CompanySuggestion, type ResolvedCompany, type SystemHealth } from "../api";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Separator } from "./ui/separator";

/** Salud del sistema + añadir empresa por URL + importar conexiones + sugerir empresas (F3 §6.5). */
export function SettingsOps() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [url, setUrl] = useState("");
  const [resolved, setResolved] = useState<ResolvedCompany | null>(null);
  const [busy, setBusy] = useState(false);
  const [suggestions, setSuggestions] = useState<CompanySuggestion[]>([]);

  function refreshHealth() {
    // Guard the whole call (not just the promise) so it degrades to "Cargando…" rather than
    // crashing the surrounding page if the endpoint is unavailable.
    try {
      api
        .systemHealth()
        .then(setHealth)
        .catch(() => setHealth(null));
    } catch {
      setHealth(null);
    }
  }
  useEffect(refreshHealth, []);

  async function resolveUrl() {
    if (!url.trim()) return;
    setBusy(true);
    try {
      const r = await api.resolveCompany(url.trim());
      setResolved(r);
      if (!r.resolved) toast.error("No detecté un ATS conocido en esa URL");
    } catch {
      toast.error("No se pudo resolver la URL");
    } finally {
      setBusy(false);
    }
  }

  async function addResolved() {
    if (!resolved?.resolved || !resolved.ats) return;
    try {
      const r = await api.addCompany({
        company: resolved.company ?? "",
        ats: resolved.ats,
        token: resolved.token,
      });
      toast.success(r.added ? `Añadida ${resolved.company}` : "Ya estaba en tu lista");
      setResolved(null);
      setUrl("");
    } catch {
      toast.error("No se pudo añadir la empresa");
    }
  }

  async function runSuggest() {
    setBusy(true);
    try {
      const r = await api.suggestCompanies();
      setSuggestions(r.suggestions);
      if (!r.suggestions.length) toast.info("Sin sugerencias nuevas para tus semillas");
    } catch {
      toast.error("No se pudo buscar sugerencias");
    } finally {
      setBusy(false);
    }
  }

  async function addSuggestion(s: CompanySuggestion) {
    try {
      const r = await api.addCompany({ company: s.company, ats: s.ats, token: s.token });
      toast.success(r.added ? `Añadida ${s.company}` : "Ya estaba en tu lista");
      setSuggestions((prev) => prev.filter((x) => x.company !== s.company));
    } catch {
      toast.error("No se pudo añadir");
    }
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const r = await api.importConnections(file);
      toast.success(`Importadas ${r.imported} conexiones`);
    } catch {
      toast.error("No se pudo importar el CSV");
    } finally {
      e.target.value = "";
    }
  }

  return (
    <div>
      <section>
        <div className="mb-1 text-sm font-semibold">Salud del sistema</div>
        <div className="mb-2 text-[0.75rem] text-muted-foreground">
          Fuentes, base de datos y garantías de coste $0 (equivale a{" "}
          <code className="font-mono">atlas status</code> +{" "}
          <code className="font-mono">doctor</code>).
        </div>
        {health ? (
          <div className="space-y-2 text-xs">
            <div className="flex flex-wrap gap-2">
              <Badge variant={health.db.ok ? "success" : "destructive"} className="tabular-nums">
                {`DB ${health.db.ok ? "ok" : "error"} · ${health.db.jobs} jobs`}
              </Badge>
              <Badge variant={health.safeguards.api_key_unset ? "success" : "destructive"}>
                {`API key ${health.safeguards.api_key_unset ? "sin fijar" : "FIJADA"}`}
              </Badge>
              <Badge variant="outline">perfil: {health.profile}</Badge>
              <Badge variant="outline">
                último run: {health.last_run?.slice(0, 19) ?? "nunca"}
              </Badge>
            </div>
            <ul className="space-y-0.5">
              {health.sources.map((s) => (
                <li key={s.source} className="flex items-center gap-2">
                  {s.ok ? (
                    <Check className="size-3 text-success" />
                  ) : (
                    <X className="size-3 text-destructive" />
                  )}
                  <span className="font-mono">{s.source}</span>
                  <span className="text-muted-foreground tabular-nums">
                    {`${s.count} · ${(s.run_at ?? "").slice(0, 19)}${
                      s.error ? ` · ${s.error.slice(0, 40)}` : ""
                    }`}
                  </span>
                </li>
              ))}
            </ul>
            <Button variant="ghost" size="sm" onClick={refreshHealth}>
              Refrescar
            </Button>
          </div>
        ) : (
          <div className="text-xs text-muted-foreground">Cargando…</div>
        )}
      </section>

      <Separator className="my-4" />

      <section>
        <div className="mb-1 text-sm font-semibold">Añadir empresa por URL</div>
        <div className="mb-2 text-[0.75rem] text-muted-foreground">
          Pega la URL de carreras; Atlas detecta el ATS (Greenhouse/Lever/Ashby/…) y la añade a{" "}
          <code className="font-mono">companies.yaml</code>.
        </div>
        <div className="flex gap-2">
          <Input
            className="flex-1 font-mono text-xs"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://boards.greenhouse.io/acme"
          />
          <Button variant="secondary" disabled={busy} onClick={resolveUrl}>
            Detectar
          </Button>
        </div>
        {resolved?.resolved ? (
          <div className="mt-2 flex items-center justify-between rounded-md border border-border p-2 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="font-semibold">{resolved.company}</span>
              <Badge variant="outline">{resolved.ats}</Badge>
              <span className="text-muted-foreground">
                <span className="tabular-nums">{resolved.preview_jobs_count}</span> posiciones
              </span>
            </div>
            <Button size="sm" disabled={resolved.already_configured} onClick={addResolved}>
              {resolved.already_configured ? "Ya está" : "Añadir"}
            </Button>
          </div>
        ) : null}
        <div className="mt-2">
          <Button variant="ghost" size="sm" disabled={busy} onClick={runSuggest}>
            Sugerir empresas de mis semillas
          </Button>
          {suggestions.map((s) => (
            <div
              key={s.company}
              className="mt-1 flex items-center justify-between rounded-md border border-border p-2 text-xs"
            >
              <div className="flex items-center gap-1.5">
                <span className="font-semibold">{s.company}</span>
                <Badge variant="outline">{s.ats}</Badge>
                <span className="text-muted-foreground">
                  {s.matching_titles.slice(0, 2).join(", ")}
                </span>
              </div>
              <Button size="sm" onClick={() => addSuggestion(s)}>
                Añadir
              </Button>
            </div>
          ))}
        </div>
      </section>

      <Separator className="my-4" />

      <section>
        <div className="mb-1 text-sm font-semibold">Importar conexiones de LinkedIn</div>
        <div className="mb-2 text-[0.75rem] text-muted-foreground">
          Sube tu <code className="font-mono">Connections.csv</code> (Ajustes → Privacidad de datos
          → Obtén una copia) para detectar referidos en tus empresas objetivo.
        </div>
        <Input type="file" accept=".csv" onChange={onFile} />
      </section>
    </div>
  );
}
