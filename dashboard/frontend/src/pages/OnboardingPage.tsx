import { useQueryClient } from "@tanstack/react-query";
import { OnboardingGate } from "../components/OnboardingGate";
import { Skeleton } from "../components/ui/skeleton";
import { qk } from "../hooks/keys";
import { useOnboarding } from "../hooks/useOnboarding";

export function OnboardingPage() {
  const onboardingQ = useOnboarding();
  const qc = useQueryClient();
  if (onboardingQ.isPending) return <Skeleton className="mx-auto mt-8 h-96 max-w-[760px]" />;
  if (!onboardingQ.data) return null;
  return (
    <OnboardingGate
      status={onboardingQ.data}
      onComplete={() => qc.invalidateQueries()}
      onRefresh={() => qc.invalidateQueries({ queryKey: qk.onboarding })}
    />
  );
}
