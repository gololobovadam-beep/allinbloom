import { describe, expect, it } from "vitest";

import { parseBouquetForm, parseCatalogProductForm } from "@/lib/bouquet-form";
import { BOUQUET_TYPES, FLOWER_TYPES } from "@/lib/constants";

const makeFormData = (entries: Record<string, string | string[]>) => {
  const formData = new FormData();
  for (const [key, value] of Object.entries(entries)) {
    if (Array.isArray(value)) {
      for (const item of value) {
        formData.append(key, item);
      }
      continue;
    }
    formData.set(key, value);
  }
  return formData;
};

describe("parseBouquetForm", () => {
  it("normalizes and parses standard form values", () => {
    const payload = parseBouquetForm(
      makeFormData({
        name: "  Garden Mood  ",
        description: "  Fresh seasonal flowers  ",
        price: "45.555",
        flowerTypes: ["rose", "hydrangeas"],
        bouquetType: "mixed",
        colors: "  Blush, Ivory ",
        isFeatured: "on",
        isActive: "on",
        isSoldOut: "on",
        allowFlowerQuantity: "on",
        defaultFlowerQuantity: "100",
        discountPercent: "14.7",
        discountNote: "  Spring promo ",
        image: " /images/custom.webp ",
      })
    );

    expect(payload).toEqual({
      name: "Garden Mood",
      description: "Fresh seasonal flowers",
      priceCents: 4556,
      flowerType: "ROSE",
      style: "ROSE, HYDRANGEAS",
      bouquetType: "MIXED",
      colors: "pink, white",
      isMixed: true,
      isFeatured: true,
      isActive: true,
      isSoldOut: true,
      allowFlowerQuantity: true,
      defaultFlowerQuantity: 100,
      discountPercent: 15,
      discountNote: "Spring promo",
      galleryImages: ["/images/custom.webp"],
      image: "/images/custom.webp",
      image2: null,
      image3: null,
      image4: null,
      image5: null,
      image6: null,
    });
  });

  it("uses fallback values and clamps numbers", () => {
    const payload = parseBouquetForm(
      makeFormData({
        name: "Fallback bouquet",
        description: "desc",
        price: "-20",
        flowerType: "unknown",
        bouquetType: "unknown",
        colors: "  ",
        discountPercent: "999",
        discountNote: "",
        image: " ",
      })
    );

    expect(payload.flowerType).toBe(FLOWER_TYPES[0]);
    expect(payload.style).toBe(FLOWER_TYPES[0]);
    expect(payload.bouquetType).toBe(BOUQUET_TYPES[0]);
    expect(payload.priceCents).toBe(0);
    expect(payload.allowFlowerQuantity).toBe(false);
    expect(payload.defaultFlowerQuantity).toBe(1);
    expect(payload.isSoldOut).toBe(false);
    expect(payload.discountPercent).toBe(90);
    expect(payload.discountNote).toBe("Discount");
    expect(payload.image).toBe("/images/bouquet-1.webp");
    expect(payload.galleryImages).toEqual(["/images/bouquet-1.webp"]);
    expect(payload.image2).toBeNull();
    expect(payload.image3).toBeNull();
    expect(payload.image4).toBeNull();
    expect(payload.image5).toBeNull();
    expect(payload.image6).toBeNull();
  });

  it("drops discount note when discount is disabled", () => {
    const payload = parseBouquetForm(
      makeFormData({
        name: "No promo",
        description: "desc",
        price: "100",
        flowerTypes: ["rose"],
        bouquetType: "mono",
        colors: "red",
        allowFlowerQuantity: "on",
        discountPercent: "-4",
        discountNote: "Should be ignored",
      })
    );

    expect(payload.discountPercent).toBe(0);
    expect(payload.discountNote).toBeNull();
    expect(payload.allowFlowerQuantity).toBe(true);
    expect(payload.defaultFlowerQuantity).toBe(1);
  });

  it("normalizes additional gallery image URLs", () => {
    const payload = parseBouquetForm(
      makeFormData({
        name: "Gallery bouquet",
        description: "desc",
        price: "75",
        flowerTypes: ["rose", "tulip", "orchid", "peony"],
        bouquetType: "season",
        colors: "white",
        allowFlowerQuantity: "on",
        image: "/images/main.webp",
        image2: " /images/2.webp ",
        image3: " ",
        image4: "/images/4.webp",
        image5: "",
        image6: "/images/6.webp",
      })
    );

    expect(payload.flowerType).toBe("ROSE");
    expect(payload.style).toBe("ROSE, TULIP, ORCHID");
    expect(payload.bouquetType).toBe("SEASON");
    expect(payload.allowFlowerQuantity).toBe(true);
    expect(payload.defaultFlowerQuantity).toBe(1);
    expect(payload.image).toBe("/images/main.webp");
    expect(payload.image2).toBe("/images/2.webp");
    expect(payload.image3).toBeNull();
    expect(payload.image4).toBe("/images/4.webp");
    expect(payload.image5).toBeNull();
    expect(payload.image6).toBe("/images/6.webp");
    expect(payload.galleryImages).toEqual(["/images/main.webp"]);
  });

  it("keeps an arbitrary ordered gallery and synchronizes the legacy first six slots", () => {
    const payload = parseBouquetForm(
      makeFormData({
        name: "Large gallery",
        description: "desc",
        price: "75",
        flowerTypes: ["rose"],
        bouquetType: "mono",
        colors: "white",
        galleryImages: [
          "/images/1.webp",
          "/images/2.webp",
          "/images/3.webp",
          "/images/4.webp",
          "/images/5.webp",
          "/images/6.webp",
          "/images/7.webp",
        ],
      })
    );

    expect(payload.galleryImages).toHaveLength(7);
    expect(payload.image).toBe("/images/1.webp");
    expect(payload.image6).toBe("/images/6.webp");
  });
});

describe("parseCatalogProductForm", () => {
  it("creates a valid gift payload for the FastAPI catalog endpoint", () => {
    const payload = parseCatalogProductForm(
      makeFormData({
        catalogType: "GIFTS",
        name: "Gift box",
        description: "A thoughtful gift",
        price: "95",
        galleryImages: "/images/gift-box.webp",
        isActive: "on",
      })
    );

    expect(payload).toMatchObject({
      catalogType: "GIFTS",
      name: "Gift box",
      priceCents: 9500,
      image: "/images/gift-box.webp",
      galleryImages: ["/images/gift-box.webp"],
      isActive: true,
      allowFlowerQuantity: false,
      tiers: [],
    });
  });
});
