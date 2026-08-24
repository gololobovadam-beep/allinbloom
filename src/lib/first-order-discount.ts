import type { Order } from "@/lib/api-types";

// A completed payment remains a prior order even if it was later refunded,
// disputed, charged back, or reversed. Otherwise a refund could reopen a
// one-time promotion indefinitely.
const BLOCKING_STATUSES = new Set([
  "PENDING",
  "PAID",
  "PARTIALLY_REFUNDED",
  "REFUNDED",
  "DISPUTED",
  "CHARGEBACK",
  "REVERSED",
]);

export const hasBlockingOrderHistory = (
  orders: Pick<Order, "status">[]
) =>
  orders.some((order) => BLOCKING_STATUSES.has(order.status));

export const countPaidOrders = (orders: Pick<Order, "status">[]) =>
  orders.filter((order) => order.status === "PAID").length;

export const isFirstOrderEligibleForKnownHistory = (
  orders: Pick<Order, "status">[]
) =>
  !hasBlockingOrderHistory(orders);
