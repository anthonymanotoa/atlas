import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { qk } from "./keys";

// F3 §6.1 follow-ups. La web SOLO lee los buckets que el engine ya sembró (urgent/overdue/
// waiting/cold) y confirma el envío de un toque — todo determinista, $0, sin LLM. Marcar
// enviado siembra el siguiente toque server-side → invalidamos la query para refrescar buckets.
export function useFollowups(enabled = true) {
  return useQuery({ queryKey: qk.followups, queryFn: api.followups, enabled });
}

export function useMarkFollowupSent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.markFollowupSent(id, true),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.followups });
      qc.invalidateQueries({ queryKey: qk.overview });
    },
  });
}
