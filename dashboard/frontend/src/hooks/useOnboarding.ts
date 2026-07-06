import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { qk } from "./keys";

export function useOnboarding() {
  return useQuery({ queryKey: qk.onboarding, queryFn: api.onboarding });
}

export function useCompleteOnboarding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.completeOnboarding(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.onboarding });
      qc.invalidateQueries({ queryKey: qk.board });
      qc.invalidateQueries({ queryKey: qk.overview });
    },
  });
}
