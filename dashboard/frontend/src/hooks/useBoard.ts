import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Job } from "../api";
import { qk } from "./keys";

export type BoardData = { columns: string[]; jobs: Record<string, Job[]>; dismissed: Job[] };

export function useBoard(enabled = true) {
  return useQuery({ queryKey: qk.board, queryFn: api.board, enabled });
}

// Mutación única de estado (move / dismiss / restore). Move optimista en cache
// con rollback en error — reemplaza el setJobs() manual de App.tsx.
export function useSetJobState() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, state }: { id: string; state: string }) => api.setState(id, state),
    onMutate: async ({ id, state }) => {
      await qc.cancelQueries({ queryKey: qk.board });
      const prev = qc.getQueryData<BoardData>(qk.board);
      if (prev) {
        const jobs: Record<string, Job[]> = {};
        let moved: Job | undefined;
        for (const c of Object.keys(prev.jobs)) {
          jobs[c] = prev.jobs[c].filter((j) => {
            if (j.id === id) {
              moved = j;
              return false;
            }
            return true;
          });
        }
        if (moved && jobs[state]) jobs[state] = [{ ...moved, state }, ...jobs[state]];
        qc.setQueryData<BoardData>(qk.board, { ...prev, jobs });
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(qk.board, ctx.prev);
    },
    onSettled: (_data, _err, { id }) => {
      qc.invalidateQueries({ queryKey: qk.board });
      qc.invalidateQueries({ queryKey: qk.overview });
      qc.invalidateQueries({ queryKey: qk.job(id) });
    },
  });
}
