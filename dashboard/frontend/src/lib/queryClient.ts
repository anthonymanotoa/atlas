import { QueryClient } from "@tanstack/react-query";

// Cliente único de la app. staleTime corto: el dashboard es local (127.0.0.1),
// pero evita refetch en cascada al montar varias vistas que comparten queries.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
  },
});
