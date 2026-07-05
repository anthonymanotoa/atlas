import { AnalyticsStrip } from "../components/AnalyticsStrip";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/states";
import { useOverview } from "../hooks/useOverview";

export function AnalyticsPage() {
  const overviewQ = useOverview();
  if (overviewQ.isPending) return <LoadingState rows={3} />;
  if (overviewQ.isError) return <ErrorState onRetry={() => overviewQ.refetch()} />;
  if (!overviewQ.data) return null;

  const ov = overviewQ.data.overview;
  return (
    <>
      <h1 className="mb-4 text-h1">Analítica</h1>
      <AnalyticsStrip ov={ov} />
      {ov.total_jobs === 0 && ov.funnel.length === 0 && (
        <div className="mt-4">
          <EmptyState
            title="Sin datos todavía"
            description="Corre una búsqueda para poblar el embudo."
          />
        </div>
      )}
    </>
  );
}
