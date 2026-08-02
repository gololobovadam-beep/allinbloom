import type { Bouquet, StoreSettings } from "@/lib/api-types";
import { normalizeColorValue, normalizePaletteText } from "@/lib/colors";

export type DiscountInfo = {
  percent: number;
  note: string;
  source: "bouquet" | "category" | "global";
};

export const clampPercent = (value: number) =>
  Math.min(90, Math.max(0, Math.round(value)));

export const applyPercentDiscount = (priceCents: number, percent: number) => {
  const clamped = clampPercent(percent);
  return Math.max(0, Math.round(priceCents * (100 - clamped) / 100));
};

type CategorySettings = Pick<
  StoreSettings,
  | "categoryDiscountPercent"
  | "categoryDiscountNote"
  | "categoryFlowerType"
  | "categoryMixed"
  | "categoryColor"
  | "categoryMinPriceCents"
  | "categoryMaxPriceCents"
>;

type GlobalSettings = Pick<
  StoreSettings,
  "globalDiscountPercent" | "globalDiscountNote"
>;

const hasCategoryFilters = (settings: CategorySettings) =>
  Boolean(
    settings.categoryFlowerType ||
      settings.categoryMixed ||
      settings.categoryColor ||
      settings.categoryMinPriceCents !== null ||
      settings.categoryMaxPriceCents !== null
  );

const matchesCategory = (
  bouquet: Pick<
    Bouquet,
    | "catalogType"
    | "flowerType"
    | "isMixed"
    | "bouquetType"
    | "colors"
    | "priceCents"
  >,
  settings: CategorySettings
) => {
  // Category rules are configured with flower attributes, so the same rule
  // must not accidentally discount a Gift or Balloon that uses neutral legacy
  // flower fields on the shared product table.
  if (bouquet.catalogType && bouquet.catalogType !== "FLOWERS") return false;
  if (settings.categoryDiscountPercent <= 0) return false;
  if (!hasCategoryFilters(settings)) return false;

  if (
    settings.categoryFlowerType &&
    settings.categoryFlowerType !== bouquet.flowerType
  ) {
    return false;
  }

  if (settings.categoryMixed === "mixed") {
    if (bouquet.bouquetType) {
      if (bouquet.bouquetType !== "MIXED") return false;
    } else if (!bouquet.isMixed) {
      return false;
    }
  }

  if (settings.categoryMixed === "mono") {
    if (bouquet.bouquetType) {
      if (bouquet.bouquetType !== "MONO") return false;
    } else if (bouquet.isMixed) {
      return false;
    }
  }

  if (settings.categoryMixed === "season" && bouquet.bouquetType !== "SEASON") {
    return false;
  }

  if (settings.categoryColor) {
    const palette = normalizePaletteText(bouquet.colors);
    const needle = normalizeColorValue(settings.categoryColor) || settings.categoryColor.toLowerCase();
    if (!palette.includes(needle)) {
      return false;
    }
  }

  if (
    settings.categoryMinPriceCents !== null &&
    bouquet.priceCents < settings.categoryMinPriceCents
  ) {
    return false;
  }

  if (
    settings.categoryMaxPriceCents !== null &&
    bouquet.priceCents > settings.categoryMaxPriceCents
  ) {
    return false;
  }

  return true;
};

export const getBouquetDiscount = (
  bouquet: Pick<
    Bouquet,
    | "discountPercent"
    | "discountNote"
    | "catalogType"
    | "flowerType"
    | "isMixed"
    | "bouquetType"
    | "colors"
    | "priceCents"
  >,
  settings: CategorySettings & GlobalSettings
): DiscountInfo | null => {
  if (bouquet.catalogType === "EVENT_SPACE") return null;

  if (bouquet.discountPercent > 0) {
    return {
      percent: bouquet.discountPercent,
      note: bouquet.discountNote || "Discount",
      source: "bouquet",
    };
  }

  if (matchesCategory(bouquet, settings)) {
    return {
      percent: settings.categoryDiscountPercent,
      note: settings.categoryDiscountNote || "Discount",
      source: "category",
    };
  }

  if (settings.globalDiscountPercent > 0) {
    return {
      percent: settings.globalDiscountPercent,
      note: settings.globalDiscountNote || "Discount",
      source: "global",
    };
  }

  return null;
};

export const getBouquetPricing = (
  bouquet: Pick<
    Bouquet,
    | "priceCents"
    | "discountPercent"
    | "discountNote"
    | "catalogType"
    | "flowerType"
    | "isMixed"
    | "bouquetType"
    | "colors"
  >,
  settings: CategorySettings & GlobalSettings
) => {
  const discount = getBouquetDiscount(bouquet, settings);
  const finalPriceCents = discount
    ? applyPercentDiscount(bouquet.priceCents, discount.percent)
    : bouquet.priceCents;

  return {
    originalPriceCents: bouquet.priceCents,
    finalPriceCents,
    discount,
  };
};

export const getCartItemDiscount = (
  item: {
    basePriceCents: number;
    bouquetDiscountPercent?: number;
    bouquetDiscountNote?: string;
    flowerType?: string;
    isMixed?: boolean;
    bouquetType?: string;
    colors?: string;
    catalogType?: Bouquet["catalogType"];
    isCustom?: boolean;
  },
  settings: CategorySettings & GlobalSettings
): DiscountInfo | null => {
  // Florist Choice pricing is separately validated by checkout and does not
  // inherit catalog-wide discounts. Keep the cart total aligned with it.
  if (item.isCustom) return null;

  if (item.bouquetDiscountPercent && item.bouquetDiscountPercent > 0) {
    return {
      percent: item.bouquetDiscountPercent,
      note: item.bouquetDiscountNote || "Discount",
      source: "bouquet",
    };
  }

  if (
    matchesCategory(
      {
        catalogType: item.catalogType,
        flowerType: (item.flowerType || "") as Bouquet["flowerType"],
        isMixed: Boolean(item.isMixed),
        bouquetType: (item.bouquetType || "").toUpperCase() as Bouquet["bouquetType"],
        colors: item.colors || "",
        priceCents: item.basePriceCents,
      },
      settings
    )
  ) {
    return {
      percent: settings.categoryDiscountPercent,
      note: settings.categoryDiscountNote || "Discount",
      source: "category",
    };
  }

  if (settings.globalDiscountPercent > 0) {
    return {
      percent: settings.globalDiscountPercent,
      note: settings.globalDiscountNote || "Discount",
      source: "global",
    };
  }

  return null;
};
