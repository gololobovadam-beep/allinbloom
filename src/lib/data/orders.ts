import { apiFetch } from "@/lib/api-server";
import type { Order, OrderStripeSession, PaymentEvent } from "@/lib/api-types";

export type AdminOrdersScope = "active" | "deleted";

export async function getAdminOrders(): Promise<Order[]> {
  const response = await apiFetch("/api/admin/orders", {}, true);
  if (!response.ok) return [];
  return response.json() as Promise<Order[]>;
}

export async function getAdminOrdersByDay(
  dayKey: string,
  scope: AdminOrdersScope = "active"
): Promise<Order[]> {
  const response = await apiFetch(
    `/api/admin/orders/by-day?date=${dayKey}&scope=${scope}`,
    {},
    true
  );
  if (!response.ok) return [];
  const data = (await response.json()) as { orders?: Order[] };
  return data.orders || [];
}

export async function getAdminOrdersByWeek(
  weekStartKey: string,
  scope: AdminOrdersScope = "active"
): Promise<Order[]> {
  const response = await apiFetch(
    `/api/admin/orders/by-week?startDate=${weekStartKey}&scope=${scope}`,
    {},
    true
  );
  if (!response.ok) return [];
  const data = (await response.json()) as { orders?: Order[] };
  return data.orders || [];
}

export async function getOrderById(id: string): Promise<Order | null> {
  const response = await apiFetch(`/api/orders/${id}`, {}, true);
  if (!response.ok) return null;
  return response.json() as Promise<Order>;
}

export async function getOrdersByEmail(email: string): Promise<Order[]> {
  if (!email) return [];
  const response = await apiFetch("/api/orders/me", {}, true);
  if (!response.ok) return [];
  return response.json() as Promise<Order[]>;
}

export async function cancelCheckoutOrder(
  orderId?: string | null,
  paypalOrderId?: string | null
): Promise<string | null> {
  const normalizedOrderId = orderId?.trim() || "";
  const normalizedPaypalOrderId = paypalOrderId?.trim() || "";
  if (!normalizedOrderId && !normalizedPaypalOrderId) return null;
  const response = await apiFetch(
    "/api/checkout/cancel",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        orderId: normalizedOrderId || undefined,
        paypalOrderId: normalizedPaypalOrderId || undefined,
      }),
    },
    false
  );
  if (!response.ok) return null;
  const data = (await response.json().catch(() => ({}))) as { status?: string };
  return data.status || null;
}

export async function getOrderStripeSession(
  orderId: string
): Promise<OrderStripeSession | null> {
  const response = await apiFetch(`/api/admin/orders/${orderId}/stripe-session`, {}, true);
  if (!response.ok) return null;
  return response.json() as Promise<OrderStripeSession>;
}

export async function getOrderPaymentEvents(
  orderId: string
): Promise<PaymentEvent[]> {
  const response = await apiFetch(
    `/api/admin/orders/${orderId}/payment-events`,
    {},
    true
  );
  if (!response.ok) return [];
  return response.json() as Promise<PaymentEvent[]>;
}

export async function countOrdersByEmail(email: string) {
  const orders = await getOrdersByEmail(email);
  return orders.filter((order) => order.status === "PAID").length;
}
