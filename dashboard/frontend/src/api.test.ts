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

  it("prep() defaults language to en", async () => {
    fetchMock.mockResolvedValue(okJson({ ok: true }));
    await api.prep("abc");
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/jobs/abc/prep");
    expect(opts.body).toBe(JSON.stringify({ language: "en" }));
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
});
