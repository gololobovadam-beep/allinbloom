"use client";

import { useFormStatus } from "react-dom";
import type { StoreSettings } from "@/lib/api-types";
import AdminImageUpload from "@/components/admin-image-upload";
import AdminImageList from "@/components/admin-image-list";
import { getHomeGalleryImages } from "@/lib/home-images";

type AdminHomeImagesFormProps = {
  settings: StoreSettings;
  action: (formData: FormData) => Promise<void>;
};

function SubmitButton() {
  const { pending } = useFormStatus();

  return (
    <button
      type="submit"
      disabled={pending}
      className="inline-flex h-11 w-full items-center justify-center rounded-full bg-[color:var(--brand)] px-6 text-xs uppercase tracking-[0.3em] text-white transition hover:bg-[color:var(--brand-dark)] disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
    >
      {pending ? "Saving..." : "Save images"}
    </button>
  );
}

export default function AdminHomeImagesForm({
  settings,
  action,
}: AdminHomeImagesFormProps) {
  return (
    <form
      action={action}
      className="relative z-10 max-w-full space-y-6"
    >
      <section className="space-y-4 rounded-[24px] border border-white/80 bg-white/60 p-4 sm:p-5">
        <h2 className="text-lg font-semibold text-stone-900">Hero image</h2>
        <AdminImageUpload
          name="homeHeroImage"
          urlLabel="Hero image URL"
          previewAlt="Homepage hero preview"
          defaultValue={settings.homeHeroImage}
          recommendedSize="1200x1500"
        />
      </section>

      <section className="space-y-4 rounded-[24px] border border-white/80 bg-white/60 p-4 sm:p-5">
        <AdminImageList
          name="homeGalleryImages"
          initialImages={getHomeGalleryImages(settings)}
          title="Atelier gallery images"
          description="Add any number of images and use the arrows to choose their order. Only the first six are displayed on the homepage."
          previewAlt="Homepage gallery image"
          recommendedSize="1000x1000"
          columns={2}
        />
      </section>

      <section className="space-y-4 rounded-[24px] border border-white/80 bg-white/60 p-4 sm:p-5">
        <h2 className="text-lg font-semibold text-stone-900">
          Shop all category images
        </h2>
        <div className="grid gap-6 lg:grid-cols-2">
          <AdminImageUpload
            name="shopAllImageFlowers"
            urlLabel="Flowers category image URL"
            previewAlt="Flowers category image preview"
            defaultValue={settings.shopAllImageFlowers}
            recommendedSize="1000x1000"
          />
          <AdminImageUpload
            name="shopAllImageBalloons"
            urlLabel="Balloons category image URL"
            previewAlt="Balloons category image preview"
            defaultValue={settings.shopAllImageBalloons}
            recommendedSize="1000x1000"
          />
          <AdminImageUpload
            name="shopAllImageGiftBox"
            urlLabel="Gift Box category image URL"
            previewAlt="Gift Box category image preview"
            defaultValue={settings.shopAllImageGiftBox}
            recommendedSize="1000x1000"
          />
          <AdminImageUpload
            name="shopAllImageEventSpace"
            urlLabel="Event Space category image URL"
            previewAlt="Event Space category image preview"
            defaultValue={settings.shopAllImageEventSpace}
            recommendedSize="1000x1000"
          />
        </div>
      </section>

      <section className="space-y-4 rounded-[24px] border border-white/80 bg-white/60 p-4 sm:p-5">
        <h2 className="text-lg font-semibold text-stone-900">
          Flowers category images
        </h2>
        <div className="grid gap-6 lg:grid-cols-2">
          <AdminImageUpload
            name="catalogCategoryImageMono"
            urlLabel="Catalog Mono category image URL"
            previewAlt="Catalog mono category image preview"
            defaultValue={settings.catalogCategoryImageMono}
            recommendedSize="1000x1000"
          />
          <AdminImageUpload
            name="catalogCategoryImageMixed"
            urlLabel="Catalog Mixed category image URL"
            previewAlt="Catalog mixed category image preview"
            defaultValue={settings.catalogCategoryImageMixed}
            recommendedSize="1000x1000"
          />
          <AdminImageUpload
            name="catalogCategoryImageSeason"
            urlLabel="Catalog Seasonal category image URL"
            previewAlt="Catalog seasonal category image preview"
            defaultValue={settings.catalogCategoryImageSeason}
            recommendedSize="1000x1000"
          />
          <AdminImageUpload
            name="catalogCategoryImageAll"
            urlLabel="Catalog All category image URL"
            previewAlt="Catalog all category image preview"
            defaultValue={settings.catalogCategoryImageAll}
            recommendedSize="1000x1000"
          />
        </div>
      </section>

      <div className="flex flex-wrap gap-3">
        <SubmitButton />
        <p className="text-xs uppercase tracking-[0.24em] text-stone-500">
          Applies to homepage and catalog category tiles
        </p>
      </div>
    </form>
  );
}
