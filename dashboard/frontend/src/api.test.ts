import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

const okJson = (data: unknown) => ({ ok: true, status: 200, json: async () => data });

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("overview() GETs /api/overview and returns the JSON", async () => {
    fetchMock.mockResolvedValue(okJson({ overview: {}, needs_action: [] }));
    const out = await api.overview();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/overview");
    expect(out).toEqual({ overview: {}, needs_action: [] });
  });

  it("job(id) GETs the per-job URL", async () => {
    fetchMock.mockResolvedValue(okJson({}));
    await api.job("abc");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/jobs/abc");
  });

  it("setState() POSTs JSON with the right method/headers/body", async () => {
    fetchMock.mockResolvedValue(okJson({ ok: true }));
    await api.setState("abc", "applied");
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/jobs/abc/state");
    expect(opts.method).toBe("POST");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    expect(opts.body).toBe(JSON.stringify({ state: "applied" }));
  });

  it("markApplied() POSTs with no body", async () => {
    fetchMock.mockResolvedValue(okJson({ ok: true }));
    await api.markApplied("abc");
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/jobs/abc/applied");
    expect(opts.method).toBe("POST");
    expect(opts.body).toBeUndefined();
  });

  it("prep() omits language by default so the backend picks the posting's language", async () => {
    fetchMock.mockResolvedValue(okJson({ ok: true }));
    await api.prep("abc");
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/jobs/abc/prep");
    expect(opts.body).toBe(JSON.stringify({}));
  });

  it("prep(lang) sends the explicit language when given", async () => {
    fetchMock.mockResolvedValue(okJson({ ok: true }));
    await api.prep("abc", "es");
    expect(fetchMock.mock.calls[0][1].body).toBe(JSON.stringify({ language: "es" }));
  });

  it("discover() POSTs /api/discover", async () => {
    fetchMock.mockResolvedValue(okJson({ started: true }));
    await api.discover();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/discover");
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
  });

  it("throws with the status code when the response is not ok", async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 404, json: async () => ({}) });
    await expect(api.job("x")).rejects.toThrow("404");
  });

  it("cvDownload() builds a URL string and never calls fetch", () => {
    const url = api.cvDownload("abc", 3);
    expect(url).toBe("/api/cv/abc/3/download?fmt=docx");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("criteria() GETs /api/criteria", async () => {
    fetchMock.mockResolvedValue(okJson({ criteria: {}, prose: "" }));
    await api.criteria();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/criteria");
  });

  it("saveCriteria() PUTs JSON with the right method/headers/body", async () => {
    fetchMock.mockResolvedValue(okJson({ ok: true, path: "criteria.md" }));
    const criteria = { roles: ["DE"] } as unknown as Parameters<typeof api.saveCriteria>[0];
    await api.saveCriteria(criteria, "prose text");
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/criteria");
    expect(opts.method).toBe("PUT");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    expect(opts.body).toBe(JSON.stringify({ criteria, prose: "prose text" }));
  });

  it("importCv() POSTs multipart FormData WITHOUT a manual Content-Type", async () => {
    fetchMock.mockResolvedValue(okJson({ ok: true, draft: "", path: "cv.md", chars: 0 }));
    const file = new File(["cv bytes"], "cv.pdf", { type: "application/pdf" });
    await api.importCv(file);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/cv/import");
    expect(opts.method).toBe("POST");
    // The browser must set the multipart boundary itself → we never set Content-Type.
    expect(opts.headers).toBeUndefined();
    expect(opts.body).toBeInstanceOf(FormData);
    expect((opts.body as FormData).get("file")).toBe(file);
  });

  it("livenessSweep() POSTs /api/liveness/sweep", async () => {
    fetchMock.mockResolvedValue(okJson({ started: true }));
    await api.livenessSweep();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/liveness/sweep");
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
  });

  it("followups() GETs /api/followups", async () => {
    fetchMock.mockResolvedValue(
      okJson({ buckets: { urgent: [], overdue: [], waiting: [], cold: [] } }),
    );
    await api.followups();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/followups");
  });

  it("markFollowupSent() POSTs the id with confirm:true", async () => {
    fetchMock.mockResolvedValue(okJson({ ok: true, next_id: 2 }));
    await api.markFollowupSent(7);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/followups/7/sent");
    expect(opts.method).toBe("POST");
    expect(opts.body).toBe(JSON.stringify({ confirm: true }));
  });

  it("analytics() GETs /api/analytics", async () => {
    fetchMock.mockResolvedValue(okJson({ funnel: [], recommendations: [] }));
    await api.analytics();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/analytics");
  });

  it("applyRec() POSTs id/action_type/payload to /api/analytics/apply-rec", async () => {
    fetchMock.mockResolvedValue(okJson({ ok: true, applied: "shortlist_threshold=62" }));
    await api.applyRec({
      id: "threshold-62",
      text: "…",
      action_type: "set_criteria",
      payload: { field: "shortlist_threshold", value: 62 },
    });
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/analytics/apply-rec");
    expect(opts.method).toBe("POST");
    expect(opts.body).toBe(
      JSON.stringify({
        id: "threshold-62",
        action_type: "set_criteria",
        payload: { field: "shortlist_threshold", value: 62 },
      }),
    );
  });
});
