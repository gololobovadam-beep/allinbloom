import { describe, expect, it, vi } from "vitest";

import { AUTH_TOKEN_COOKIE, AUTH_USER_COOKIE } from "@/lib/auth-cookies";

type AuthRefreshResponse = {
  ok: boolean;
  status: number;
  json: () => Promise<unknown>;
};

const makeRefreshResponse = (
  payload: unknown,
  init: { ok: boolean; status: number } = { ok: true, status: 200 }
): AuthRefreshResponse => ({
  ok: init.ok,
  status: init.status,
  json: async () => payload,
});

const loadAuthClient = async () => {
  vi.resetModules();
  return import("@/lib/auth-client");
};

describe("auth-client session helpers", () => {
  it("never exposes a browser-readable authentication token", async () => {
    localStorage.setItem(AUTH_TOKEN_COOKIE, "legacy-token");
    document.cookie = `${AUTH_TOKEN_COOKIE}=legacy-cookie; Path=/`;

    const { getClientAuthToken } = await loadAuthClient();
    expect(getClientAuthToken()).toBeNull();
  });

  it("keeps only non-authoritative user display data in storage", async () => {
    const user = { id: "u1", email: "user@example.com", name: "User" };
    const { setAuthSession, getClientUser } = await loadAuthClient();

    setAuthSession(user);

    expect(getClientUser()).toEqual(user);
    expect(localStorage.getItem(AUTH_TOKEN_COOKIE)).toBeNull();
    expect(localStorage.getItem(AUTH_USER_COOKIE)).toBe(JSON.stringify(user));
  });
});

describe("auth-client refresh flow", () => {
  it("deduplicates concurrent cookie-based refresh requests", async () => {
    let resolveFetch: ((value: AuthRefreshResponse) => void) | undefined;
    const pendingResponse = new Promise<AuthRefreshResponse>((resolve) => {
      resolveFetch = resolve;
    });
    const fetchMock = vi.fn(() => pendingResponse);
    vi.stubGlobal("fetch", fetchMock);

    const authClient = await loadAuthClient();
    const p1 = authClient.refreshAuthSession();
    const p2 = authClient.refreshAuthSession();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/refresh", {
      method: "POST",
      credentials: "include",
    });

    resolveFetch?.(
      makeRefreshResponse({ user: { id: "u1", email: "user@example.com" } })
    );

    const [result1, result2] = await Promise.all([p1, p2]);
    expect(result1).toEqual({ id: "u1", email: "user@example.com" });
    expect(result2).toEqual(result1);
    expect(localStorage.getItem(AUTH_TOKEN_COOKIE)).toBeNull();
  });

  it("clears browser display state after refresh 401", async () => {
    localStorage.setItem(AUTH_TOKEN_COOKIE, "old-token");
    localStorage.setItem(
      AUTH_USER_COOKIE,
      JSON.stringify({ id: "u1", email: "user@example.com" })
    );
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        makeRefreshResponse({}, { ok: false, status: 401 })
      )
    );

    const authClient = await loadAuthClient();
    const result = await authClient.refreshAuthSession();

    expect(result).toBeNull();
    expect(localStorage.getItem(AUTH_TOKEN_COOKIE)).toBeNull();
    expect(localStorage.getItem(AUTH_USER_COOKIE)).toBeNull();
  });
});
