"use client";

import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import { setAuthSession } from "@/lib/auth-client";
import { clientFetch } from "@/lib/api-client";
import { getGoogleRedirectUri } from "@/lib/google-auth";

type GoogleCodeResponse = {
  code?: string;
  state?: string;
  error?: string;
};

type GoogleCodeClient = {
  requestCode: () => void;
};

type GoogleAccountsOauth2 = {
  initCodeClient: (config: {
    client_id: string;
    scope: string;
    ux_mode?: "popup" | "redirect";
    callback?: (response: GoogleCodeResponse) => void;
    redirect_uri?: string;
    state?: string;
    error_callback?: () => void;
  }) => GoogleCodeClient;
};

type GoogleWindow = Window & {
  google?: {
    accounts?: {
      oauth2?: GoogleAccountsOauth2;
    };
  };
};

const GOOGLE_SCOPE = "openid email profile";
const isMobileBrowser = () => {
  if (typeof navigator === "undefined") return false;
  return /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || "");
};

const requestGoogleOauthState = async () => {
  const response = await clientFetch("/api/auth/google/state", {
    method: "POST",
  });
  const payload = (await response.json().catch(() => null)) as
    | { state?: string; detail?: string }
    | null;
  const state = payload?.state?.trim();
  if (!response.ok || !state) {
    throw new Error(payload?.detail || "Unable to start Google sign-in.");
  }
  return state;
};

export default function AuthPanel() {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [needsName, setNeedsName] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [retryAfter, setRetryAfter] = useState<number | null>(null);
  const [googleBusy, setGoogleBusy] = useState(false);
  const [googleReady, setGoogleReady] = useState(false);
  const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";
  const googleEnabled =
    process.env.NEXT_PUBLIC_GOOGLE_ENABLED === "true" && Boolean(googleClientId);

  const completeGoogleSignIn = useCallback(
    async (path: string, body: Record<string, string>, fallbackMessage: string) => {
      setStatus("Signing in...");
      const verify = await clientFetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await verify.json().catch(() => ({}));
      if (!verify.ok) {
        setStatus(payload?.detail || fallbackMessage);
        return;
      }

      const user = payload?.user;
      if (!user) {
        setStatus(fallbackMessage);
        return;
      }

      setAuthSession(user);
      window.location.href = "/";
    },
    []
  );

  const getGoogleOauth2 = useCallback(() => {
    const google = (window as GoogleWindow).google;
    return google?.accounts?.oauth2 || null;
  }, []);

  const startGoogleRedirectSignIn = useCallback(async () => {
    const googleOauth2 = getGoogleOauth2();
    if (!googleOauth2) {
      setGoogleBusy(false);
      setStatus("Google sign-in is not ready yet. Refresh and try again.");
      return;
    }

    let state: string;
    try {
      state = await requestGoogleOauthState();
    } catch {
      setGoogleBusy(false);
      setStatus("Unable to start Google sign-in. Please try again.");
      return;
    }

    const redirectUri = getGoogleRedirectUri();
    try {
      const codeClient = googleOauth2.initCodeClient({
        client_id: googleClientId,
        scope: GOOGLE_SCOPE,
        ux_mode: "redirect",
        redirect_uri: redirectUri,
        state,
      });
      codeClient.requestCode();
    } catch {
      setGoogleBusy(false);
      setStatus("Unable to open Google sign-in.");
    }
  }, [getGoogleOauth2, googleClientId]);

  const requestGoogleSignIn = useCallback(async () => {
    const googleOauth2 = getGoogleOauth2();
    if (!googleOauth2) {
      setStatus("Google sign-in is not ready yet. Refresh and try again.");
      return;
    }

    setGoogleBusy(true);
    setStatus("Opening Google sign-in...");

    if (isMobileBrowser()) {
      void startGoogleRedirectSignIn();
      return;
    }

    try {
      const state = await requestGoogleOauthState();
      const codeClient = googleOauth2.initCodeClient({
        client_id: googleClientId,
        scope: GOOGLE_SCOPE,
        ux_mode: "popup",
        state,
        callback: (response) => {
          if (response?.error || !response?.code || response.state !== state) {
            setStatus("Continuing Google sign-in in this tab...");
            void startGoogleRedirectSignIn();
            return;
          }
          setGoogleBusy(false);
          void completeGoogleSignIn(
            "/api/auth/google/code",
            { code: response.code, state },
            "Unable to sign in with Google."
          );
        },
        error_callback: () => {
          setStatus("Continuing Google sign-in in this tab...");
          void startGoogleRedirectSignIn();
        },
      });
      codeClient.requestCode();
    } catch {
      setStatus("Unable to start Google sign-in. Please try again.");
      setGoogleBusy(false);
    }
  }, [
    completeGoogleSignIn,
    getGoogleOauth2,
    googleClientId,
    startGoogleRedirectSignIn,
  ]);

  useEffect(() => {
    if (!googleEnabled || !googleClientId) return;

    const onLoaded = () => {
      const ready = Boolean(getGoogleOauth2());
      setGoogleReady(ready);
      if (!ready) {
        setStatus("Unable to load Google sign-in right now.");
      }
    };

    const onLoadFailed = () => {
      setGoogleReady(false);
      setStatus(
        "Unable to load Google sign-in. Disable blockers and refresh the page."
      );
    };

    const existing = document.getElementById("google-identity") as HTMLScriptElement | null;
    if (existing) {
      if (getGoogleOauth2()) {
        onLoaded();
        return;
      }
      existing.addEventListener("load", onLoaded, { once: true });
      existing.addEventListener("error", onLoadFailed, { once: true });
      return () => {
        existing.removeEventListener("load", onLoaded);
        existing.removeEventListener("error", onLoadFailed);
      };
    }

    const script = document.createElement("script");
    script.id = "google-identity";
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = onLoaded;
    script.onerror = onLoadFailed;
    document.head.appendChild(script);
  }, [getGoogleOauth2, googleClientId, googleEnabled]);

  useEffect(() => {
    if (!retryAfter) return;
    const timer = setInterval(() => {
      setRetryAfter((prev) => {
        if (!prev || prev <= 1) {
          clearInterval(timer);
          return null;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [retryAfter]);

  const requestCode = async () => {
    setStatus("Sending code...");
    const response = await clientFetch("/api/auth/request-code", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });

    const payload = await response.json().catch(() => ({}));

    if (response.ok) {
      setNeedsName(false);
      setCodeSent(true);
      setRetryAfter(null);
      setStatus("Code sent. Check your email.");
      return;
    }

    if (response.status === 429 && payload?.retryAfterSec) {
      setRetryAfter(payload.retryAfterSec);
    }
    setStatus(payload?.error || payload?.detail || "Unable to send code.");
  };

  const verifyCode = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (needsName && !name.trim()) {
      setStatus("Please enter your name to finish signup.");
      return;
    }
    setStatus("Verifying...");

    const response = await clientFetch("/api/auth/verify-code", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        code,
        name: name.trim() || undefined,
      }),
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message =
        payload?.detail || payload?.error || "Invalid code. Please try again.";
      if (String(message).toLowerCase().includes("name")) {
        setNeedsName(true);
        setStatus("Please enter your name to finish signup.");
        return;
      }
      setStatus(message);
      return;
    }

    const user = payload?.user;
    if (!user) {
      setStatus("Unable to sign in.");
      return;
    }
    setAuthSession(user);
    window.location.href = "/";
  };

  return (
    <div className="glass w-full max-w-md space-y-4 rounded-[32px] border border-white/80 p-5 text-sm sm:p-6">
      <div className="space-y-2 text-center">
        <p className="text-xs uppercase tracking-[0.32em] text-stone-500">
          Secure sign in
        </p>
        <h1 className="text-3xl font-semibold text-stone-900">
          Welcome back
        </h1>
        <p className="text-sm text-stone-600">
          Use a one-time email code or Google.
        </p>
      </div>
      <div className="space-y-3">
        <label className="flex flex-col gap-2 text-sm text-stone-700">
          Email
          <input
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
              setName("");
              setCode("");
              setCodeSent(false);
              setNeedsName(false);
              setStatus(null);
            }}
            type="email"
            placeholder="you@example.com"
            className="w-full min-w-0 rounded-2xl border border-stone-200 bg-white/80 px-4 py-3 text-sm text-stone-800 outline-none focus:border-stone-400"
          />
        </label>
        <button
          type="button"
          onClick={requestCode}
          disabled={!email || Boolean(retryAfter)}
          className="w-full rounded-full border border-stone-200 bg-white/80 px-4 py-2 text-xs uppercase tracking-[0.3em] text-stone-600 disabled:opacity-50"
        >
          {retryAfter
            ? `Resend in ${retryAfter}s`
            : codeSent
            ? "Resend code"
            : "Send code"}
        </button>
      </div>
      {codeSent ? (
        <form onSubmit={verifyCode} className="min-w-0 space-y-3">
          {needsName ? (
            <label className="flex flex-col gap-2 text-sm text-stone-700">
              Full name
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                type="text"
                placeholder="Jane Doe"
                className="w-full min-w-0 rounded-2xl border border-stone-200 bg-white/80 px-4 py-3 text-sm text-stone-800 outline-none focus:border-stone-400"
              />
            </label>
          ) : null}
          <label className="flex flex-col gap-2 text-sm text-stone-700">
            Verification code
            <input
              value={code}
              onChange={(event) => setCode(event.target.value)}
              placeholder="6-digit code"
              className="w-full min-w-0 rounded-2xl border border-stone-200 bg-white/80 px-4 py-3 text-sm text-stone-800 outline-none focus:border-stone-400"
            />
          </label>
          <button
            type="submit"
            disabled={!email || !code || (needsName && !name.trim())}
            className="w-full rounded-full bg-[color:var(--brand)] px-4 py-3 text-xs uppercase tracking-[0.3em] text-white disabled:opacity-50"
          >
            Verify & sign in
          </button>
        </form>
      ) : null}
      {googleEnabled ? (
        <>
          <div className="flex items-center gap-2 text-xs uppercase tracking-[0.3em] text-stone-400">
            <div className="h-px flex-1 bg-stone-200" />
            or
            <div className="h-px flex-1 bg-stone-200" />
          </div>
          <button
            type="button"
            onClick={() => void requestGoogleSignIn()}
            disabled={!googleReady || googleBusy}
            className="inline-flex w-full items-center justify-center gap-2 rounded-full border border-stone-200 bg-white/80 px-4 py-3 text-xs uppercase tracking-[0.24em] text-stone-600 disabled:opacity-50"
          >
            <Image
              src="/google.webp"
              alt=""
              aria-hidden
              width={16}
              height={16}
              className="h-4 w-4 object-contain"
            />
            {googleBusy
              ? "Opening Google..."
              : googleReady
              ? "Continue with Google"
              : "Loading Google..."}
          </button>
          <p className="text-center text-xs text-stone-500">
            Sign in with Google in one step.
          </p>
        </>
      ) : null}
      {status ? (
        <p className="text-center text-xs uppercase tracking-[0.24em] text-stone-500">
          {status}
        </p>
      ) : null}
    </div>
  );
}


