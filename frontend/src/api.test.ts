import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, send, upload } from "./api";
afterEach(() => vi.unstubAllGlobals());
describe("HTTP client", () => {
  it("sends session cookies and a JSON body without any AI credential", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ id: 3 }),
      });
    vi.stubGlobal("fetch", fetchMock);
    expect(
      await send("/projects", "POST", { name: "Konstruksion FV" }),
    ).toEqual({ id: 3 });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/projects");
    expect(options.credentials).toBe("same-origin");
    expect(options.headers.get("Content-Type")).toBe("application/json");
    expect(options.body).toBe('{"name":"Konstruksion FV"}');
    expect(options.headers.has("Authorization")).toBe(false);
  });
  it("preserves multipart boundaries for file upload", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ id: 1 }),
      });
    vi.stubGlobal("fetch", fetchMock);
    await upload("/projects/1/imports", new File(["data"], "boq.xlsx"));
    const options = fetchMock.mock.calls[0][1];
    expect(options.headers.has("Content-Type")).toBe(false);
    expect(options.body.get("file").name).toBe("boq.xlsx");
  });
  it("shows validation errors and retains HTTP status", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue({
          ok: false,
          status: 422,
          json: async () => ({
            detail: [{ loc: ["body", "unit"], msg: "Field required" }],
          }),
        }),
    );
    await expect(api("/prices")).rejects.toMatchObject({
      status: 422,
      message: "unit: Field required",
    });
  });
  it("surfaces authorization rejection without fabricating results", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue({
          ok: false,
          status: 403,
          json: async () => ({ detail: "Nuk keni akses" }),
        }),
    );
    await expect(api("/projects/7")).rejects.toBeInstanceOf(ApiError);
  });
  it("handles empty logout response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 204 }),
    );
    expect(await send("/auth/logout", "POST")).toBeUndefined();
  });
});
