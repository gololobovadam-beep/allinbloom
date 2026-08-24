"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { formatDateTime, formatMoney, formatOrderStatus } from "@/lib/format";
import { ADMIN_ORDERS_BADGE_EVENT } from "@/lib/admin-orders";
import { clientFetch } from "@/lib/api-client";
import { sanitizeOrderItemDetails } from "@/lib/order-details";
import type { Order } from "@/lib/api-types";

type AdminOrderRowProps = {
  order: Order;
  onRemoved: (orderId: string) => void;
  mode?: "active" | "deleted";
};

const orderStatusBadgeClass = (status: Order["status"]) => {
  switch (status) {
    case "PAID":
      return "border-emerald-200 bg-emerald-100 text-emerald-700";
    case "PENDING":
      return "border-amber-200 bg-amber-100 text-amber-700";
    case "FAILED":
      return "border-rose-200 bg-rose-100 text-rose-700";
    case "CANCELED":
      return "border-stone-300 bg-stone-200 text-stone-700";
    case "PARTIALLY_REFUNDED":
    case "REFUNDED":
      return "border-sky-200 bg-sky-100 text-sky-700";
    case "DISPUTED":
    case "CHARGEBACK":
    case "REVERSED":
      return "border-violet-200 bg-violet-100 text-violet-700";
    default:
      return "border-stone-200 bg-white/80 text-stone-600";
  }
};

const orderMetaBadgeClass =
  "inline-flex h-8 items-center justify-center rounded-full border px-3 text-[10px] uppercase tracking-[0.24em] whitespace-nowrap";

export default function AdminOrderRow({
  order,
  onRemoved,
  mode = "active",
}: AdminOrderRowProps) {
  const statusLabel = formatOrderStatus(order.status);
  const isDeletedMode = mode === "deleted";
  const [isRead, setIsRead] = useState(order.isRead ?? false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const isBusy = isLoading || isDeleting || isRestoring;

  const storeScrollPosition = () => {
    try {
      sessionStorage.setItem(
        `admin-orders-scroll:${mode}`,
        JSON.stringify({ y: window.scrollY, ts: Date.now() })
      );
    } catch {
      // Ignore storage errors (e.g., disabled cookies).
    }
  };

  useEffect(() => {
    if (!isMenuOpen) return;

    const closeOnOutsideClick = (event: MouseEvent) => {
      if (
        menuRef.current &&
        event.target instanceof Node &&
        !menuRef.current.contains(event.target)
      ) {
        setIsMenuOpen(false);
      }
    };

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsMenuOpen(false);
      }
    };

    window.addEventListener("mousedown", closeOnOutsideClick);
    window.addEventListener("keydown", closeOnEscape);

    return () => {
      window.removeEventListener("mousedown", closeOnOutsideClick);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [isMenuOpen]);

  const toggleRead = async () => {
    if (isBusy) return;
    setIsLoading(true);
    try {
      const response = await clientFetch(
        `/api/admin/orders/${order.id}/toggle-read`,
        {
          method: "PATCH",
        },
        true
      );
      if (!response.ok) {
        return;
      }
      const data = (await response.json()) as { isRead?: boolean };
      setIsRead(Boolean(data?.isRead));
      window.dispatchEvent(new Event(ADMIN_ORDERS_BADGE_EVENT));
    } finally {
      setIsLoading(false);
    }
  };

  const softDelete = async () => {
    if (isBusy) return;
    setIsMenuOpen(false);
    const confirmed = window.confirm(
      "Soft delete this order? It will be hidden from admin lists."
    );
    if (!confirmed) return;

    setIsDeleting(true);
    try {
      const response = await clientFetch(
        `/api/admin/orders/${order.id}/soft-delete`,
        {
          method: "PATCH",
        },
        true
      );
      if (!response.ok) {
        return;
      }
      onRemoved(order.id);
      window.dispatchEvent(new Event(ADMIN_ORDERS_BADGE_EVENT));
    } finally {
      setIsDeleting(false);
    }
  };

  const restoreOrder = async () => {
    if (isBusy) return;
    setIsMenuOpen(false);
    const confirmed = window.confirm(
      "Restore this order to active orders?"
    );
    if (!confirmed) return;

    setIsRestoring(true);
    try {
      const response = await clientFetch(
        `/api/admin/orders/${order.id}/restore`,
        {
          method: "PATCH",
        },
        true
      );
      if (!response.ok) {
        return;
      }
      onRemoved(order.id);
      window.dispatchEvent(new Event(ADMIN_ORDERS_BADGE_EVENT));
    } finally {
      setIsRestoring(false);
    }
  };

  return (
    <div className="relative rounded-[24px] border border-white/80 bg-white/70 p-4 shadow-sm">
      <div ref={menuRef} className="absolute right-4 top-4 z-20">
        <button
          type="button"
          aria-label="Order actions"
          aria-expanded={isMenuOpen}
          onClick={() => setIsMenuOpen((current) => !current)}
          disabled={isBusy}
          className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-stone-200 bg-white/90 transition hover:border-stone-300 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span className="inline-flex items-center gap-0.5">
            <span className="h-1 w-1 rounded-full bg-stone-600" />
            <span className="h-1 w-1 rounded-full bg-stone-600" />
            <span className="h-1 w-1 rounded-full bg-stone-600" />
          </span>
        </button>
        {isMenuOpen ? (
          <div className="absolute right-0 top-10 min-w-[190px] rounded-2xl border border-stone-200 bg-white p-1.5 shadow-lg">
            {isDeletedMode ? (
              <>
                <button
                  type="button"
                  onClick={restoreOrder}
                  disabled={isBusy}
                  className="flex w-full items-center rounded-xl px-3 py-2 text-left text-xs uppercase tracking-[0.18em] text-emerald-700 transition hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isRestoring ? "Restoring..." : "Restore"}
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={softDelete}
                disabled={isBusy}
                className="flex w-full items-center rounded-xl px-3 py-2 text-left text-xs uppercase tracking-[0.18em] text-rose-700 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isDeleting ? "Deleting..." : "Delete"}
              </button>
            )}
          </div>
        ) : null}
      </div>
      <div className="flex flex-col gap-4 pr-10">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-[0.2em] text-stone-500">
            Order {order.id.slice(0, 8)}
          </p>
          <p className="break-words text-sm font-semibold text-stone-900">
            {formatMoney(order.totalCents)}
          </p>
          <p className="text-xs text-stone-500">
            {formatDateTime(order.createdAt)}
          </p>
          {order.email ? (
            <p className="break-all text-xs text-stone-500">{order.email}</p>
          ) : null}
        </div>
        <div className="flex w-full flex-wrap items-center justify-start gap-2">
          <div
            className={`${orderMetaBadgeClass} ${orderStatusBadgeClass(
              order.status
            )}`}
          >
            {statusLabel}
          </div>
          <button
            type="button"
            onClick={toggleRead}
            disabled={isBusy}
            className={`${orderMetaBadgeClass} transition ${
              isRead
                ? "border-emerald-200 bg-emerald-100 text-emerald-700"
                : "border-stone-200 bg-white/80 text-stone-600"
            } ${isLoading ? "cursor-wait opacity-70" : ""} ${
              isBusy && !isLoading ? "opacity-70" : ""
            }`}
          >
            {isRead ? "Read" : "Unread"}
          </button>
          <div
            className={`${orderMetaBadgeClass} border-stone-200 bg-white/80 text-stone-600`}
          >
            {order.items.length} items
          </div>
          <Link
            href={`/admin/orders/${order.id}`}
            onClick={storeScrollPosition}
            className={`${orderMetaBadgeClass} border-stone-300 bg-white/80 text-stone-600 transition hover:border-stone-400`}
          >
            Details
          </Link>
        </div>
      </div>
      <div className="mt-4 grid gap-2 text-sm text-stone-600">
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
    </div>
  );
}
