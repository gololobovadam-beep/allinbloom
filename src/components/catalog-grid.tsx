"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import BouquetCard from "@/components/bouquet-card";
import ProductCard, {
  type EditorialProductKind,
} from "@/components/product-card";
import type { CatalogItem } from "@/lib/api-types";
import type { CatalogSearchParams } from "@/lib/data/bouquets";

export type CatalogGridVariant = "bouquet" | EditorialProductKind;

type CatalogGridProps = {
  initialItems: CatalogItem[];
  initialCursor: string | null;
  filters: CatalogSearchParams;
  filtersKey: string;
  firstOrderDiscount: {
    percent: number;
    note: string;
  } | null;
  cardVariant?: CatalogGridVariant;
  emptyMessage?: string;
  productLabel?: string;
};

const MOBILE_PAGE_SIZE = 6;
const DESKTOP_PAGE_SIZE = 12;

const useCatalogPageSize = () => {
  const [pageSize, setPageSize] = useState(DESKTOP_PAGE_SIZE);

  useEffect(() => {
    const query = window.matchMedia("(min-width: 1024px)");
    const update = () => {
      setPageSize(query.matches ? DESKTOP_PAGE_SIZE : MOBILE_PAGE_SIZE);
    };
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  return pageSize;
};

export default function CatalogGrid({
  initialItems,
  initialCursor,
  filters,
  filtersKey,
  firstOrderDiscount,
  cardVariant = "bouquet",
  emptyMessage =
    "No bouquets match these filters. Try a softer palette or wider price range.",
  productLabel = "bouquets",
}: CatalogGridProps) {
  const [items, setItems] = useState<CatalogItem[]>(initialItems);
  const [cursor, setCursor] = useState<string | null>(initialCursor);
  const [hasMore, setHasMore] = useState(Boolean(initialCursor));
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const pageSize = useCatalogPageSize();
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setItems(initialItems);
    setCursor(initialCursor);
    setHasMore(Boolean(initialCursor));
    setIsLoading(false);
    setError("");
  }, [filtersKey, initialCursor, initialItems]);

  const baseParams = useMemo(() => {
    const params = new URLSearchParams();
    if (filters.catalogType) params.set("catalogType", filters.catalogType);
    if (filters.filter) params.set("filter", filters.filter);
    if (filters.flower) params.set("flower", filters.flower);
    if (filters.color) params.set("color", filters.color);
    if (filters.bouquetType) params.set("bouquetType", filters.bouquetType);
    if (filters.min) params.set("min", filters.min);
    if (filters.max) params.set("max", filters.max);
    if (filters.sort) params.set("sort", filters.sort);
    return params;
  }, [
    filters.bouquetType,
    filters.catalogType,
    filters.color,
    filters.filter,
    filters.flower,
    filters.max,
    filters.min,
    filters.sort,
  ]);

  const loadMore = useCallback(async () => {
    if (isLoading || !hasMore) return;
    setIsLoading(true);
    setError("");

    try {
      const params = new URLSearchParams(baseParams);
      params.set("take", String(pageSize));
      if (cursor) {
        params.set("cursor", cursor);
      }

      const response = await fetch(`/api/catalog?${params.toString()}`, {
        method: "GET",
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error("Failed to load more catalog products.");
      }

      const data = (await response.json()) as {
        items: CatalogItem[];
        nextCursor: string | null;
      };

      setItems((prev) => [...prev, ...data.items]);
      setCursor(data.nextCursor);
      setHasMore(Boolean(data.nextCursor));
    } catch {
      setError("Unable to load more products right now.");
    } finally {
      setIsLoading(false);
    }
  }, [baseParams, cursor, hasMore, isLoading, pageSize]);

  useEffect(() => {
    if (!hasMore) return;
    const target = sentinelRef.current;
    if (!target) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          loadMore();
        }
      },
      { rootMargin: "360px" }
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [hasMore, loadMore]);

  if (!items.length) {
    return (
      <div className="glass rounded-[28px] border border-white/80 p-8 text-center text-sm text-stone-600">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="relative z-0 space-y-6">
      <div
        className={
          cardVariant === "bouquet"
            ? "grid grid-cols-2 gap-3 sm:gap-6 md:grid-cols-2 lg:grid-cols-3"
            : "space-y-5 sm:space-y-6"
        }
      >
        {items.map((entry) => (
          cardVariant === "bouquet" ? (
            <BouquetCard
              key={entry.bouquet.id}
              bouquet={entry.bouquet}
              pricing={entry.pricing}
              firstOrderDiscount={firstOrderDiscount}
              enableFlowerQuantityInput={filters.catalogType !== "BALOONS"}
              splitPriceRows
            />
          ) : (
            <ProductCard
              key={entry.bouquet.id}
              product={entry.bouquet}
              kind={cardVariant}
              pricing={entry.pricing}
              firstOrderDiscount={firstOrderDiscount}
            />
          )
        ))}
      </div>
      <div className="flex flex-col items-center gap-2 text-xs uppercase tracking-[0.22em] text-stone-500 sm:tracking-[0.3em]">
        {hasMore ? (
          <>
            <span>{isLoading ? `Loading more ${productLabel}` : "Scroll for more"}</span>
            <div
              ref={sentinelRef}
              className="h-6 w-full"
              aria-hidden="true"
            />
          </>
        ) : (
          <span>All {productLabel} loaded</span>
        )}
        {error ? (
          <span className="text-[11px] uppercase tracking-[0.22em] text-rose-500">
            {error}
          </span>
        ) : null}
      </div>
    </div>
  );
}
