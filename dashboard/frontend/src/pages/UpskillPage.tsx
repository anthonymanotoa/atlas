import { UpskillView } from "../components/UpskillView";
import { ErrorState, LoadingState } from "../components/ui/states";
import { useUpskillLatest } from "../hooks/useUpskill";

export function UpskillPage() {
  const q = useUpskillLatest();
  if (q.isPending) return <LoadingState rows={3} />;
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  return <UpskillView report={q.data?.report ?? null} />;
}
