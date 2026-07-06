import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { qk } from "./keys";

// F4 §7.2 profile_expand. La web SOLO lee los borradores de expansión que el brain ya produjo y
// aplica los ítems confirmados (por índice) — una escritura DETERMINISTA al master CV, aditiva e
// idempotente ($0: el escaneo de GitHub/portfolio/certs lo hizo el brain offline).
export function useProfileExpansions() {
  return useQuery({
    queryKey: qk.profileExpansions,
    queryFn: () => api.profileExpansions(),
  });
}

export function useApplyProfileExpansion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, indices }: { id: number; indices: number[] }) =>
      api.applyProfileExpansion(id, indices),
    // Al aplicar, el borrador marca esos ítems como `applied` → refrescamos la lista.
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.profileExpansions }),
  });
}
