import { headers } from "next/headers";
import CatalogGrid, { type CatalogGridVariant } from "@/components/catalog-grid";
import type { CatalogType } from "@/lib/api-types";
import { getAuthSession } from "@/lib/auth-session";
import { getBouquets } from "@/lib/data/bouquets";
import { getOrdersByEmail } from "@/lib/data/orders";
import { isFirstOrderEligibleForKnownHistory } from "@/lib/first-order-discount";
import { getBouquetPricing } from "@/lib/pricing";
import { getStoreSettings } from "@/lib/data/settings";

const MOBILE_UA =
  /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile/i;

const getInitialPageSize = async () => {
  const headerStore = await headers();
  return MOBILE_UA.test(headerStore.get("user-agent") || "") ? 6 : 12;
};

type CatalogListingProps = {
  catalogType: CatalogType;
  eyebrow: string;
  title: string;
  description: string;
  cardVariant?: CatalogGridVariant;
  productLabel: string;
  emptyMessage: string;
  includeFirstOrderDiscount?: boolean;
};

/** Shared, filter-free catalog shell for the new top-level catalog sections. */
export default async function CatalogListing({
  catalogType,
  eyebrow,
  title,
  description,
  cardVariant = "bouquet",
  productLabel,
  emptyMessage,
  includeFirstOrderDiscount = true,
}: CatalogListingProps) {
  const pageSize = await getInitialPageSize();
  const [settings, rawProducts, session] = await Promise.all([
    getStoreSettings(),
    getBouquets({ catalogType }, { take: pageSize + 1 }),
    includeFirstOrderDiscount ? getAuthSession() : Promise.resolve({ user: null }),
  ]);
  const hasMore = rawProducts.length > pageSize;
  const products = hasMore ? rawProducts.slice(0, pageSize) : rawProducts;
  const email = session.user?.email || null;
  const orders = includeFirstOrderDiscount && email ? await getOrdersByEmail(email) : [];
  // The server grants the one-time offer only to a verified account, where
  // eligibility can be atomically checked. Keep catalog pricing aligned with
  // the amount that checkout will actually charge.
  const isFirstOrderEligible = includeFirstOrderDiscount
    ? Boolean(email && isFirstOrderEligibleForKnownHistory(orders))
    : false;
  const firstOrderDiscount =
    isFirstOrderEligible && settings.firstOrderDiscountPercent > 0
      ? {
          percent: settings.firstOrderDiscountPercent,
          note: settings.firstOrderDiscountNote || "10% off your first order",
        }
      : null;
  const initialItems = products.map((bouquet) => ({
    bouquet,
    pricing: getBouquetPricing(bouquet, settings),
  }));
  const lastProduct = products[products.length - 1];

  return (
    <div className="flex flex-col gap-7 sm:gap-10">
      <div className="space-y-3">
        <p className="text-xs uppercase tracking-[0.32em] text-stone-500">
          {eyebrow}
        </p>
        <h1 className="text-3xl font-semibold text-stone-900 sm:text-5xl">
          {title}
        </h1>
        <p className="max-w-2xl text-balance text-sm leading-relaxed text-stone-600">
          {description}
        </p>
      </div>
      <CatalogGrid
        initialItems={initialItems}
        initialCursor={hasMore && lastProduct ? lastProduct.id : null}
        filters={{ catalogType }}
        filtersKey={`catalog:${catalogType}`}
        firstOrderDiscount={firstOrderDiscount}
        cardVariant={cardVariant}
        emptyMessage={emptyMessage}
        productLabel={productLabel}
      />
    </div>
  );
}
