import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { qk } from "./keys";

// Cola de intents del brain (F4 §7.1). Poll cada 30 s para que el badge de pendientes y la
// lista reflejen el trabajo que el brain va drenando en background, sin recargar la página.
export function useIntents() {
  return useQuery({
    queryKey: qk.intents,
    queryFn: () => api.intents(),
    refetchInterval: 30_000,
  });
}

// Encolar es la ÚNICA escritura de la web sobre intents ($0: solo inserta una fila `pending`).
// Al encolar, invalidamos la cola para que el panel se actualice al instante (badge + lista).
export function useEnqueueIntent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      type,
      payload,
      jobId,
    }: {
      type: string;
      payload?: Record<string, unknown>;
      jobId?: string;
    }) => api.enqueueIntent(type, payload, jobId),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.intents }),
  });
}
