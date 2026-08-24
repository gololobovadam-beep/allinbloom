import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { requireAuth } from "@/lib/auth-session";
import SignOutButton from "@/components/sign-out-button";
import { getOrdersByEmail } from "@/lib/data/orders";
import type { OrderStatus } from "@/lib/api-types";
import { formatDateTime, formatMoney, formatOrderStatus } from "@/lib/format";
import { getCurrentUser } from "@/lib/data/users";
import AdminAlertsBadge from "@/components/admin-alerts-badge";
import AdminReviewsBadge from "@/components/admin-reviews-badge";

export const metadata: Metadata = {
  title: "Account",
  robots: {
    index: false,
    follow: false,
  },
};

const orderStatusBadgeClass = (status: OrderStatus) => {
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

export default async function AccountPage() {
  const { user } = await requireAuth();
  if (!user) {
    redirect("/auth");
  }

  const [orders, currentUser] = await Promise.all([
    getOrdersByEmail(user.email),
    getCurrentUser(),
  ]);

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 sm:gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between sm:gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.32em] text-stone-500">
            Account
          </p>
          <h1 className="text-3xl font-semibold text-stone-900 sm:text-5xl">
            Welcome back
          </h1>
        </div>
        <div className="w-full sm:w-auto sm:min-w-[180px]">
          <SignOutButton />
        </div>
      </div>
      <div className="glass rounded-[28px] border border-white/80 p-5 text-sm text-stone-600 sm:p-6">
        <p>Name: {currentUser?.name || user.name || "-"}</p>
        <p className="break-all">Email: {currentUser?.email || user.email}</p>
        {currentUser?.phone ? <p>Phone: {currentUser.phone}</p> : null}
        {user.role === "ADMIN" ? (
          <p>Role: {user.role}</p>
        ) : null}
      </div>
      {user.role === "ADMIN" ? (
        <div className="glass rounded-[28px] border border-white/80 p-5 text-sm text-stone-600 sm:p-6">
          <p>You have admin access.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link
              href="/admin"
              className="relative inline-flex h-11 w-full items-center justify-center rounded-full border border-stone-300 bg-white/80 px-4 text-center text-xs uppercase tracking-[0.3em] text-stone-600 sm:w-auto"
            >
              Open admin panel
              <AdminAlertsBadge />
            </Link>
            <Link
              href="/admin/reviews"
              className="relative inline-flex h-11 w-full items-center justify-center rounded-full border border-stone-300 bg-white/80 px-4 text-center text-xs uppercase tracking-[0.3em] text-stone-600 sm:w-auto"
            >
              Reviews
              <AdminReviewsBadge />
            </Link>
          </div>
        </div>
      ) : null}
      <div className="glass rounded-[28px] border border-white/80 p-5 text-sm text-stone-600 sm:p-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-stone-900">
              Order history
            </h2>
            <p className="mt-1 text-xs text-stone-500">
              Your recent purchases and delivery timeline.
            </p>
          </div>
          {orders.length ? (
            <span className="inline-flex h-8 items-center rounded-full border border-stone-200 bg-white/80 px-3 text-[10px] uppercase tracking-[0.24em] text-stone-600">
              {orders.length} orders
            </span>
          ) : null}
        </div>
        <div className="mt-4 space-y-3">
          {orders.length ? (
            orders.map((order) => (
              <article
                key={order.id}
                className="relative overflow-hidden rounded-[24px] border border-white/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.88)_0%,rgba(252,246,244,0.8)_100%)] p-4 shadow-sm sm:p-5"
              >
                <div className="pointer-events-none absolute -right-10 -top-10 h-28 w-28 rounded-full bg-[color:var(--soft-rose)]/75 blur-2xl" />
                <div className="relative">
                  <div className="grid gap-3">
                    <div className="min-w-0">
                      <p className="inline-flex h-8 w-fit items-center justify-start rounded-full border border-white/80 bg-white/80 px-3 text-left text-[10px] uppercase tracking-[0.24em] text-stone-600">
                        Order {order.id.slice(0, 8)}
                      </p>
                      <p className="mt-2 text-xs text-stone-500">
                        {formatDateTime(order.createdAt)}
                      </p>
                    </div>
                    <div className="flex w-full flex-wrap items-center justify-start gap-2">
                      <span
                        className={`${orderMetaBadgeClass} ${orderStatusBadgeClass(
                          order.status
                        )}`}
                      >
                        {formatOrderStatus(order.status)}
                      </span>
                      <span
                        className={`${orderMetaBadgeClass} border-stone-200 bg-white/80 text-stone-600`}
                      >
                        {order.items.length} items
                      </span>
                    </div>
                  </div>

                  <div className="mt-4">
                    <p className="text-[10px] uppercase tracking-[0.24em] text-stone-500">
                      Total
                    </p>
                    <p className="text-xl font-semibold text-stone-900 sm:text-2xl">
                      {formatMoney(order.totalCents)}
                    </p>
                  </div>

                  <div className="mt-4 rounded-2xl border border-white/80 bg-white/70 p-3 sm:p-4">
                    <p className="text-[10px] uppercase tracking-[0.24em] text-stone-500">
                      Items
                    </p>
                    <div className="mt-2 space-y-2">
                      {order.items.map((item) => (
                        <div
                          key={item.id}
                          className="flex items-start justify-between gap-3 text-sm text-stone-700"
                        >
                          <span className="min-w-0 break-words">
                            {item.quantity} x {item.name}
                          </span>
                          <span className="shrink-0 text-xs text-stone-500">
                            {formatMoney(item.priceCents)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </article>
            ))
          ) : (
            <div className="rounded-2xl border border-dashed border-stone-300/70 bg-white/55 p-6 text-center">
              <p className="text-sm text-stone-600">
                No orders yet. Start with our seasonal collection.
              </p>
              <Link
                href="/catalog"
                className="mt-4 inline-flex h-11 items-center justify-center rounded-full bg-[color:var(--brand)] px-6 text-xs uppercase tracking-[0.3em] text-white transition hover:bg-[color:var(--brand-dark)]"
              >
                Browse catalog
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
