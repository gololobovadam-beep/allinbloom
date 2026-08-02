import type { Bouquet } from "@/lib/api-types";

type BouquetImageFields = Pick<
  Bouquet,
  | "image"
  | "image2"
  | "image3"
  | "image4"
  | "image5"
  | "image6"
  | "galleryImages"
>;

const uniqueImages = (values: Array<string | null | undefined>) =>
  values
    .map((value) => String(value || "").trim())
    .filter(Boolean)
    .filter((value, index, all) => all.indexOf(value) === index);

/**
 * Returns the full ordered gallery for editing. Relation-backed gallery images
 * take precedence over the six historical image fields.
 */
export const getBouquetGalleryImages = (bouquet: BouquetImageFields): string[] => {
  const relationImages = uniqueImages(bouquet.galleryImages || []);
  if (relationImages.length) return relationImages;

  return uniqueImages([
    bouquet.image,
    bouquet.image2,
    bouquet.image3,
    bouquet.image4,
    bouquet.image5,
    bouquet.image6,
  ]);
};

/** The storefront deliberately displays and lightboxes only the first six. */
export const getVisibleBouquetGalleryImages = (
  bouquet: BouquetImageFields,
  limit = 6
) => getBouquetGalleryImages(bouquet).slice(0, Math.max(1, limit));
