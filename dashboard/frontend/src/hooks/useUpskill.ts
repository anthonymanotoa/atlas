import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { qk } from "./keys";

// F4 §7.2: el último reporte de upskilling (gap analysis). Read-only ($0) — la pasada 1 es
// determinista y la síntesis la escribió el brain offline; aquí solo se lee la fila persistida.
export function useUpskillLatest() {
  return useQuery({ queryKey: qk.upskill, queryFn: api.upskillLatest });
}
