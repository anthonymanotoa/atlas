import { Navigate, type RouteObject } from "react-router";
import { AppShell } from "./components/AppShell";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { PipelinePage } from "./pages/PipelinePage";
import { PortfolioPage } from "./pages/PortfolioPage";

// /jobs/:id nace apuntando al DetailDrawer sobre el pipeline (paridad) y la
// Task 8 lo reemplaza por la página completa JobDetailPage.
import { JobDetailRoute } from "./pages/PipelinePage";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/pipeline" replace /> },
      { path: "pipeline", element: <PipelinePage /> },
      { path: "jobs/:id", element: <JobDetailRoute /> },
      { path: "analytics", element: <AnalyticsPage /> },
      { path: "portfolio", element: <PortfolioPage /> },
      { path: "onboarding", element: <OnboardingPage /> },
      { path: "*", element: <Navigate to="/pipeline" replace /> },
    ],
  },
];
