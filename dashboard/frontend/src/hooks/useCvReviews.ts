import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { qk } from "./keys";

// F4 §7.2 cv_review. La web SOLO lee las revisiones que el brain ya produjo y dispara acciones
// DETERMINISTAS (aplicar un edit, resolver un flag): ninguna llama a un LLM. apply-edit y
// soften/drop re-renderizan el CV → invalidamos también la vacante para refrescar sus versiones.
export function useCvReviews(jobId: string) {
  return useQuery({
    queryKey: qk.cvReviews(jobId),
    queryFn: () => api.cvReviews(jobId),
  });
}

export function useApplyCvReviewEdit(jobId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, index }: { id: number; index: number }) => api.applyCvReviewEdit(id, index),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.cvReviews(jobId) });
      qc.invalidateQueries({ queryKey: qk.job(jobId) });
    },
  });
}

export function useResolveCvReviewFlag(jobId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      index,
      action,
    }: {
      id: number;
      index: number;
      action: "keep" | "soften" | "drop";
    }) => api.resolveCvReviewFlag(id, index, action),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.cvReviews(jobId) });
      qc.invalidateQueries({ queryKey: qk.job(jobId) });
    },
  });
}
