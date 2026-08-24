import { BOUQUET_TYPES, FLOWER_TYPES } from "@/lib/constants";
import { normalizeColorCsv } from "@/lib/colors";
import {
  clampFlowerQuantity,
  FLOWER_QUANTITY_MIN,
} from "@/lib/flower-quantity";

export type BouquetFormPayload = {
  name: string;
  description: string;
  priceCents: number;
  flowerType: (typeof FLOWER_TYPES)[number];
  style: string;
  bouquetType: (typeof BOUQUET_TYPES)[number];
  colors: string;
  isMixed: boolean;
  isFeatured: boolean;
  isActive: boolean;
  isSoldOut: boolean;
  allowFlowerQuantity: boolean;
  defaultFlowerQuantity: number;
  discountPercent: number;
  discountNote: string | null;
  galleryImages: string[];
  image: string;
  image2: string | null;
  image3: string | null;
  image4: string | null;
  image5: string | null;
  image6: string | null;
};

export type CatalogProductFormPayload = {
  catalogType: "BALOONS" | "GIFTS" | "EVENT_SPACE";
  name: string;
  description: string;
  priceCents: number;
  currency: "USD";
  flowerType: (typeof FLOWER_TYPES)[number];
  style: string;
  bouquetType: "MONO";
  colors: string;
  isMixed: false;
  isFeatured: boolean;
  isActive: boolean;
  isSoldOut: boolean;
  allowFlowerQuantity: false;
  defaultFlowerQuantity: number;
  discountPercent: number;
  discountNote: string | null;
  galleryImages: string[];
  image: string;
  image2: string | null;
  image3: string | null;
  image4: string | null;
  image5: string | null;
  image6: string | null;
  videoUrl: string | null;
  videoOrientation: "HORIZONTAL" | "VERTICAL";
  tiers: Array<{ priceCents: number; title: string | null; description: string }>;
};

const normalizeEnum = <T extends readonly string[]>(
  value: string | null,
  allowed: T,
  fallback: T[number]
) => {
  if (!value) return fallback;
  const upper = value.toUpperCase();
  return (allowed as readonly string[]).includes(upper) ? (upper as T[number]) : fallback;
};

const parseFlowerTypes = (formData: FormData): (typeof FLOWER_TYPES)[number][] => {
  const valid = new Set<string>(FLOWER_TYPES);
  const parsed = formData
    .getAll("flowerTypes")
    .map((value) => String(value || "").trim().toUpperCase())
    .filter((value): value is (typeof FLOWER_TYPES)[number] => valid.has(value));

  const unique = parsed.filter((value, index) => parsed.indexOf(value) === index);
  if (unique.length) {
    return unique.slice(0, 3);
  }

  const fallbackCsv = String(formData.get("style") || "");
  const fallbackFromCsv = fallbackCsv
    .split(",")
    .map((value) => value.trim().toUpperCase())
    .filter((value): value is (typeof FLOWER_TYPES)[number] => valid.has(value))
    .filter((value, index, list) => list.indexOf(value) === index)
    .slice(0, 3);
  if (fallbackFromCsv.length) {
    return fallbackFromCsv;
  }

  const fallbackPrimary = normalizeEnum(
    String(formData.get("flowerType")),
    FLOWER_TYPES,
    FLOWER_TYPES[0]
  );
  return [fallbackPrimary];
};

export const parseBouquetForm = (formData: FormData): BouquetFormPayload => {
  const normalizeOptionalImage = (value: FormDataEntryValue | null) => {
    const normalized = String(value || "").trim();
    return normalized || null;
  };

  const name = String(formData.get("name") || "").trim();
  const description = String(formData.get("description") || "").trim();
  const price = Number(formData.get("price") || 0);
  const galleryImages = formData
    .getAll("galleryImages")
    .map((value) => String(value || "").trim())
    .filter(Boolean)
    .filter((value, index, list) => list.indexOf(value) === index);
  const rawImage = String(formData.get("image") || "").trim();
  const image = galleryImages[0] || rawImage || "/images/bouquet-1.webp";
  const resolvedGalleryImages = galleryImages.length ? galleryImages : [image];
  const colors = normalizeColorCsv(String(formData.get("colors") || ""));
  const discountPercent = Math.min(
    90,
    Math.max(0, Math.round(Number(formData.get("discountPercent") || 0)))
  );
  const discountNote = String(formData.get("discountNote") || "").trim();
  const normalizedDiscountNote =
    discountPercent > 0 ? discountNote || "Discount" : null;
  const flowerTypes = parseFlowerTypes(formData);
  const bouquetType = normalizeEnum(
    String(formData.get("bouquetType")),
    BOUQUET_TYPES,
    formData.get("isMixed") === "on" ? "MIXED" : "MONO"
  );
  const allowFlowerQuantity = formData.get("allowFlowerQuantity") === "on";
  const defaultFlowerQuantity = allowFlowerQuantity
    ? clampFlowerQuantity(Number(formData.get("defaultFlowerQuantity")))
    : FLOWER_QUANTITY_MIN;

  return {
    name,
    description,
    priceCents: Math.max(0, Math.round(price * 100)),
    flowerType: flowerTypes[0],
    style: flowerTypes.join(", "),
    bouquetType,
    colors,
    isMixed: bouquetType === "MIXED",
    isFeatured: formData.get("isFeatured") === "on",
    isActive: formData.get("isActive") === "on",
    isSoldOut: formData.get("isSoldOut") === "on",
    allowFlowerQuantity,
    defaultFlowerQuantity,
    discountPercent,
    discountNote: normalizedDiscountNote,
    galleryImages: resolvedGalleryImages,
    image,
    image2: resolvedGalleryImages[1] || normalizeOptionalImage(formData.get("image2")),
    image3: resolvedGalleryImages[2] || normalizeOptionalImage(formData.get("image3")),
    image4: resolvedGalleryImages[3] || normalizeOptionalImage(formData.get("image4")),
    image5: resolvedGalleryImages[4] || normalizeOptionalImage(formData.get("image5")),
    image6: resolvedGalleryImages[5] || normalizeOptionalImage(formData.get("image6")),
  };
};

const parseGalleryImages = (formData: FormData) =>
  formData
    .getAll("galleryImages")
    .map((value) => String(value || "").trim())
    .filter(Boolean)
    .filter((value, index, list) => list.indexOf(value) === index);

/** Shared form parser for Gifts and Event Space. Product price, image URLs and
 * availability are still authoritatively revalidated by FastAPI. */
export const parseCatalogProductForm = (
  formData: FormData
): CatalogProductFormPayload => {
  const rawCatalogType = String(formData.get("catalogType") || "")
    .trim()
    .toUpperCase();
  const catalogType =
    rawCatalogType === "EVENT_SPACE"
      ? "EVENT_SPACE"
      : rawCatalogType === "BALOONS"
      ? "BALOONS"
      : "GIFTS";
  const galleryImages = parseGalleryImages(formData);
  const fallbackImage = galleryImages[0] || "/images/mock.webp";
  const rawPrice = Number(formData.get("price") || 0);
  const discountPercent = Math.min(
    90,
    Math.max(0, Math.round(Number(formData.get("discountPercent") || 0)))
  );
  const discountNote = String(formData.get("discountNote") || "").trim();
  const rawTierPrices = formData.getAll("tierPrice");
  const rawTierTitles = formData.getAll("tierTitle");
  const rawTierDescriptions = formData.getAll("tierDescription");
  const videoOrientation =
    String(formData.get("videoOrientation") || "").trim().toUpperCase() === "VERTICAL"
      ? "VERTICAL"
      : "HORIZONTAL";
  const tiers = rawTierDescriptions
    .map((description, index) => {
      const normalizedDescription = String(description || "").trim();
      const price = Number(rawTierPrices[index] || 0);
      if (!normalizedDescription || !Number.isFinite(price) || price < 0) {
        return null;
      }
      return {
        priceCents: Math.max(0, Math.round(price * 100)),
        title: String(rawTierTitles[index] || "").trim() || null,
        description: normalizedDescription,
      };
    })
    .filter(
      (tier): tier is { priceCents: number; title: string | null; description: string } =>
        Boolean(tier)
    );

  return {
    catalogType,
    name: String(formData.get("name") || "").trim(),
    description: String(formData.get("description") || "").trim(),
    priceCents:
      catalogType === "EVENT_SPACE"
        ? 0
        : Math.max(0, Math.round((Number.isFinite(rawPrice) ? rawPrice : 0) * 100)),
    currency: "USD",
    // The unified legacy table keeps these floral columns non-null. They are
    // neither rendered nor used for gifts and event-space cards.
    flowerType: FLOWER_TYPES[0],
    style: "",
    bouquetType: "MONO",
    colors: "",
    isMixed: false,
    isFeatured: formData.get("isFeatured") === "on",
    isActive: formData.get("isActive") === "on",
    isSoldOut: formData.get("isSoldOut") === "on",
    allowFlowerQuantity: false,
    defaultFlowerQuantity: FLOWER_QUANTITY_MIN,
    discountPercent: catalogType === "EVENT_SPACE" ? 0 : discountPercent,
    discountNote:
      catalogType === "EVENT_SPACE" || discountPercent <= 0
        ? null
        : discountNote || "Discount",
    galleryImages: galleryImages.length ? galleryImages : [fallbackImage],
    image: fallbackImage,
    image2: galleryImages[1] || null,
    image3: galleryImages[2] || null,
    image4: galleryImages[3] || null,
    image5: galleryImages[4] || null,
    image6: galleryImages[5] || null,
    videoUrl:
      catalogType === "BALOONS"
        ? null
        : String(formData.get("videoUrl") || "").trim() || null,
    videoOrientation: catalogType === "BALOONS" ? "HORIZONTAL" : videoOrientation,
    tiers: catalogType === "EVENT_SPACE" ? tiers : [],
  };
};

