import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { qk } from "./keys";

// F3 §6.5 system health. Lectura del estado del sistema (fuentes, DB, garantías $0) vía la capa
// de datos TanStack Query — reemplaza el useState+useEffect imperativo previo en SettingsOps.
export function useSystemHealth(enabled = true) {
  return useQuery({ queryKey: qk.systemHealth, queryFn: api.systemHealth, enabled });
}
