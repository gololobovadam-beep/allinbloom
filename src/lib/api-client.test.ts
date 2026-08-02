import { describe, expect, it, vi } from "vitest";

const response = (status = 200) => ({ status, ok: status < 400 });

describe("clientFetch", () => {
  it("uses browser cookies for authenticated calls and never adds Authorization", async () => {
    vi.resetModules();
    const fetchMock = vi.fn().mockResolvedValue(response());
    vi.stubGlobal("fetch", fetchMock);

    const { clientFetch } = await import("@/lib/api-client");
    await clientFetch("/api/users/me", { method: "GET" }, true);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(options.credentials).toBe("include");
    expect(new Headers(options.headers).has("Authorization")).toBe(false);
  });
});
