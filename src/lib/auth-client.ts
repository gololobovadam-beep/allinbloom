"use client";

import { AUTH_TOKEN_COOKIE, AUTH_USER_COOKIE } from "@/lib/auth-cookies";

export type AuthUser = {
  id: string;
  email: string;
  name?: string | null;
  role?: string | null;
  image?: string | null;
  phone?: string | null;
};

type RefreshPayload = {
  user?: AuthUser;
};

let pendingRefresh: Promise<AuthUser | null> | null = null;

const setStorage = (key: string, value: string) => {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Ignore storage errors.
  }
};

const getStorage = (key: string) => {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
};

const removeStorage = (key: string) => {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Ignore storage errors.
  }
};

const clearLegacyCookie = (name: string) => {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=; Path=/; Max-Age=0; SameSite=Lax`;
};

/**
 * Kept only as a compatibility export while callers migrate.  Authentication
 * credentials are intentionally never readable from browser JavaScript.
 */
export const getClientAuthToken = () => null;

export const getClientUser = () => {
  const stored = getStorage(AUTH_USER_COOKIE);
  if (!stored) return null;
  try {
    return JSON.parse(stored) as AuthUser;
  } catch {
    removeStorage(AUTH_USER_COOKIE);
    return null;
  }
};

export const setAuthSession = (user: AuthUser) => {
  if (typeof window === "undefined") return;
  // User display data is not an authority signal; the server always reads the
  // HttpOnly session cookies.  Remove old JS-readable access tokens eagerly.
  removeStorage(AUTH_TOKEN_COOKIE);
  setStorage(AUTH_USER_COOKIE, JSON.stringify(user));
  clearLegacyCookie(AUTH_TOKEN_COOKIE);
  clearLegacyCookie(AUTH_USER_COOKIE);
};

export const clearAuthSession = () => {
  removeStorage(AUTH_TOKEN_COOKIE);
  removeStorage(AUTH_USER_COOKIE);
  clearLegacyCookie(AUTH_TOKEN_COOKIE);
  clearLegacyCookie(AUTH_USER_COOKIE);
};

export const refreshAuthSession = async (): Promise<AuthUser | null> => {
  if (pendingRefresh) return pendingRefresh;

  pendingRefresh = (async () => {
    const response = await fetch("/api/auth/refresh", {
      method: "POST",
      credentials: "include",
    });
    if (!response.ok) {
      if (response.status === 401) clearAuthSession();
      return null;
    }
    const payload = (await response.json().catch(() => null)) as RefreshPayload | null;
    const user = payload?.user;
    if (!user) return null;
    setAuthSession(user);
    return user;
  })();

  try {
    return await pendingRefresh;
  } finally {
    pendingRefresh = null;
  }
};

/** @deprecated Browser code must use cookie-authenticated fetch instead. */
export const getUsableAuthToken = async () => null;
