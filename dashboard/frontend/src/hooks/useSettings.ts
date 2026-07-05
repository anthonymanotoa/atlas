import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { qk } from "./keys";

export function useSettings(enabled = true) {
  return useQuery({ queryKey: qk.settings, queryFn: api.settings, enabled });
}

export function useSetSetting() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) => api.setSetting(key, value),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.settings });
      qc.invalidateQueries({ queryKey: qk.csvColumns });
    },
  });
}

export function useCsvColumns(enabled = true) {
  return useQuery({ queryKey: qk.csvColumns, queryFn: api.csvColumns, enabled });
}

export function useCvLibrary(enabled = true) {
  return useQuery({ queryKey: qk.cvLibrary, queryFn: api.cvLibrary, enabled });
}
