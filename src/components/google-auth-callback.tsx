"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { setAuthSession } from "@/lib/auth-client";
import { clientFetch } from "@/lib/api-client";
import { getGoogleRedirectUri } from "@/lib/google-auth";

export default function GoogleAuthCallback() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState("Completing Google sign-in...");
  const [exchangeFailed, setExchangeFailed] = useState(false);
  const queryError = searchParams.get("error");
  const code = searchParams.get("code");
  const state = searchParams.get("state");
  const immediateFailureMessage = queryError
    ? "Google sign-in was canceled."
    : code
    ? state
      ? null
      : "Google sign-in state is missing."
    : "Google sign-in code is missing.";

  useEffect(() => {
    if (!code || !state || immediateFailureMessage) {
      return;
    }

    let canceled = false;
    const complete = async () => {
      const redirectUri = getGoogleRedirectUri();
      const response = await clientFetch("/api/auth/google/code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, redirectUri, state }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (canceled) return;
        setExchangeFailed(true);
        setStatus(payload?.detail || "Unable to sign in with Google.");
        return;
      }

      const user = payload?.user;
      if (!user) {
        if (canceled) return;
        setExchangeFailed(true);
        setStatus("Unable to sign in with Google.");
        return;
      }

      setAuthSession(user);
      window.location.replace("/");
    };

    void complete();
    return () => {
      canceled = true;
    };
  }, [code, immediateFailureMessage, state]);

  const failed = Boolean(immediateFailureMessage) || exchangeFailed;
  const displayStatus = immediateFailureMessage || status;

  return (
    <div className="glass w-full max-w-md rounded-[32px] border border-white/80 p-5 text-center text-sm sm:p-6">
      <p className="text-xs uppercase tracking-[0.32em] text-stone-500">
        Google sign in
      </p>
      <p className="mt-3 text-sm text-stone-700">{displayStatus}</p>
      {failed ? (
        <Link
          href="/auth"
          className="mt-4 inline-flex h-11 items-center justify-center rounded-full border border-stone-200 bg-white/80 px-4 text-xs uppercase tracking-[0.24em] text-stone-600"
        >
          Back to sign in
        </Link>
      ) : null}
    </div>
  );
}


