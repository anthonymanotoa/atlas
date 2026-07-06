import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Peer } from "../api";
import { qk } from "./keys";

export function usePortfolioLatest() {
  return useQuery({ queryKey: qk.portfolio, queryFn: api.portfolioLatest });
}

export function usePeers() {
  return useQuery({ queryKey: qk.peers, queryFn: api.peers });
}

export function usePortfolioResearch() {
  return useQuery({ queryKey: qk.portfolioResearch, queryFn: api.portfolioResearch });
}

export function useGeneratePortfolio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (includeGithub: boolean) => api.generatePortfolio(includeGithub),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.portfolio }),
  });
}

export function useAddPeer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Peer>) => api.addPeer(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.peers }),
  });
}
