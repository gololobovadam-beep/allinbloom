"use client";

import Link from "next/link";
import { useCart } from "@/lib/cart";

export default function CartBadge({ compact = false }: { compact?: boolean }) {
  const { itemCount } = useCart();

  return (
    <Link
      href="/cart"
      className={`relative inline-flex items-center whitespace-nowrap rounded-full border border-stone-200 bg-white/80 uppercase text-stone-600 transition hover:border-stone-300 hover:text-stone-900 sm:px-4 sm:py-2 sm:text-xs sm:tracking-[0.3em] ${
        compact
          ? "px-2.5 py-[7px] text-[10px] tracking-[0.18em]"
          : "px-3 py-2 text-[11px] tracking-[0.22em]"
      }`}
    >
      Cart
      {itemCount > 0 ? (
        <span className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-[color:var(--brand)] text-[10px] font-semibold text-white">
          {itemCount}
        </span>
      ) : null}
    </Link>
  );
}
