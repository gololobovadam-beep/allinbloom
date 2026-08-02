import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getOrderById,
  getOrderPaymentEvents,
  getOrderStripeSession,
} from "@/lib/data/orders";
import {
  formatDateTime,
  formatLabel,
  formatMoney,
  formatOrderStatus,
} from "@/lib/format";
import { sanitizeOrderItemDetails } from "@/lib/order-details";

const FAILURE_STAGE_LABELS: Record<string, string> = {
  checkout_timeout: "Pending payment timed out",
  checkout_setup_timeout: "Checkout setup timed out",
  stripe_checkout_create: "Stripe checkout creation",
  stripe_checkout_redirect: "Stripe redirect creation",
  stripe_checkout: "Stripe checkout",
  stripe_payment_intent: "Stripe payment intent",
  paypal_order_create: "PayPal order creation",
  paypal_order: "PayPal order",
  paypal_capture: "PayPal capture",
};

const PAYMENT_EVENT_LABELS: Record<string, string> = {
  checkout_order_created: "Order created",
  stripe_checkout_create_started: "Stripe session creation started",
  stripe_checkout_session_created: "Stripe session created",
  stripe_checkout_create_failed: "Stripe session creation failed",
  stripe_checkout_redirect_url_missing: "Stripe redirect URL missing",
  paypal_order_created: "PayPal order created",
  paypal_order_create_failed: "PayPal order creation failed",
  browser_redirect_started: "Browser redirect started",
  browser_success_returned: "Browser returned to success page",
  browser_status_check_started: "Browser started status check",
  checkout_status_requested: "Status check requested",
  checkout_status_resolved: "Status check resolved",
  checkout_cancel_returned: "Cancel return received",
  checkout_cancel_observed_paid: "Cancel flow found paid order",
  checkout_cancel_observed_closed: "Cancel flow found closed order",
  checkout_cancel_resolved_paid: "Cancel flow resolved paid",
  checkout_cancel_resolved_failed: "Cancel flow resolved failed",
  checkout_marked_canceled: "Checkout marked canceled",
  checkout_setup_timed_out: "Checkout setup timed out",
  stripe_webhook_received: "Stripe webhook received",
  stripe_payment_marked_paid: "Stripe marked paid",
  stripe_payment_paid_webhook_no_status_change: "Stripe paid webhook had no status change",
  stripe_checkout_marked_failed: "Stripe checkout marked failed",
  stripe_payment_intent_marked_failed: "Stripe PaymentIntent marked failed",
  stripe_failure_webhook_ignored: "Stripe failure webhook ignored",
  stripe_payment_intent_failure_ignored: "Stripe PaymentIntent failure ignored",
  stripe_checkout_webhook_unresolved: "Stripe webhook unresolved",
  stripe_payment_data_mismatch: "Stripe payment data mismatch",
  stripe_sync_marked_paid: "Stripe sync marked paid",
  stripe_sync_marked_failed: "Stripe sync marked failed",
  stripe_session_expired_by_cancel: "Stripe session expired by cancel",
  stripe_session_expire_failed: "Stripe session expire failed",
  stripe_session_fetch_failed_during_cancel: "Stripe session fetch failed during cancel",
  paypal_sync_marked_paid: "PayPal sync marked paid",
  paypal_sync_marked_failed: "PayPal sync marked failed",
  paypal_order_voided_by_cancel: "PayPal order voided by cancel",
  paypal_order_void_failed: "PayPal order void failed",
  paypal_order_fetch_failed_during_cancel: "PayPal order fetch failed during cancel",
};

const PAYMENT_SOURCE_LABELS: Record<string, string> = {
  browser: "Browser",
  server: "Server",
  server_sync: "Server sync",
  stripe_webhook: "Stripe webhook",
};

const formatStripeTimestamp = (value?: number | null) =>
  value ? formatDateTime(new Date(value * 1000)) : "";

const formatContextValue = (value: unknown) => {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "number" || typeof value === "string") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
};

const formatPaymentEventContext = (context: Record<string, unknown> | null) => {
  if (!context) return [];
  return Object.entries(context)
    .map(([key, value]) => {
      const formatted = formatContextValue(value);
      return formatted ? `${formatLabel(key)}: ${formatted}` : "";
    })
    .filter(Boolean);
};

const formatDeliveryDateTime = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) return "";
  try {
    const parsed = JSON.parse(trimmed) as {
      date?: unknown;
      timeWindow?: unknown;
      idealTime?: unknown;
    };
    if (typeof parsed.date === "string" && typeof parsed.timeWindow === "string") {
      const [year, month, day] = parsed.date
        .split("-")
        .map((part) => Number(part));
      const date = new Date(year, month - 1, day);
      const formattedDate =
        year && month && day && !Number.isNaN(date.getTime())
          ? new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(date)
          : parsed.date;
      const parts = [`Date: ${formattedDate}`, `Window: ${parsed.timeWindow}`];
      if (typeof parsed.idealTime === "string" && parsed.idealTime.trim()) {
        const [hour = 0, minute = 0] = parsed.idealTime
          .split(":")
          .map((part) => Number(part));
        const time = new Date(2000, 0, 1, hour, minute);
        const formattedTime = Number.isNaN(time.getTime())
          ? parsed.idealTime
          : new Intl.DateTimeFormat("en-US", { timeStyle: "short" }).format(time);
        parts.push(`Ideal delivery time: ${formattedTime}`);
      }
      return parts.join(" | ");
    }
  } catch {
    // Older orders used a plain datetime-local string.
  }
  const [datePart, timePart = ""] = trimmed.split("T");
  const [year, month, day] = datePart.split("-").map((part) => Number(part));
  const [hour = 0, minute = 0] = timePart
    .split(":")
    .map((part) => Number(part));
  if (!year || !month || !day) return trimmed;
  const date = new Date(year, month - 1, day, hour, minute);
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
};

export default async function AdminOrderDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [order, stripeSession, paymentEvents] = await Promise.all([
    getOrderById(id),
    getOrderStripeSession(id),
    getOrderPaymentEvents(id),
  ]);

  if (!order) {
    notFound();
  }

  const verifiedDeliveryAddress = stripeSession?.deliveryAddress?.trim() || "";
  const fallbackDeliveryAddress = order.deliveryAddress?.trim() || "";
  const line1 = order.deliveryAddressLine1?.trim() || "";
  const line2 = order.deliveryAddressLine2?.trim() || "";
  const floor = order.deliveryFloor?.trim() || "";
  const floorLabel = floor
    ? floor.toLowerCase().startsWith("floor")
      ? floor
      : `Floor ${floor}`
    : "";
  const city = order.deliveryCity?.trim() || "";
  const state = order.deliveryState?.trim() || "";
  const postal = order.deliveryPostalCode?.trim() || "";
  const country = order.deliveryCountry?.trim() || "";
  const cityStateZip = [city, [state, postal].filter(Boolean).join(" ")].filter(Boolean).join(", ");
  const structuredLines = [line1, line2, floorLabel, cityStateZip, country].filter(
    Boolean
  );
  const deliveryAddress = structuredLines.length
    ? structuredLines.join(", ")
    : verifiedDeliveryAddress || fallbackDeliveryAddress;
  const deliveryMiles = stripeSession?.deliveryMiles || order.deliveryMiles;
  const deliveryFeeCents =
    stripeSession?.deliveryFeeCents ?? order.deliveryFeeCents ?? null;
  const deliveryDateTime =
    stripeSession?.deliveryDateTime?.trim() || order.deliveryDateTime?.trim() || "";
  const formattedDeliveryDateTime = formatDeliveryDateTime(deliveryDateTime);
  const shipping = stripeSession?.shipping;
  const address = shipping?.address;
  const hasStripeSession = Boolean(
    stripeSession?.paymentStatus ||
      stripeSession?.status ||
      shipping ||
      verifiedDeliveryAddress
  );
  const hasPayPalOrder = Boolean(order.paypalOrderId);
  const paymentProvider = hasPayPalOrder
    ? "PayPal"
    : order.stripeSessionId
    ? "Stripe"
    : "Unknown";
  const failureStage = order.paymentFailureStage?.trim() || "";
  const failureStageLabel = FAILURE_STAGE_LABELS[failureStage] || failureStage;
  const storedFailureMessage = order.paymentFailureMessage?.trim() || "";
  const storedFailureCode = order.paymentFailureCode?.trim() || "";
  const storedFailureDetails = order.paymentFailureDetails?.trim() || "";
  const orderStatusLabel =
    order.status === "FAILED" && storedFailureCode === "session_expired"
      ? "Checkout expired"
      : formatOrderStatus(order.status);
  const liveStripeErrorMessage = stripeSession?.lastPaymentErrorMessage?.trim() || "";
  const liveStripeErrorCode = stripeSession?.lastPaymentErrorCode?.trim() || "";
  const liveStripeDeclineCode =
    stripeSession?.lastPaymentErrorDeclineCode?.trim() || "";
  const liveStripeIntentId = stripeSession?.paymentIntentId?.trim() || "";
  const liveStripeIntentStatus = stripeSession?.paymentIntentStatus?.trim() || "";
  const stripeCreatedAt = formatStripeTimestamp(stripeSession?.created);
  const stripeExpiresAt = formatStripeTimestamp(stripeSession?.expiresAt);
  const liveChargeId = stripeSession?.latestChargeId?.trim() || "";
  const liveChargeStatus = stripeSession?.latestChargeStatus?.trim() || "";
  const liveChargeFailureCode = stripeSession?.chargeFailureCode?.trim() || "";
  const liveChargeFailureMessage =
    stripeSession?.chargeFailureMessage?.trim() || "";
  const liveOutcomeType = stripeSession?.chargeOutcomeType?.trim() || "";
  const liveOutcomeReason = stripeSession?.chargeOutcomeReason?.trim() || "";
  const liveOutcomeNetwork =
    stripeSession?.chargeOutcomeNetworkStatus?.trim() || "";
  const liveOutcomeSellerMessage =
    stripeSession?.chargeOutcomeSellerMessage?.trim() || "";
  const cardSummary = [
    stripeSession?.cardBrand?.trim(),
    stripeSession?.cardFunding?.trim(),
    stripeSession?.cardCountry?.trim(),
  ]
    .filter(Boolean)
    .join(" / ");
  const postalCheck =
    stripeSession?.cardCheckAddressPostalCode?.trim() || "";
  const cvcCheck = stripeSession?.cardCheckCvc?.trim() || "";
  const hasPaymentDiagnostics = Boolean(
    storedFailureMessage ||
      storedFailureCode ||
      storedFailureDetails ||
      failureStage ||
      order.paymentFailedAt ||
      liveStripeErrorMessage ||
      liveStripeErrorCode ||
      liveStripeDeclineCode ||
      liveStripeIntentId ||
      liveStripeIntentStatus ||
      stripeCreatedAt ||
      stripeExpiresAt ||
      liveChargeId ||
      liveChargeStatus ||
      liveChargeFailureCode ||
      liveChargeFailureMessage ||
      liveOutcomeType ||
      liveOutcomeReason ||
      liveOutcomeNetwork ||
      liveOutcomeSellerMessage ||
      cardSummary ||
      postalCheck ||
      cvcCheck
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.32em] text-stone-500">
            Order details
          </p>
          <h1 className="text-2xl font-semibold text-stone-900 sm:text-3xl">
            Order {order.id.slice(0, 8)}
          </h1>
        </div>
        <Link
          href="/admin/orders"
          className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-full border border-stone-300 bg-white/80 px-4 text-center text-xs uppercase tracking-[0.3em] text-stone-600 sm:w-auto"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="h-4 w-4"
          >
            <path
              fillRule="evenodd"
              d="M12.78 4.22a.75.75 0 0 1 0 1.06L8.06 10l4.72 4.72a.75.75 0 1 1-1.06 1.06l-5.25-5.25a.75.75 0 0 1 0-1.06l5.25-5.25a.75.75 0 0 1 1.06 0Z"
              clipRule="evenodd"
            />
          </svg>
          Back to orders
        </Link>
      </div>

      <div className="space-y-6">
        <div className="glass rounded-[28px] border border-white/80 p-4 sm:p-6">
          <h2 className="text-lg font-semibold text-stone-900">
            Items in order
          </h2>
          <div className="mt-4 space-y-2 text-sm text-stone-600">
            {order.items.map((item) => {
              const details = sanitizeOrderItemDetails(item.details);
              return (
                <div key={item.id} className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="break-words">
                      {item.quantity} x {item.name}
                    </p>
                    {details ? (
                      <p className="mt-1 text-xs text-stone-500">
                        {details}
                      </p>
                    ) : null}
                  </div>
                  <span className="shrink-0">{formatMoney(item.priceCents)}</span>
                </div>
              );
            })}
          </div>
          <div className="mt-4 flex justify-between text-sm font-semibold text-stone-900">
            <span>Total</span>
            <span>{formatMoney(order.totalCents)}</span>
          </div>
        </div>

        <div className="glass rounded-[28px] border border-white/80 p-4 text-sm text-stone-600 sm:p-6">
            <h2 className="text-lg font-semibold text-stone-900">
              Order summary
            </h2>
            <div className="mt-3 space-y-2">
              <p>Status: {orderStatusLabel}</p>
              <p>Created: {formatDateTime(order.createdAt)}</p>
              {order.email ? <p className="break-all">Email: {order.email}</p> : null}
              {order.phone ? <p>Phone: {order.phone}</p> : null}
              <p>Payment method: {paymentProvider}</p>
              {hasStripeSession ? (
                <p>
                  Stripe payment: {stripeSession?.paymentStatus || "unknown"} (
                  {stripeSession?.status || "unknown"})
                </p>
              ) : hasPayPalOrder ? (
                <p>PayPal order: {order.paypalOrderId}</p>
              ) : (
                <p>Stripe session: not linked yet.</p>
              )}
              {order.paypalCaptureId ? (
                <p>PayPal capture: {order.paypalCaptureId}</p>
              ) : null}
            </div>
        </div>

        {hasPaymentDiagnostics ? (
          <details className="glass rounded-[28px] border border-white/80 p-4 text-sm text-stone-600 sm:p-6">
              <summary className="cursor-pointer list-none text-lg font-semibold text-stone-900 [&::-webkit-details-marker]:hidden">
                <span className="flex items-center justify-between gap-3">
                  Technical payment diagnostics
                  <span className="text-xs font-normal uppercase tracking-[0.2em] text-stone-500">
                    Show details
                  </span>
                </span>
              </summary>
              <div className="mt-3 space-y-2">
                {storedFailureMessage ? (
                  <p className="text-stone-800">
                    Failure reason: {storedFailureMessage}
                  </p>
                ) : null}
                {failureStageLabel ? <p>Failure stage: {failureStageLabel}</p> : null}
                {storedFailureCode ? <p>Stored failure code: {storedFailureCode}</p> : null}
                {order.paymentFailedAt ? (
                  <p>Recorded: {formatDateTime(order.paymentFailedAt)}</p>
                ) : null}
                {liveStripeErrorMessage ? (
                  <p className="text-stone-800">
                    Stripe live error: {liveStripeErrorMessage}
                  </p>
                ) : null}
                {liveStripeErrorCode ? (
                  <p>Stripe error code: {liveStripeErrorCode}</p>
                ) : null}
                {liveStripeDeclineCode ? (
                  <p>Stripe decline code: {liveStripeDeclineCode}</p>
                ) : null}
                {liveStripeIntentId ? (
                  <p>Stripe PaymentIntent: {liveStripeIntentId}</p>
                ) : null}
                {liveStripeIntentStatus ? (
                  <p>Stripe intent status: {liveStripeIntentStatus}</p>
                ) : null}
                {stripeCreatedAt ? (
                  <p>Stripe session created: {stripeCreatedAt}</p>
                ) : null}
                {stripeExpiresAt ? (
                  <p>Stripe session expires: {stripeExpiresAt}</p>
                ) : null}
                {liveChargeId ? <p>Stripe charge: {liveChargeId}</p> : null}
                {liveChargeStatus ? (
                  <p>Stripe charge status: {liveChargeStatus}</p>
                ) : null}
                {liveChargeFailureCode ? (
                  <p>Charge failure code: {liveChargeFailureCode}</p>
                ) : null}
                {liveChargeFailureMessage ? (
                  <p className="text-stone-800">
                    Charge failure message: {liveChargeFailureMessage}
                  </p>
                ) : null}
                {liveOutcomeType ? <p>Outcome type: {liveOutcomeType}</p> : null}
                {liveOutcomeReason ? (
                  <p>Outcome reason: {liveOutcomeReason}</p>
                ) : null}
                {liveOutcomeNetwork ? (
                  <p>Network status: {liveOutcomeNetwork}</p>
                ) : null}
                {liveOutcomeSellerMessage ? (
                  <p className="text-stone-800">
                    Seller message: {liveOutcomeSellerMessage}
                  </p>
                ) : null}
                {cardSummary ? <p>Card: {cardSummary}</p> : null}
                {postalCheck ? <p>ZIP check: {postalCheck}</p> : null}
                {cvcCheck ? <p>CVC check: {cvcCheck}</p> : null}
                {storedFailureDetails ? (
                  <div className="pt-2">
                    <p className="text-xs uppercase tracking-[0.24em] text-stone-500">
                      Technical details
                    </p>
                    <p className="break-words whitespace-pre-line">
                      {storedFailureDetails}
                    </p>
                  </div>
                ) : null}
              </div>
          </details>
        ) : null}

        <div className="glass rounded-[28px] border border-white/80 p-4 text-sm text-stone-600 sm:p-6">
            <h2 className="text-lg font-semibold text-stone-900">
              Delivery address
            </h2>
            <div className="mt-3 space-y-2">
              {deliveryAddress ? (
                <>
                  {structuredLines.length ? (
                    structuredLines.map((line, index) => (
                      <p key={`${line}-${index}`} className="break-words">
                        {line}
                      </p>
                    ))
                  ) : (
                    <p className="break-words">{deliveryAddress}</p>
                  )}
                  {deliveryMiles ? <p>Distance: {deliveryMiles} miles</p> : null}
                  {deliveryFeeCents !== null ? (
                    <p>
                      Delivery fee:{" "}
                      {deliveryFeeCents > 0 ? formatMoney(deliveryFeeCents) : "Free"}
                    </p>
                  ) : null}
                  {formattedDeliveryDateTime ? (
                    <p>Delivery date/time: {formattedDeliveryDateTime}</p>
                  ) : null}
                  {order.orderComment ? (
                    <div className="pt-2">
                      <p className="text-xs uppercase tracking-[0.24em] text-stone-500">
                        Order comment
                      </p>
                      <p className="break-words">{order.orderComment}</p>
                    </div>
                  ) : null}
                </>
              ) : shipping ? (
                <>
                  <p>{shipping.name}</p>
                  {shipping.phone ? <p>{shipping.phone}</p> : null}
                  {address ? (
                    <>
                      <p>{address.line1}</p>
                      {address.line2 ? <p>{address.line2}</p> : null}
                      <p>
                        {address.city}, {address.state} {address.postalCode}
                      </p>
                      <p>{address.country}</p>
                    </>
                  ) : null}
                </>
              ) : (
                <p>
                  Address will appear after checkout is created.
                </p>
              )}
            </div>
        </div>

        {paymentEvents.length ? (
          <details className="glass rounded-[28px] border border-white/80 p-4 text-sm text-stone-600 sm:p-6">
            <summary className="cursor-pointer list-none text-lg font-semibold text-stone-900 [&::-webkit-details-marker]:hidden">
              <span className="flex items-center justify-between gap-3">
                Technical payment timeline
                <span className="text-xs font-normal uppercase tracking-[0.2em] text-stone-500">
                  Show details
                </span>
              </span>
            </summary>
            <div className="mt-4 space-y-4">
              {paymentEvents.map((event) => {
                const contextLines = formatPaymentEventContext(event.context);
                const eventLabel =
                  PAYMENT_EVENT_LABELS[event.event] || formatLabel(event.event);
                const sourceLabel =
                  PAYMENT_SOURCE_LABELS[event.source] || formatLabel(event.source);
                return (
                  <div
                    key={event.id}
                    className="border-t border-stone-200 pt-3 first:border-t-0 first:pt-0"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p className="font-medium text-stone-900">
                          {eventLabel}
                        </p>
                        <p className="text-xs uppercase tracking-[0.24em] text-stone-500">
                          {sourceLabel} - {formatLabel(event.provider)}
                        </p>
                      </div>
                      <p className="text-xs text-stone-500">
                        {formatDateTime(event.createdAt)}
                      </p>
                    </div>
                    {event.message ? (
                      <p className="mt-2 text-stone-700">{event.message}</p>
                    ) : null}
                    {event.stripeEventId ? (
                      <p className="mt-1 break-all text-xs">
                        Stripe event: {event.stripeEventId}
                      </p>
                    ) : null}
                    {event.stripeSessionId ? (
                      <p className="mt-1 break-all text-xs">
                        Stripe session: {event.stripeSessionId}
                      </p>
                    ) : null}
                    {event.paymentIntentId ? (
                      <p className="mt-1 break-all text-xs">
                        PaymentIntent: {event.paymentIntentId}
                      </p>
                    ) : null}
                    {contextLines.length ? (
                      <div className="mt-2 space-y-1 text-xs text-stone-500">
                        {contextLines.map((line) => (
                          <p key={`${event.id}-${line}`} className="break-words">
                            {line}
                          </p>
                        ))}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </details>
        ) : null}
      </div>
    </div>
  );
}
