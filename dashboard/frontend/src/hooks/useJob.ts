import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { qk } from "./keys";

export function useJob(id?: string) {
  return useQuery({
    queryKey: qk.job(id ?? ""),
    queryFn: () => api.job(id as string),
    enabled: !!id,
  });
}

function useInvalidateJob() {
  const qc = useQueryClient();
  return (id: string) => {
    qc.invalidateQueries({ queryKey: qk.job(id) });
    qc.invalidateQueries({ queryKey: qk.board });
    qc.invalidateQueries({ queryKey: qk.overview });
  };
}

export function usePrepJob() {
  const invalidate = useInvalidateJob();
  return useMutation({
    mutationFn: ({ id, language }: { id: string; language?: string }) => api.prep(id, language),
    onSettled: (_d, _e, { id }) => invalidate(id),
  });
}

export function useMarkApplied() {
  const invalidate = useInvalidateJob();
  return useMutation({
    mutationFn: (id: string) => api.markApplied(id),
    onSettled: (_d, _e, id) => invalidate(id),
  });
}

export function useRecordOutcome() {
  const invalidate = useInvalidateJob();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Parameters<typeof api.recordOutcome>[1] }) =>
      api.recordOutcome(id, body),
    onSettled: (_d, _e, { id }) => invalidate(id),
  });
}
