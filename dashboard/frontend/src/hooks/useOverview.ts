import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { qk } from "./keys";

export function useOverview(enabled = true) {
  return useQuery({ queryKey: qk.overview, queryFn: api.overview, enabled });
}
