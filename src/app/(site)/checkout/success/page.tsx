"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { clearCartStorage, clearCheckoutFormStorage, useCart } from "@/lib/cart";
import { clientFetch } from "@/lib/api-client";

const PAYPAL_RETRY_DELAY_MS = 3000;
const PAYPAL_MAX_ATTEMPTS = 6;

const recordCheckoutEvent = async ({
  orderId,
  event,
  provider,
  context,
}: {
  orderId: string;
  event: string;
  provider: "stripe" | "paypal";
  context?: Record<string, unknown>;
}) => {
  try {
    await clientFetch(
      "/api/checkout/event",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          orderId,
          event,
          provider,
          context,
        }),
        keepalive: true,
      },
      false
    );
  } catch {
    // Checkout telemetry should never change the customer-facing result.
  }
};

export default function CheckoutSuccessPage() {
  return (
    <Suspense fallback={<CheckoutSuccessFallback />}>
      <CheckoutSuccessContent />
    </Suspense>
  );
}

function CheckoutSuccessContent() {
  const { clear } = useCart();
  const searchParams = useSearchParams();
  const paypalToken = searchParams.get("token");
  const checkoutOrderId = searchParams.get("orderId");
  const isPaypalReturn =
    searchParams.get("provider") === "paypal" || Boolean(paypalToken);
  const provider = isPaypalReturn ? "paypal" : "stripe";
  const hasCheckoutToken = Boolean(checkoutOrderId);
  const [status, setStatus] = useState<"loading" | "success" | "error" | "pending">(
    isPaypalReturn ? (paypalToken ? "loading" : "error") : hasCheckoutToken ? "loading" : "pending"
  );
  const [error, setError] = useState<string | null>(
    isPaypalReturn
      ? paypalToken
        ? null
        : "Missing PayPal approval token."
      : hasCheckoutToken
      ? null
      : "Missing checkout confirmation token. Open checkout again from cart."
  );

  useEffect(() => {
    if (!checkoutOrderId) return;

    void recordCheckoutEvent({
      orderId: checkoutOrderId,
      event: "browser_success_returned",
      provider,
      context: {
        hasPaypalToken: Boolean(paypalToken),
      },
    });
  }, [checkoutOrderId, paypalToken, provider]);

  useEffect(() => {
    if (isPaypalReturn || !checkoutOrderId) return;

    let isMounted = true;
    const verifyOrderStatus = async () => {
      setStatus("loading");
      setError(null);
      void recordCheckoutEvent({
        orderId: checkoutOrderId,
        event: "browser_status_check_started",
        provider: "stripe",
      });
      const response = await clientFetch(
        "/api/checkout/status",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            orderId: checkoutOrderId,
          }),
        },
        false
      );
      const payload = (await response.json().catch(() => ({}))) as {
        status?: string;
        detail?: string;
      };

      if (!isMounted) return;

      if (!response.ok) {
        setStatus("pending");
        setError(payload?.detail || "Payment confirmation is still in progress.");
        return;
      }

      const orderStatus = (payload?.status || "").toUpperCase();
      if (orderStatus === "PAID") {
        setStatus("success");
        clearCartStorage();
        clearCheckoutFormStorage();
        clear();
        return;
      }
      if (orderStatus === "FAILED" || orderStatus === "CANCELED") {
        setStatus("error");
        setError("Payment was not completed. Return to cart and try again.");
        return;
      }

      setStatus("pending");
      setError(null);
    };

    void verifyOrderStatus();
    return () => {
      isMounted = false;
    };
  }, [checkoutOrderId, clear, isPaypalReturn]);

  useEffect(() => {
    if (!isPaypalReturn || !paypalToken) return;

    let isMounted = true;
    let attempts = 0;
    let timeout: ReturnType<typeof setTimeout> | null = null;

    const capture = async () => {
      attempts += 1;
      if (attempts === 1) {
        setStatus("loading");
        setError(null);
      }
      const response = await clientFetch(
        "/api/paypal/capture",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            orderId: paypalToken,
            checkoutOrderId: checkoutOrderId || undefined,
          }),
        },
        true
      );
      const payload = (await response.json().catch(() => ({}))) as {
        status?: string;
        detail?: string;
      };

      if (!isMounted) return;

      if (!response.ok) {
        setStatus("error");
        setError(payload?.detail || "Unable to confirm PayPal payment.");
        return;
      }

      const paymentStatus = (payload?.status || "").toUpperCase();
      if (paymentStatus === "PAID") {
        setStatus("success");
        clearCartStorage();
        clearCheckoutFormStorage();
        clear();
        return;
      }
      if (paymentStatus === "FAILED" || paymentStatus === "CANCELED") {
        setStatus("error");
        setError("PayPal payment was not completed.");
        return;
      }

      if (attempts >= PAYPAL_MAX_ATTEMPTS) {
        setStatus("pending");
        setError(
          "PayPal payment is still pending. Please refresh this page in a moment."
        );
        return;
      }

      setStatus("pending");
      setError("PayPal payment is still pending. Checking again shortly.");
      timeout = setTimeout(() => {
        void capture();
      }, PAYPAL_RETRY_DELAY_MS);
    };

    void capture();
    return () => {
      isMounted = false;
      if (timeout) {
        clearTimeout(timeout);
      }
    };
  }, [checkoutOrderId, clear, isPaypalReturn, paypalToken]);

  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-4 text-center sm:gap-6">
      <div className="rounded-full bg-white/80 px-5 py-2 text-xs uppercase tracking-[0.32em] text-stone-500">
        {status === "loading"
          ? "Confirming payment"
          : status === "pending"
          ? "Payment processing"
          : status === "error"
          ? "Payment not confirmed"
          : "Payment confirmed"}
      </div>
      <h1 className="text-4xl font-semibold text-stone-900 sm:text-5xl">
        {status === "error"
          ? "We need a quick check"
          : status === "success"
          ? "Your order is in bloom"
          : "We're confirming your order"}
      </h1>
      <p className="text-sm leading-relaxed text-stone-600">
        {status === "loading"
          ? "Hang tight while we confirm your payment."
          : status === "pending"
          ? error ||
            "Payment confirmation is still processing. Refresh this page shortly."
          : status === "error"
          ? error ||
            "We could not confirm your payment yet. Please return to the cart and try again."
          : "We have received your order and our florists are preparing your bouquet now. You will receive a confirmation email with delivery details shortly. If you don't see it, please check your spam folder."}
      </p>
      <Link
        href={status === "success" ? "/catalog" : "/cart"}
        className="rounded-full bg-[color:var(--brand)] px-6 py-3 text-xs uppercase tracking-[0.3em] text-white transition hover:bg-[color:var(--brand-dark)]"
      >
        {status === "success" ? "Continue shopping" : "Return to cart"}
      </Link>
    </div>
  );
}

function CheckoutSuccessFallback() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-4 text-center sm:gap-6">
      <div className="rounded-full bg-white/80 px-5 py-2 text-xs uppercase tracking-[0.32em] text-stone-500">
        Finalizing payment
      </div>
      <h1 className="text-4xl font-semibold text-stone-900 sm:text-5xl">
        Checking your order
      </h1>
      <p className="text-sm leading-relaxed text-stone-600">
        Please wait while we load your payment confirmation.
      </p>
    </div>
  );
}
