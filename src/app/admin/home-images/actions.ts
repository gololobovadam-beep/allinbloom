"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { requireAdmin } from "@/lib/auth-session";
import { updateStoreSettings } from "@/lib/data/settings";
import {
  DEFAULT_CATALOG_CATEGORY_IMAGES,
  DEFAULT_HOME_GALLERY_IMAGES,
  DEFAULT_HOME_HERO_IMAGE,
} from "@/lib/home-images";

const parseImageUrl = (value: FormDataEntryValue | null, fallback: string) => {
  const parsed = String(value || "").trim();
  return parsed || fallback;
};

export async function updateHomeImages(formData: FormData) {
  await requireAdmin();

  const homeGalleryImages = formData
    .getAll("homeGalleryImages")
    .map((value) => String(value || "").trim())
    .filter(Boolean)
    .filter((value, index, values) => values.indexOf(value) === index);

  await updateStoreSettings({
    homeHeroImage: parseImageUrl(
      formData.get("homeHeroImage"),
      DEFAULT_HOME_HERO_IMAGE
    ),
    homeGalleryImages: homeGalleryImages.length
      ? homeGalleryImages
      : [...DEFAULT_HOME_GALLERY_IMAGES],
    catalogCategoryImageMono: parseImageUrl(
      formData.get("catalogCategoryImageMono"),
      DEFAULT_CATALOG_CATEGORY_IMAGES.mono
    ),
    catalogCategoryImageMixed: parseImageUrl(
      formData.get("catalogCategoryImageMixed"),
      DEFAULT_CATALOG_CATEGORY_IMAGES.mixed
    ),
    catalogCategoryImageSeason: parseImageUrl(
      formData.get("catalogCategoryImageSeason"),
      DEFAULT_CATALOG_CATEGORY_IMAGES.season
    ),
    catalogCategoryImageAll: parseImageUrl(
      formData.get("catalogCategoryImageAll"),
      DEFAULT_CATALOG_CATEGORY_IMAGES.all
    ),
  });

  revalidatePath("/admin/home-images");
  revalidatePath("/catalog");
  revalidatePath("/");
  redirect("/admin/home-images?toast=home-images-saved");
}
