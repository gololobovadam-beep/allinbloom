import type { StoreSettings } from "@/lib/api-types";

export const DEFAULT_HOME_HERO_IMAGE = "/images/hero-bouquet.webp";
export const DEFAULT_HOME_GALLERY_IMAGES = [
  "/images/bouquet-1.webp",
  "/images/bouquet-2.webp",
  "/images/bouquet-3.webp",
  "/images/bouquet-4.webp",
  "/images/bouquet-5.webp",
  "/images/bouquet-6.webp",
] as const;
export const DEFAULT_CATALOG_CATEGORY_IMAGES = {
  mono: "/images/bouquet-7.webp",
  mixed: "/images/bouquet-5.webp",
  season: "/images/bouquet-2.webp",
  all: "/images/hero-bouquet.webp",
} as const;

const coerceImageUrl = (value: string | null | undefined, fallback: string) => {
  const trimmed = String(value || "").trim();
  return trimmed || fallback;
};

export const getHomeHeroImage = (settings: StoreSettings) =>
  coerceImageUrl(settings.homeHeroImage, DEFAULT_HOME_HERO_IMAGE);

export const getHomeGalleryImages = (settings: StoreSettings) => {
  const relationImages = (settings.homeGalleryImages || [])
    .map((value) => String(value || "").trim())
    .filter(Boolean)
    .filter((value, index, values) => values.indexOf(value) === index);
  if (relationImages.length) return relationImages;

  return [
    coerceImageUrl(settings.homeGalleryImage1, DEFAULT_HOME_GALLERY_IMAGES[0]),
    coerceImageUrl(settings.homeGalleryImage2, DEFAULT_HOME_GALLERY_IMAGES[1]),
    coerceImageUrl(settings.homeGalleryImage3, DEFAULT_HOME_GALLERY_IMAGES[2]),
    coerceImageUrl(settings.homeGalleryImage4, DEFAULT_HOME_GALLERY_IMAGES[3]),
    coerceImageUrl(settings.homeGalleryImage5, DEFAULT_HOME_GALLERY_IMAGES[4]),
    coerceImageUrl(settings.homeGalleryImage6, DEFAULT_HOME_GALLERY_IMAGES[5]),
  ];
};

export const getVisibleHomeGalleryImages = (settings: StoreSettings) =>
  getHomeGalleryImages(settings).slice(0, 6);

export const getCatalogCategoryImages = (settings: StoreSettings) => ({
  mono: coerceImageUrl(
    settings.catalogCategoryImageMono,
    DEFAULT_CATALOG_CATEGORY_IMAGES.mono
  ),
  mixed: coerceImageUrl(
    settings.catalogCategoryImageMixed,
    DEFAULT_CATALOG_CATEGORY_IMAGES.mixed
  ),
  season: coerceImageUrl(
    settings.catalogCategoryImageSeason,
    DEFAULT_CATALOG_CATEGORY_IMAGES.season
  ),
  all: coerceImageUrl(
    settings.catalogCategoryImageAll,
    DEFAULT_CATALOG_CATEGORY_IMAGES.all
  ),
});
