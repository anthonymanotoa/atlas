import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Recommendation } from "../api";
import { qk } from "./keys";

// F3 §6.2 analytics. La web lee la composición determinista (funnel con tasas, piso de score,
// conversión por dimensión, tiempos, recomendaciones) y aplica UNA rec (edita criteria.md del
// perfil activo por el mutator validado). $0, sin LLM. Aplicar una rec cambia los umbrales →
// invalidamos analytics (y overview, que depende de los mismos criterios) para refrescar.
export function useAnalytics(enabled = true) {
  return useQuery({ queryKey: qk.analytics, queryFn: api.analytics, enabled });
}

export function useApplyRec() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (rec: Recommendation) => api.applyRec(rec),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.analytics });
      qc.invalidateQueries({ queryKey: qk.overview });
    },
  });
}
