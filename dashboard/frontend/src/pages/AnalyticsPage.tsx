import { AnalyticsStrip } from "../components/AnalyticsStrip";
import { Skeleton } from "../components/ui/skeleton";
import { useOverview } from "../hooks/useOverview";

export function AnalyticsPage() {
  const overviewQ = useOverview();
  if (overviewQ.isPending) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (!overviewQ.data) return null;
  return (
    <>
      <h1 className="mb-4 text-h1">Analítica</h1>
      <AnalyticsStrip ov={overviewQ.data.overview} />
    </>
  );
}
