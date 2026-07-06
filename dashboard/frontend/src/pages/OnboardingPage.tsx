import { useQueryClient } from "@tanstack/react-query";
import { OnboardingWizard } from "../components/onboarding/OnboardingWizard";
import { LoadingState } from "../components/ui/states";
import { useOnboarding } from "../hooks/useOnboarding";

export function OnboardingPage() {
  const onboardingQ = useOnboarding();
  const qc = useQueryClient();
  if (onboardingQ.isPending) {
    return <LoadingState rows={2} className="mx-auto max-w-[760px]" />;
  }
  if (!onboardingQ.data) return null;
  return <OnboardingWizard status={onboardingQ.data} onDone={() => qc.invalidateQueries()} />;
}
