import { QueryClientProvider } from "@tanstack/react-query";
import { useMemo } from "react";
import { createBrowserRouter, RouterProvider } from "react-router";
import { TooltipProvider } from "./components/ui/tooltip";
import { queryClient } from "./lib/queryClient";
import { routes } from "./routes";

// App = solo providers. Todo el layout vive en AppShell; los datos, en src/hooks/.
export default function App() {
  const router = useMemo(() => createBrowserRouter(routes), []);
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <RouterProvider router={router} />
      </TooltipProvider>
    </QueryClientProvider>
  );
}
