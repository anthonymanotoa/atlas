import { renderHook, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    board: vi.fn(),
    setState: vi.fn(),
    overview: vi.fn(),
    followups: vi.fn(),
    markFollowupSent: vi.fn(),
    analytics: vi.fn(),
    applyRec: vi.fn(),
    systemHealth: vi.fn(),
  },
}));
vi.mock("../api", () => ({ api }));

import { makeQueryClient } from "../test/utils";
import { useAnalytics, useApplyRec } from "./useAnalytics";
import { useFollowups, useMarkFollowupSent } from "./useFollowups";
import { qk } from "./keys";
import { useSystemHealth } from "./useSystemHealth";
import { useBoard, useSetJobState, type BoardData } from "./useBoard";

const board: BoardData = {
  columns: ["shortlisted", "applied"],
  jobs: {
    shortlisted: [{ id: "j1", title: "DS", company: "Acme", state: "shortlisted" }],
    applied: [],
  },
  dismissed: [],
};

function wrapperFor(qc: ReturnType<typeof makeQueryClient>) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("useBoard", () => {
  beforeEach(() => vi.clearAllMocks());

  it("carga el tablero desde /api/board", async () => {
    api.board.mockResolvedValue(board);
    const qc = makeQueryClient();
    const { result } = renderHook(() => useBoard(), { wrapper: wrapperFor(qc) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.columns).toEqual(["shortlisted", "applied"]);
    expect(api.board).toHaveBeenCalledTimes(1);
  });

  it("enabled=false no dispara la request (gate de onboarding)", async () => {
    const qc = makeQueryClient();
    renderHook(() => useBoard(false), { wrapper: wrapperFor(qc) });
    await new Promise((r) => setTimeout(r, 20));
    expect(api.board).not.toHaveBeenCalled();
  });
});

describe("useSetJobState", () => {
  beforeEach(() => vi.clearAllMocks());

  it("mueve el job en cache de forma optimista antes de resolver", async () => {
    api.setState.mockImplementation(() => new Promise(() => {})); // nunca resuelve
    const qc = makeQueryClient();
    qc.setQueryData(qk.board, board);
    const { result } = renderHook(() => useSetJobState(), { wrapper: wrapperFor(qc) });
    result.current.mutate({ id: "j1", state: "applied" });
    await waitFor(() => {
      const data = qc.getQueryData<BoardData>(qk.board);
      expect(data?.jobs.shortlisted).toHaveLength(0);
      expect(data?.jobs.applied?.[0]?.id).toBe("j1");
      expect(data?.jobs.applied?.[0]?.state).toBe("applied");
    });
  });

  it("si la API falla, hace rollback del cache", async () => {
    api.setState.mockRejectedValue(new Error("boom"));
    const qc = makeQueryClient();
    qc.setQueryData(qk.board, board);
    const { result } = renderHook(() => useSetJobState(), { wrapper: wrapperFor(qc) });
    result.current.mutate({ id: "j1", state: "applied" });
    await waitFor(() => expect(result.current.isError).toBe(true));
    const data = qc.getQueryData<BoardData>(qk.board);
    expect(data?.jobs.shortlisted?.[0]?.id).toBe("j1");
  });
});

describe("useFollowups / useMarkFollowupSent", () => {
  beforeEach(() => vi.clearAllMocks());

  it("carga los buckets desde /api/followups", async () => {
    api.followups.mockResolvedValue({
      buckets: { urgent: [], overdue: [], waiting: [], cold: [] },
    });
    const qc = makeQueryClient();
    const { result } = renderHook(() => useFollowups(), { wrapper: wrapperFor(qc) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.followups).toHaveBeenCalledTimes(1);
  });

  it("markFollowupSent envía confirm:true e invalida followups", async () => {
    api.markFollowupSent.mockResolvedValue({ ok: true, next_id: 2 });
    const qc = makeQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useMarkFollowupSent(), { wrapper: wrapperFor(qc) });
    result.current.mutate(1);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.markFollowupSent).toHaveBeenCalledWith(1, true);
    expect(spy).toHaveBeenCalledWith({ queryKey: qk.followups });
  });
});

describe("useAnalytics / useApplyRec", () => {
  beforeEach(() => vi.clearAllMocks());

  it("carga la analítica desde /api/analytics", async () => {
    api.analytics.mockResolvedValue({ funnel: [], recommendations: [] });
    const qc = makeQueryClient();
    const { result } = renderHook(() => useAnalytics(), { wrapper: wrapperFor(qc) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.analytics).toHaveBeenCalledTimes(1);
  });

  it("applyRec invalida analytics al éxito", async () => {
    api.applyRec.mockResolvedValue({ ok: true, applied: "x=1" });
    const qc = makeQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const rec = { id: "r1", text: "t", action_type: "set_criteria" as const, payload: {} };
    const { result } = renderHook(() => useApplyRec(), { wrapper: wrapperFor(qc) });
    result.current.mutate(rec);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.applyRec).toHaveBeenCalledWith(rec);
    expect(spy).toHaveBeenCalledWith({ queryKey: qk.analytics });
  });
});

describe("useSystemHealth", () => {
  beforeEach(() => vi.clearAllMocks());

  it("carga la salud del sistema desde /api/system/health", async () => {
    api.systemHealth.mockResolvedValue({ profile: "owner" });
    const qc = makeQueryClient();
    const { result } = renderHook(() => useSystemHealth(), { wrapper: wrapperFor(qc) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.systemHealth).toHaveBeenCalledTimes(1);
  });
});
