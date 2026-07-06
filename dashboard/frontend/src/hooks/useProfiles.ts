import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { qk } from "./keys";

export function useProfiles() {
  return useQuery({ queryKey: qk.profiles, queryFn: api.profiles });
}

// Cambiar de perfil cambia TODO el universo de datos → invalidación total.
export function useSwitchProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.switchProfile(id),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useRenameProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, label }: { id: string; label: string }) => api.renameProfile(id, label),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.profiles }),
  });
}
