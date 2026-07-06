import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { OnboardingStatus } from "../api";

// vi.hoisted so the mocks exist before vi.mock's hoisted factories reference them.
const { api } = vi.hoisted(() => ({
  api: {
    completeOnboarding: vi.fn(),
  },
}));
vi.mock("../api", () => ({ api }));

import { OnboardingGate } from "./OnboardingGate";

function statusFixture(overrides: Partial<OnboardingStatus> = {}): OnboardingStatus {
  return {
    complete: false,
    profile: "p1",
    domain: "",
    target_label: "",
    cv_present: true,
    audit: { findings: [], summary: { high: 0, med: 0, low: 0 } },
    ...overrides,
  };
}

describe("OnboardingGate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.completeOnboarding.mockResolvedValue({ ok: true });
  });

  it("renders target-aware copy when target_label is set", () => {
    render(
      <OnboardingGate
        status={statusFixture({ target_label: "Arquitectura" })}
        onComplete={() => {}}
        onRefresh={() => {}}
      />,
    );
    expect(screen.getByText(/hacia Arquitectura/)).toBeInTheDocument();
  });

  it("falls back to neutral copy when target_label is empty", () => {
    render(
      <OnboardingGate
        status={statusFixture({ target_label: "" })}
        onComplete={() => {}}
        onRefresh={() => {}}
      />,
    );
    expect(screen.getByText(/hacia tu rol objetivo/)).toBeInTheDocument();
  });

  it("complete flow calls api.completeOnboarding then onComplete", async () => {
    const onComplete = vi.fn();
    render(
      <OnboardingGate status={statusFixture()} onComplete={onComplete} onRefresh={() => {}} />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Completar onboarding y empezar" }),
    );
    expect(api.completeOnboarding).toHaveBeenCalledTimes(1);
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("refresh control calls onRefresh without completing onboarding", async () => {
    const onRefresh = vi.fn();
    render(
      <OnboardingGate status={statusFixture()} onComplete={() => {}} onRefresh={onRefresh} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /Re-evaluar/ }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
    expect(api.completeOnboarding).not.toHaveBeenCalled();
  });
});
