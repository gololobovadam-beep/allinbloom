import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import CatalogFilters from "@/components/catalog-filters";
import CatalogGrid from "@/components/catalog-grid";
import { getBouquets } from "@/lib/data/bouquets";
import type { CatalogSearchParams } from "@/lib/data/bouquets";
import { getStoreSettings } from "@/lib/data/settings";
import { getCatalogCategoryImages } from "@/lib/home-images";
import { getBouquetPricing } from "@/lib/pricing";
import { SITE_DESCRIPTION } from "@/lib/site";
import { getAuthSession } from "@/lib/auth-session";
import { getOrdersByEmail } from "@/lib/data/orders";
import { isFirstOrderEligibleForKnownHistory } from "@/lib/first-order-discount";
import { headers } from "next/headers";

const MOBILE_UA =
  /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile/i;

const CATALOG_CATEGORY_TILES = [
  {
    key: "mono",
    title: "Mono bouquets",
    href: "/catalog?entry=1&bouquetType=mono",
  },
  {
    key: "mixed",
    title: "Mixed bouquets",
    href: "/catalog?entry=1&bouquetType=mixed",
  },
  {
    key: "season",
    title: "Seasonal bouquets",
    href: "/catalog?entry=1&bouquetType=season",
  },
  {
    key: "all",
    title: "All bouquets",
    href: "/catalog?entry=1",
  },
] as const;

const getInitialPageSize = async () => {
  const headerStore = await headers();
  const ua = headerStore.get("user-agent") || "";
  return MOBILE_UA.test(ua) ? 6 : 12;
};

const resolveBouquetType = (params: CatalogSearchParams) => {
  const direct = (params.bouquetType || "").trim().toLowerCase();
  if (direct === "mono" || direct === "mixed" || direct === "season") {
    return direct;
  }
  const legacyMixed = (params.mixed || "").trim().toLowerCase();
  if (legacyMixed === "mono" || legacyMixed === "mixed") {
    return legacyMixed;
  }
  if ((params.style || "").trim().toLowerCase() === "season") {
    return "season";
  }
  return "";
};

const hasCatalogListingContext = (params: CatalogSearchParams) =>
  params.entry === "1" ||
  Boolean(
    params.filter ||
      params.flower ||
      params.color ||
      resolveBouquetType(params) ||
      params.min ||
      params.max ||
      params.sort
  );

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<CatalogSearchParams>;
}): Promise<Metadata> {
  const params = await searchParams;
  const hasListingContext = hasCatalogListingContext(params);
  const isFeatured = params.filter === "featured";
  const title = !hasListingContext
    ? "Bouquet Categories | Chicago Flower Delivery"
    : isFeatured
    ? "Signature Bouquets | Chicago Florist"
    : "Bouquet Catalog | Chicago Flower Delivery";
  const description = !hasListingContext
    ? "Choose a bouquet category: mono, mixed, seasonal, or all bouquets."
    : isFeatured
    ? "Discover our most-loved signature bouquets curated by Chicago florists."
    : "Browse our full Chicago flower delivery catalog. Filter by flower, palette, bouquet type, and price.";
  const canonical = isFeatured
    ? "/catalog?filter=featured"
    : hasListingContext
    ? "/catalog?entry=1"
    : "/catalog";

  return {
    title,
    description,
    alternates: {
      canonical,
    },
    openGraph: {
      title,
      description: SITE_DESCRIPTION,
      url: canonical,
    },
  };
}

export default async function CatalogPage({
  searchParams,
}: {
  searchParams: Promise<CatalogSearchParams>;
}) {
  const params = await searchParams;
  const hasListingContext = hasCatalogListingContext(params);
  const settings = await getStoreSettings();
  const catalogCategoryImages = getCatalogCategoryImages(settings);
  const catalogCategoryTiles = CATALOG_CATEGORY_TILES.map((tile) => ({
    ...tile,
    image: catalogCategoryImages[tile.key],
  }));
  if (!hasListingContext) {
    return (
      <div className="flex flex-col gap-6 sm:gap-8">
        <div className="space-y-3">
          <p className="text-xs uppercase tracking-[0.32em] text-stone-500">
            Catalog
          </p>
          <h1 className="text-3xl font-semibold text-stone-900 sm:text-5xl">
            Choose your bouquet category
          </h1>
          <p className="max-w-2xl text-balance text-sm leading-relaxed text-stone-600">
            Start with a category, then refine your selection with filters.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          {catalogCategoryTiles.map((tile) => {
            const [firstWord, ...restWords] = tile.title.split(" ");
            return (
              <Link
                key={tile.title}
                href={tile.href}
                className="group relative isolate overflow-hidden rounded-[24px] border border-white/80 bg-white/70 shadow-sm transition lg:hover:-translate-y-1 lg:hover:shadow-[0_16px_35px_rgba(var(--brand-rgb),0.22)]"
              >
                <div className="relative aspect-square w-full">
                  <Image
                    src={tile.image}
                    alt={tile.title}
                    fill
                    sizes="(max-width: 639px) 48vw, (max-width: 1023px) 30vw, 22vw"
                    className="object-cover transition duration-500 lg:group-hover:scale-110"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-[rgba(26,11,8,0.72)] via-[rgba(26,11,8,0.28)] to-transparent transition lg:group-hover:from-[rgba(26,11,8,0.82)]" />
                  <div className="absolute inset-x-2 bottom-2 rounded-2xl border border-white/40 bg-white/18 px-3 py-2 backdrop-blur">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-white sm:text-xs sm:tracking-[0.24em]">
                      <span className="block leading-tight">{firstWord}</span>
                      <span className="mt-0.5 block leading-tight">
                        {restWords.join(" ")}
                      </span>
                    </p>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    );
  }

  const listFilters: CatalogSearchParams = {
    filter: params.filter,
    flower: params.flower,
    color: params.color,
    bouquetType: resolveBouquetType(params),
    min: params.min,
    max: params.max,
    sort: params.sort,
  };
  const { user } = await getAuthSession();
  const email = user?.email || null;
  const orders = email ? await getOrdersByEmail(email) : [];
  // First-order discounts are verified-account only on the backend to keep
  // the promotion race-safe; do not advertise a guest-only price here.
  const isFirstOrderEligible = Boolean(
    email && isFirstOrderEligibleForKnownHistory(orders)
  );
  const firstOrderDiscount =
    isFirstOrderEligible && settings.firstOrderDiscountPercent > 0
      ? {
          percent: settings.firstOrderDiscountPercent,
          note: settings.firstOrderDiscountNote || "10% off your first order",
        }
      : null;
  const pageSize = await getInitialPageSize();
  const rawBouquets = await getBouquets(listFilters, { take: pageSize + 1 });
  const hasMore = rawBouquets.length > pageSize;
  const bouquets = hasMore ? rawBouquets.slice(0, pageSize) : rawBouquets;
  const isFeatured = params.filter === "featured";
  const initialItems = bouquets.map((bouquet) => ({
    bouquet,
    pricing: getBouquetPricing(bouquet, settings),
  }));
  const lastBouquet = bouquets[bouquets.length - 1];
  const initialCursor = hasMore && lastBouquet ? lastBouquet.id : null;
  const filtersKey = [
    params.entry || "",
    params.filter || "",
    params.flower || "",
    params.color || "",
    resolveBouquetType(params),
    params.min || "",
    params.max || "",
    params.sort || "",
  ].join("|");

  return (
    <div className="flex flex-col gap-7 sm:gap-10">
      <div className="space-y-3">
        <p className="text-xs uppercase tracking-[0.32em] text-stone-500">
          {isFeatured ? "Signature edit" : "Catalog"}
        </p>
        <h1 className="text-3xl font-semibold text-stone-900 sm:text-5xl">
          {isFeatured ? "Signature sets" : "Bouquets for every mood"}
        </h1>
        <p className="max-w-2xl text-balance text-sm leading-relaxed text-stone-600">
          {isFeatured
            ? "Our most loved bouquets, curated by the All in Bloom Floral Studio team."
            : "Filter by flower, palette, bouquet type, and price. Every bouquet is assembled fresh on the day of delivery by our in-house florists."}
        </p>
      </div>
      <CatalogFilters />
      <CatalogGrid
        initialItems={initialItems}
        initialCursor={initialCursor}
        filters={listFilters}
        filtersKey={filtersKey}
        firstOrderDiscount={firstOrderDiscount}
      />
    </div>
  );
}
