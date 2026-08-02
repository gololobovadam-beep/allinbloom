"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import type { Bouquet, CatalogType } from "@/lib/api-types";
import { formatMoney } from "@/lib/format";
import { deleteCatalogProduct } from "@/app/admin/actions";
import ImageWithFallback from "@/components/image-with-fallback";
import { getBouquetGalleryImages } from "@/lib/bouquet-images";

type AdminCatalogProductRowProps = {
  product: Bouquet;
  catalogType: Extract<CatalogType, "BALOONS" | "GIFTS" | "EVENT_SPACE">;
  editPath: string;
};

export default function AdminCatalogProductRow({
  product,
  catalogType,
  editPath,
}: AdminCatalogProductRowProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const image = getBouquetGalleryImages(product)[0] || product.image;

  useEffect(() => {
    if (!isMenuOpen) return;
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (event.target instanceof Node && !menuRef.current?.contains(event.target)) {
        setIsMenuOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsMenuOpen(false);
    };
    window.addEventListener("mousedown", closeOnOutsideClick);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("mousedown", closeOnOutsideClick);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [isMenuOpen]);

  const confirmPermanentDelete = (event: FormEvent<HTMLFormElement>) => {
    if (!window.confirm("Delete this item permanently? This cannot be undone.")) {
      event.preventDefault();
      return;
    }
    setIsMenuOpen(false);
  };

  return (
    <div className="relative rounded-[24px] border border-white/80 bg-white/70 p-4 shadow-sm">
      <div ref={menuRef} className="absolute right-4 top-4 z-20">
        <button
          type="button"
          aria-label="Product actions"
          aria-expanded={isMenuOpen}
          onClick={() => setIsMenuOpen((current) => !current)}
          className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-stone-200 bg-white/90 transition hover:border-stone-300"
        >
          <span className="inline-flex items-center gap-0.5">
            <span className="h-1 w-1 rounded-full bg-stone-600" />
            <span className="h-1 w-1 rounded-full bg-stone-600" />
            <span className="h-1 w-1 rounded-full bg-stone-600" />
          </span>
        </button>
        {isMenuOpen ? (
          <div className="absolute right-0 top-10 min-w-[190px] rounded-2xl border border-stone-200 bg-white p-1.5 shadow-lg">
            <form action={deleteCatalogProduct} onSubmit={confirmPermanentDelete}>
              <input type="hidden" name="id" value={product.id} />
              <input type="hidden" name="catalogType" value={catalogType} />
              <button
                type="submit"
                className="flex w-full items-center rounded-xl px-3 py-2 text-left text-xs uppercase tracking-[0.18em] text-rose-700 transition hover:bg-rose-50"
              >
                Delete forever
              </button>
            </form>
          </div>
        ) : null}
      </div>
      <div className="flex max-w-full flex-col gap-4 pr-10 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 flex-1 items-center gap-4">
          <div className="h-16 w-16 shrink-0 overflow-hidden rounded-2xl border border-white/80 bg-white">
            <ImageWithFallback
              src={image}
              alt={product.name}
              width={80}
              height={80}
              className="h-full w-full object-cover"
            />
          </div>
          <div className="min-w-0">
            <p className="break-words text-sm font-semibold text-stone-900 [overflow-wrap:anywhere]">
              {product.name}
            </p>
            <p className="break-words text-xs uppercase tracking-[0.2em] text-stone-500">
              {catalogType === "EVENT_SPACE" ? "Event space" : formatMoney(product.priceCents)}
            </p>
          </div>
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center sm:gap-3">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {product.isFeatured ? (
              <span className="rounded-full bg-rose-100 px-3 py-1 text-rose-700">Featured</span>
            ) : null}
            {!product.isActive ? (
              <span className="rounded-full bg-stone-200 px-3 py-1 text-stone-600">Hidden</span>
            ) : null}
            {product.isSoldOut ? (
              <span className="rounded-full bg-amber-100 px-3 py-1 text-amber-700">Sold out</span>
            ) : null}
          </div>
          <Link
            href={`${editPath}/${product.id}/edit`}
            className="inline-flex h-11 w-full items-center justify-center rounded-full border border-stone-300 bg-white/80 px-4 text-center text-xs uppercase tracking-[0.3em] text-stone-600 sm:w-auto"
          >
            Edit
          </Link>
        </div>
      </div>
    </div>
  );
}
