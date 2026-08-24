"use client";

import { useMemo, useState } from "react";
import { useFormStatus } from "react-dom";
import type { Bouquet } from "@/lib/api-types";
import AdminImageList from "@/components/admin-image-list";
import { getBouquetGalleryImages } from "@/lib/bouquet-images";

type EditableCatalogType = "BALOONS" | "GIFTS" | "EVENT_SPACE";

type TierDraft = {
  price: string;
  title: string;
  description: string;
};

type ProductWithContent = Bouquet & {
  galleryImages?: string[];
  videoUrl?: string | null;
  videoOrientation?: "HORIZONTAL" | "VERTICAL";
  tiers?: Array<{ priceCents: number; title?: string | null; description: string }>;
};

type AdminCatalogProductFormProps = {
  product?: ProductWithContent;
  catalogType: EditableCatalogType;
  action: (formData: FormData) => Promise<void>;
};

const controlClass =
  "h-11 w-full min-w-0 rounded-2xl border border-stone-200 bg-white/80 px-4 py-0 text-sm text-stone-800 outline-none focus:border-stone-400";
const textareaClass =
  "w-full min-w-0 rounded-2xl border border-stone-200 bg-white/80 px-4 py-3 text-sm text-stone-800 outline-none focus:border-stone-400";

function SubmitButton({ label }: { label: string }) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="inline-flex h-11 w-full items-center justify-center rounded-full bg-[color:var(--brand)] px-6 text-xs uppercase tracking-[0.3em] text-white transition hover:bg-[color:var(--brand-dark)] disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
    >
      {pending ? "Saving..." : label}
    </button>
  );
}

const createTier = (): TierDraft => ({ price: "", title: "", description: "" });

export default function AdminCatalogProductForm({
  product,
  catalogType,
  action,
}: AdminCatalogProductFormProps) {
  const isEventSpace = catalogType === "EVENT_SPACE";
  const supportsVideo = catalogType === "GIFTS" || isEventSpace;
  const initialImages = useMemo(() => {
    const fromApi = product?.galleryImages?.filter(Boolean) || [];
    return fromApi.length ? fromApi : product ? getBouquetGalleryImages(product) : [];
  }, [product]);
  const [tiers, setTiers] = useState<TierDraft[]>(() => {
    if (!isEventSpace) return [];
    const existing = product?.tiers || [];
    return existing.length
        ? existing.map((tier) => ({
          price: (tier.priceCents / 100).toFixed(2),
          title: tier.title || "",
          description: tier.description,
        }))
      : [];
  });
  const [error, setError] = useState("");

  const updateTier = (index: number, field: keyof TierDraft, value: string) => {
    setTiers((current) =>
      current.map((tier, tierIndex) =>
        tierIndex === index ? { ...tier, [field]: value } : tier
      )
    );
  };

  const removeTier = (index: number) => {
    setTiers((current) => current.filter((_, tierIndex) => tierIndex !== index));
  };

  const validate = (event: React.FormEvent<HTMLFormElement>) => {
    const formData = new FormData(event.currentTarget);
    const name = String(formData.get("name") || "").trim();
    const description = String(formData.get("description") || "").trim();
    const galleryImages = formData
      .getAll("galleryImages")
      .map((value) => String(value || "").trim())
      .filter(Boolean);

    if (!name || !description || !galleryImages.length) {
      event.preventDefault();
      setError("Name, description, and at least one image are required.");
      return;
    }

    if (!isEventSpace) {
      const price = Number(formData.get("price") || 0);
      if (!Number.isFinite(price) || price <= 0) {
        event.preventDefault();
        setError("Price must be greater than 0.");
        return;
      }
    }

    if (isEventSpace) {
      const invalidTier = tiers.some(
        (tier) => !tier.description.trim() || !Number.isFinite(Number(tier.price)) || Number(tier.price) < 0
      );
      if (invalidTier) {
        event.preventDefault();
        setError("Every tier needs a description and a valid price.");
        return;
      }
    }

    setError("");
  };

  const noun = isEventSpace ? "event space" : catalogType === "BALOONS" ? "balloon" : "gift";

  return (
    <form
      action={action}
      onSubmit={validate}
      className="glass relative z-10 max-w-full space-y-6 rounded-[28px] border border-white/80 p-4 sm:p-6"
    >
      {product ? <input type="hidden" name="id" value={product.id} /> : null}
      <input type="hidden" name="catalogType" value={catalogType} />
      {isEventSpace ? <input type="hidden" name="price" value="0" /> : null}

      <div className="grid gap-6 lg:grid-cols-2 lg:items-start xl:gap-8">
        <div className="min-w-0 space-y-4">
          <label className="flex flex-col gap-2 text-sm text-stone-700">
            Name
            <input name="name" defaultValue={product?.name} required className={controlClass} />
          </label>
          <label className="flex flex-col gap-2 text-sm text-stone-700">
            Description
            <textarea
              name="description"
              defaultValue={product?.description}
              rows={5}
              required
              className={textareaClass}
            />
          </label>
          {!isEventSpace ? (
            <label className="flex flex-col gap-2 text-sm text-stone-700">
              Price (USD)
              <input
                name="price"
                type="number"
                min="0.01"
                step="0.01"
                defaultValue={product ? (product.priceCents / 100).toFixed(2) : ""}
                required
                className={controlClass}
              />
            </label>
          ) : null}
          {supportsVideo ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="flex flex-col gap-2 text-sm text-stone-700 sm:col-span-2">
                YouTube video URL (optional)
                <input
                  name="videoUrl"
                  type="url"
                  defaultValue={product?.videoUrl || ""}
                  placeholder="https://www.youtube.com/watch?v=..."
                  className={controlClass}
                />
                <span className="text-xs leading-relaxed text-stone-500">
                  Only a YouTube link is embedded on the storefront.
                </span>
              </label>
              <label className="flex flex-col gap-2 text-sm text-stone-700">
                Video format
                <select
                  name="videoOrientation"
                  defaultValue={product?.videoOrientation || "HORIZONTAL"}
                  className={controlClass}
                >
                  <option value="HORIZONTAL">Horizontal</option>
                  <option value="VERTICAL">Vertical</option>
                </select>
              </label>
            </div>
          ) : null}
          {!isEventSpace ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="flex flex-col gap-2 text-sm text-stone-700">
                Discount percent
                <input
                  name="discountPercent"
                  type="number"
                  min="0"
                  max="90"
                  defaultValue={product?.discountPercent ?? 0}
                  className={controlClass}
                />
              </label>
              <label className="flex flex-col gap-2 text-sm text-stone-700">
                Discount comment
                <input
                  name="discountNote"
                  defaultValue={product?.discountNote || ""}
                  className={controlClass}
                />
              </label>
            </div>
          ) : null}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <label className="flex items-center gap-2 text-sm text-stone-700">
              <input name="isFeatured" type="checkbox" defaultChecked={product?.isFeatured} />
              Featured
            </label>
            <label className="flex items-center gap-2 text-sm text-stone-700">
              <input name="isActive" type="checkbox" defaultChecked={product ? product.isActive : true} />
              Visible in catalog
            </label>
            <label className="flex items-center gap-2 text-sm text-stone-700">
              <input name="isSoldOut" type="checkbox" defaultChecked={product?.isSoldOut} />
              Sold out
            </label>
          </div>
        </div>

        <div className="min-w-0 space-y-6">
          <AdminImageList
            name="galleryImages"
            initialImages={initialImages}
            title="Gallery images"
            description="You can add as many images as needed. The storefront shows the first six in this order."
            previewAlt={`${noun} gallery image`}
            recommendedSize="1000x1000"
          />
          {isEventSpace ? (
            <section className="space-y-3">
              <div className="space-y-1">
                <h2 className="text-lg font-semibold text-stone-900">Event tiers</h2>
                <p className="text-sm leading-relaxed text-stone-600">
                  Optional: configure the price and description for each level of the event.
                </p>
              </div>
              <div className="space-y-3">
                {tiers.map((tier, index) => (
                  <div
                    key={`tier-${index}`}
                    className="relative grid gap-3 rounded-[24px] border border-stone-200/70 bg-white/45 p-3"
                  >
                    <button
                      type="button"
                      onClick={() => removeTier(index)}
                      className="absolute right-2 top-2 inline-flex h-7 w-7 items-center justify-center rounded-full border border-stone-200 bg-white/90 text-sm text-stone-600 transition hover:border-stone-300 hover:text-stone-800"
                      aria-label={`Remove tier ${index + 1}`}
                    >
                      ×
                    </button>
                    <label className="flex flex-col gap-2 pr-8 text-sm text-stone-700">
                      Tier {index + 1} price (USD)
                      <input
                        name="tierPrice"
                        type="number"
                        min="0"
                        step="0.01"
                        value={tier.price}
                        onChange={(event) => updateTier(index, "price", event.target.value)}
                        className={controlClass}
                      />
                    </label>
                    <label className="flex flex-col gap-2 text-sm text-stone-700">
                      Title (optional)
                      <input
                        name="tierTitle"
                        value={tier.title}
                        onChange={(event) => updateTier(index, "title", event.target.value)}
                        className={controlClass}
                      />
                    </label>
                    <label className="flex flex-col gap-2 text-sm text-stone-700">
                      Description
                      <textarea
                        name="tierDescription"
                        rows={3}
                        value={tier.description}
                        onChange={(event) => updateTier(index, "description", event.target.value)}
                        className={textareaClass}
                      />
                    </label>
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={() => setTiers((current) => [...current, createTier()])}
                className="inline-flex h-10 w-full items-center justify-center rounded-full border border-stone-300 bg-white/85 px-4 text-[11px] uppercase tracking-[0.22em] text-stone-700 transition hover:border-stone-400"
              >
                Add tier
              </button>
            </section>
          ) : null}
        </div>
      </div>

      {error ? (
        <p className="rounded-2xl border border-rose-300 bg-rose-50/80 px-4 py-3 text-sm text-rose-700">
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-3">
        <SubmitButton label={`Save ${noun}`} />
        <p className="text-xs uppercase tracking-[0.24em] text-stone-500">
          Changes apply instantly
        </p>
      </div>
    </form>
  );
}
