import Link from "next/link";
import AdminOrdersBadge from "@/components/admin-orders-badge";
import AdminReviewsBadge from "@/components/admin-reviews-badge";

export default function AdminSidebar() {
  return (
    <aside className="glass h-fit w-full rounded-[28px] border border-white/80 p-5 sm:p-6 lg:max-w-[260px]">
      <div className="space-y-1">
        <p className="text-xs uppercase tracking-[0.32em] text-stone-500">
          All in Bloom
        </p>
        <h2 className="text-xl font-semibold text-stone-900">Admin panel</h2>
      </div>
      <nav className="mt-6 space-y-3 text-sm text-stone-600">
        <Link
          href="/admin"
          className="flex h-11 items-center rounded-2xl border border-transparent bg-white/70 px-3 transition hover:border-stone-200"
        >
          Bouquets
        </Link>
        <Link
          href="/admin/balloons"
          className="flex h-11 items-center rounded-2xl border border-transparent bg-white/70 px-3 transition hover:border-stone-200"
        >
          Balloons
        </Link>
        <Link
          href="/admin/gifts"
          className="flex h-11 items-center rounded-2xl border border-transparent bg-white/70 px-3 transition hover:border-stone-200"
        >
          Gifts
        </Link>
        <Link
          href="/admin/event-space"
          className="flex h-11 items-center rounded-2xl border border-transparent bg-white/70 px-3 transition hover:border-stone-200"
        >
          Event space
        </Link>
        <Link
          href="/admin/orders"
          className="relative flex h-11 items-center rounded-2xl border border-transparent bg-white/70 px-3 transition hover:border-stone-200"
        >
          Orders
          <AdminOrdersBadge />
        </Link>
        <Link
          href="/admin/reviews"
          className="relative flex h-11 items-center rounded-2xl border border-transparent bg-white/70 px-3 transition hover:border-stone-200"
        >
          Reviews
          <AdminReviewsBadge />
        </Link>
        <Link
          href="/admin/promotions"
          className="flex h-11 items-center rounded-2xl border border-transparent bg-white/70 px-3 transition hover:border-stone-200"
        >
          Promotions
        </Link>
        <Link
          href="/admin/discounts"
          className="flex h-11 items-center rounded-2xl border border-transparent bg-white/70 px-3 transition hover:border-stone-200"
        >
          Discounts
        </Link>
        <Link
          href="/admin/home-images"
          className="flex h-11 items-center rounded-2xl border border-transparent bg-white/70 px-3 transition hover:border-stone-200"
        >
          Homepage images
        </Link>
        <Link
          href="/catalog"
          className="flex h-11 items-center rounded-2xl border border-transparent bg-white/70 px-3 transition hover:border-stone-200"
        >
          View storefront
        </Link>
      </nav>
    </aside>
  );
}
