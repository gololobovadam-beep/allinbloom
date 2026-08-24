import { cookies } from "next/headers";

const API_BASE = process.env.API_BASE_URL || "";

export const apiUrl = (path: string) => {
  if (!API_BASE) return path;
  return `${API_BASE}${path}`;
};

const getServerCookieHeader = async (cookieNames?: readonly string[]) => {
  const store = await cookies();
  const allowed = cookieNames ? new Set(cookieNames) : null;
  const all = allowed
    ? store.getAll().filter(({ name }) => allowed.has(name))
    : store.getAll();
  if (!all.length) return "";
  return all.map(({ name, value }) => `${name}=${value}`).join("; ");
};

export const apiFetch = async (
  path: string,
  options: RequestInit = {},
  auth: boolean = false,
  forwardedCookieNames?: readonly string[]
) => {
  const headers = new Headers(options.headers);
  // Server Components do not automatically forward incoming browser cookies to
  // an external FastAPI origin. Forward them only for explicitly
  // authenticated SSR/server-action calls, preserving the HttpOnly auth model
  // without attaching session cookies to public API requests.
  if ((auth || forwardedCookieNames?.length) && !headers.has("Cookie")) {
    const cookieHeader = await getServerCookieHeader(
      auth ? undefined : forwardedCookieNames
    );
    if (cookieHeader) headers.set("Cookie", cookieHeader);
  }

  return fetch(apiUrl(path), {
    ...options,
    headers,
    cache: "no-store",
  });
};
