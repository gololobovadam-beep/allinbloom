import { cookies } from "next/headers";

const API_BASE = process.env.API_BASE_URL || "";

export const apiUrl = (path: string) => {
  if (!API_BASE) return path;
  return `${API_BASE}${path}`;
};

const getServerCookieHeader = async () => {
  const store = await cookies();
  const all = store.getAll();
  if (!all.length) return "";
  return all.map(({ name, value }) => `${name}=${value}`).join("; ");
};

export const apiFetch = async (
  path: string,
  options: RequestInit = {},
  auth: boolean = false
) => {
  const headers = new Headers(options.headers);
  // Server Components do not automatically forward incoming browser cookies to
  // an external FastAPI origin. Forward them only for explicitly
  // authenticated SSR/server-action calls, preserving the HttpOnly auth model
  // without attaching session cookies to public API requests.
  if (auth && !headers.has("Cookie")) {
    const cookieHeader = await getServerCookieHeader();
    if (cookieHeader) headers.set("Cookie", cookieHeader);
  }

  return fetch(apiUrl(path), {
    ...options,
    headers,
    cache: "no-store",
  });
};
