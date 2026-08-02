import { describe, expect, it } from "vitest";

import type { StoreSettings } from "@/lib/api-types";
import {
  DEFAULT_CATALOG_CATEGORY_IMAGES,
  DEFAULT_HOME_GALLERY_IMAGES,
  DEFAULT_HOME_HERO_IMAGE,
  getCatalogCategoryImages,
  getHomeGalleryImages,
  getHomeHeroImage,
  getVisibleHomeGalleryImages,
} from "@/lib/home-images";

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
  homeHeroImage: "/images/custom-hero.webp",
  homeGalleryImage1: "/images/custom-1.webp",
  homeGalleryImage2: "/images/custom-2.webp",
  homeGalleryImage3: "/images/custom-3.webp",
  homeGalleryImage4: "/images/custom-4.webp",
  homeGalleryImage5: "/images/custom-5.webp",
  homeGalleryImage6: "/images/custom-6.webp",
  catalogCategoryImageMono: "/images/custom-mono.webp",
  catalogCategoryImageMixed: "/images/custom-mixed.webp",
  catalogCategoryImageSeason: "/images/custom-season.webp",
  catalogCategoryImageAll: "/images/custom-all.webp",
};

const makeSettings = (overrides: Partial<StoreSettings> = {}): StoreSettings => ({
  ...baseSettings,
  ...overrides,
});

describe("home image fallback helpers", () => {
  it("uses default hero image when configured value is empty", () => {
    const heroImage = getHomeHeroImage(makeSettings({ homeHeroImage: "   " }));
    expect(heroImage).toBe(DEFAULT_HOME_HERO_IMAGE);
  });

  it("builds gallery images with per-slot fallback", () => {
    const gallery = getHomeGalleryImages(
      makeSettings({
        homeGalleryImage1: " /images/hero.webp ",
        homeGalleryImage2: "",
        homeGalleryImage3: "   ",
      })
    );

    expect(gallery).toEqual([
      "/images/hero.webp",
      DEFAULT_HOME_GALLERY_IMAGES[1],
      DEFAULT_HOME_GALLERY_IMAGES[2],
      "/images/custom-4.webp",
      "/images/custom-5.webp",
      "/images/custom-6.webp",
    ]);
  });

  it("returns catalog category image defaults when values are blank", () => {
    const images = getCatalogCategoryImages(
      makeSettings({
        catalogCategoryImageMono: "  ",
        catalogCategoryImageMixed: "",
      })
    );

    expect(images).toEqual({
      mono: DEFAULT_CATALOG_CATEGORY_IMAGES.mono,
      mixed: DEFAULT_CATALOG_CATEGORY_IMAGES.mixed,
      season: "/images/custom-season.webp",
      all: "/images/custom-all.webp",
    });
  });

  it("keeps arbitrary admin gallery images but exposes only the first six publicly", () => {
    const homeGalleryImages = Array.from(
      { length: 8 },
      (_, index) => `/images/gallery-${index + 1}.webp`
    );
    const settings = makeSettings({ homeGalleryImages });

    expect(getHomeGalleryImages(settings)).toEqual(homeGalleryImages);
    expect(getVisibleHomeGalleryImages(settings)).toEqual(homeGalleryImages.slice(0, 6));
  });
});
