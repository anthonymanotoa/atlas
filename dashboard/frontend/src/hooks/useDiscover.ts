import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type Overview } from "../api";

const SEARCH_SOURCES_FALLBACK = "las fuentes activas de tu perfil";

export function searchSourcesLabel(ov?: Overview | null): string {
  const names = (ov?.source_health || []).map((s) => s.source).filter(Boolean);
  return names.length > 0 ? names.join(" · ") : SEARCH_SOURCES_FALLBACK;
}

// Dispara discover→score determinista, pollea /api/discover/status (~2 min máx)
// y refresca todas las queries al terminar. Un solo dueño: AppShell.
export function useDiscover(ov?: Overview | null) {
  const qc = useQueryClient();
  const [searching, setSearching] = useState(false);
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!searching) return;
    setSeconds(0);
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [searching]);

  const run = useCallback(async () => {
    if (searching) return;
    setSearching(true);
    const tid = toast.loading("Buscando vacantes nuevas…", {
      description: `Consultando fuentes y puntuando contra tu CV. ${searchSourcesLabel(ov)}`,
    });
    try {
      await api.discover();
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const { running } = await api.discoverStatus();
        if (!running) break;
      }
      await qc.invalidateQueries();
      toast.success("Búsqueda completa", {
        id: tid,
        description: "Tablero actualizado. Revisá la columna “Preseleccionados”.",
      });
    } catch {
      toast.error("No se pudo completar la búsqueda", { id: tid });
    } finally {
      setSearching(false);
    }
  }, [searching, ov, qc]);

  return { searching, seconds, run };
}
