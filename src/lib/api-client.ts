"use client";

import { refreshAuthSession } from "@/lib/auth-client";

export const clientFetch = async (
  path: string,
  options: RequestInit = {},
  auth: boolean = false
) => {
  const makeRequest = (headers: Headers) =>
    fetch(path, {
      ...options,
      headers,
      credentials: options.credentials ?? "include",
    });

  const headers = new Headers(options.headers);

  const response = await makeRequest(headers);
  if (!auth || response.status !== 401) {
    return response;
  }

  const refreshed = await refreshAuthSession();
  if (!refreshed) {
    return response;
  }

  return makeRequest(new Headers(options.headers));
};
