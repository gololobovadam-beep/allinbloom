import { describe, expect, it } from "vitest";

import type { Bouquet, StoreSettings } from "@/lib/api-types";
import {
  applyPercentDiscount,
  clampPercent,
  getBouquetDiscount,
  getBouquetPricing,
  getCartItemDiscount,
} from "@/lib/pricing";

const baseSettings: StoreSettings = {
  id: "default",
  globalDiscountPercent: 0,
  globalDiscountNote: null,
  categoryDiscountPercent: 0,
  categoryDiscountNote: null,
  categoryFlowerType: null,
  categoryStyle: null,
  categoryMixed: null,
  categoryColor: null,
  categoryMinPriceCents: null,
  categoryMaxPriceCents: null,
  firstOrderDiscountPercent: 10,
  firstOrderDiscountNote: "10% off your first order",
  homeHeroImage: "/images/hero-bouquet.webp",
  homeGalleryImage1: "/images/bouquet-1.webp",
  homeGalleryImage2: "/images/bouquet-2.webp",
  homeGalleryImage3: "/images/bouquet-3.webp",
  homeGalleryImage4: "/images/bouquet-4.webp",
  homeGalleryImage5: "/images/bouquet-5.webp",
  homeGalleryImage6: "/images/bouquet-6.webp",
  catalogCategoryImageMono: "/images/bouquet-7.webp",
  catalogCategoryImageMixed: "/images/bouquet-5.webp",
  catalogCategoryImageSeason: "/images/bouquet-2.webp",
  catalogCategoryImageAll: "/images/hero-bouquet.webp",
};

const makeSettings = (overrides: Partial<StoreSettings> = {}): StoreSettings => ({
  ...baseSettings,
  ...overrides,
});

const baseBouquet: Bouquet = {
  id: "bq_1",
  name: "Classic Rose",
  description: "Classic bouquet",
  priceCents: 10000,
  currency: "USD",
  flowerType: "ROSE",
  style: "ROSE",
  bouquetType: "MONO",
  colors: "Red,White",
  isMixed: false,
  isFeatured: true,
  isActive: true,
  isSoldOut: false,
  allowFlowerQuantity: true,
  defaultFlowerQuantity: 1,
  discountPercent: 0,
  discountNote: null,
  image: "/images/bouquet-1.webp",
  image2: null,
  image3: null,
  image4: null,
  image5: null,
  image6: null,
};

describe("pricing helpers", () => {
  it("clamps and rounds discount percent", () => {
    expect(clampPercent(-3)).toBe(0);
    expect(clampPercent(12.6)).toBe(13);
    expect(clampPercent(105)).toBe(90);
  });

  it("applies percent discounts with clamping", () => {
    expect(applyPercentDiscount(10000, 25)).toBe(7500);
    expect(applyPercentDiscount(999, 33)).toBe(669);
    expect(applyPercentDiscount(10000, 200)).toBe(1000);
    expect(applyPercentDiscount(1, 50)).toBe(1);
    expect(applyPercentDiscount(10000, -15)).toBe(10000);
  });
});

describe("getBouquetDiscount", () => {
  it("prefers bouquet discount over category and global", () => {
    const discount = getBouquetDiscount(
      { ...baseBouquet, discountPercent: 35, discountNote: "VIP" },
      makeSettings({
        categoryDiscountPercent: 20,
        categoryFlowerType: "ROSE",
        globalDiscountPercent: 5,
      })
    );

    expect(discount).toEqual({ percent: 35, note: "VIP", source: "bouquet" });
  });

  it("uses category discount only when filters are configured and matched", () => {
    const discount = getBouquetDiscount(
      baseBouquet,
      makeSettings({
        categoryDiscountPercent: 20,
        categoryDiscountNote: "Category promo",
        categoryFlowerType: "ROSE",
        categoryMixed: "mono",
        categoryColor: "red",
        categoryMinPriceCents: 9000,
        categoryMaxPriceCents: 11000,
        globalDiscountPercent: 5,
      })
    );

    expect(discount).toEqual({
      percent: 20,
      note: "Category promo",
      source: "category",
    });
  });

  it("matches season bouquet type filter only for season bouquets", () => {
    const seasonBouquet: Bouquet = {
      ...baseBouquet,
      bouquetType: "SEASON",
      isMixed: false,
    };

    const seasonDiscount = getBouquetDiscount(
      seasonBouquet,
      makeSettings({
        categoryDiscountPercent: 18,
        categoryMixed: "season",
      })
    );

    expect(seasonDiscount).toEqual({
      percent: 18,
      note: "Discount",
      source: "category",
    });

    const monoDiscount = getBouquetDiscount(
      seasonBouquet,
      makeSettings({
        categoryDiscountPercent: 18,
        categoryMixed: "mono",
      })
    );

    expect(monoDiscount).toBeNull();
  });

  it("falls back to global discount when category filters are missing", () => {
    const discount = getBouquetDiscount(
      baseBouquet,
      makeSettings({
        categoryDiscountPercent: 20,
        globalDiscountPercent: 7,
        globalDiscountNote: "Global promo",
      })
    );

    expect(discount).toEqual({
      percent: 7,
      note: "Global promo",
      source: "global",
    });
  });

  it("does not apply flower-category discounts to gifts or balloons", () => {
    const settings = makeSettings({
      categoryDiscountPercent: 20,
      categoryMixed: "mono",
      globalDiscountPercent: 5,
      globalDiscountNote: "Storewide",
    });

    expect(
      getBouquetDiscount({ ...baseBouquet, catalogType: "GIFTS" }, settings)
    ).toEqual({ percent: 5, note: "Storewide", source: "global" });
    expect(
      getBouquetDiscount({ ...baseBouquet, catalogType: "BALOONS" }, settings)
    ).toEqual({ percent: 5, note: "Storewide", source: "global" });
  });

  it("returns null when no discounts are active", () => {
    expect(getBouquetDiscount(baseBouquet, makeSettings())).toBeNull();
  });
});

describe("pricing composition", () => {
  it("returns final bouquet pricing with selected discount", () => {
    const pricing = getBouquetPricing(
      baseBouquet,
      makeSettings({
        globalDiscountPercent: 10,
        globalDiscountNote: "Weekend",
      })
    );

    expect(pricing).toEqual({
      originalPriceCents: 10000,
      finalPriceCents: 9000,
      discount: {
        percent: 10,
        note: "Weekend",
        source: "global",
      },
    });
  });

  it("resolves cart item discount from bouquet fields first", () => {
    const discount = getCartItemDiscount(
      {
        basePriceCents: 12000,
        bouquetDiscountPercent: 15,
        bouquetDiscountNote: "Item promo",
      },
      makeSettings({
        categoryDiscountPercent: 30,
        categoryFlowerType: "ROSE",
        globalDiscountPercent: 5,
      })
    );

    expect(discount).toEqual({
      percent: 15,
      note: "Item promo",
      source: "bouquet",
    });
  });

  it("uses category matching for cart item metadata", () => {
    const discount = getCartItemDiscount(
      {
        basePriceCents: 10000,
        flowerType: "ROSE",
        isMixed: false,
        colors: "Deep RED",
      },
      makeSettings({
        categoryDiscountPercent: 12,
        categoryFlowerType: "ROSE",
        categoryMixed: "mono",
        categoryColor: "red",
      })
    );

    expect(discount).toEqual({
      percent: 12,
      note: "Discount",
      source: "category",
    });
  });

  it("uses season cart metadata for category matching", () => {
    const discount = getCartItemDiscount(
      {
        basePriceCents: 10000,
        flowerType: "ROSE",
        isMixed: false,
        bouquetType: "SEASON",
        colors: "Deep RED",
      },
      makeSettings({
        categoryDiscountPercent: 12,
        categoryMixed: "season",
      })
    );

    expect(discount).toEqual({
      percent: 12,
      note: "Discount",
      source: "category",
    });
  });

  it("keeps cart discounts consistent for non-flower and custom items", () => {
    const settings = makeSettings({
      categoryDiscountPercent: 12,
      categoryMixed: "mono",
      globalDiscountPercent: 5,
      globalDiscountNote: "Storewide",
    });

    expect(
      getCartItemDiscount(
        {
          basePriceCents: 10000,
          catalogType: "GIFTS",
          bouquetType: "MONO",
        },
        settings
      )
    ).toEqual({ percent: 5, note: "Storewide", source: "global" });

    expect(
      getCartItemDiscount(
        {
          basePriceCents: 10000,
          isCustom: true,
          bouquetDiscountPercent: 20,
        },
        settings
      )
    ).toBeNull();
  });
});
