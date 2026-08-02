"use client";

import AddToCartControls from "@/components/add-to-cart-controls";
import MosaicGallery from "@/components/mosaic-gallery";
import YouTubeVideoModal from "@/components/youtube-video-modal";
import { getBouquetGalleryImages } from "@/lib/bouquet-images";
import { formatMoney } from "@/lib/format";
import { applyPercentDiscount } from "@/lib/pricing";
import { SITE_INSTAGRAM } from "@/lib/site";
import type { Bouquet, BouquetPricing } from "@/lib/api-types";

export type EditorialProductKind = "gift" | "event";

type ProductCardProps = {
  product: Bouquet;
  kind: EditorialProductKind;
  pricing: BouquetPricing;
  firstOrderDiscount?: {
    percent: number;
    note: string;
  } | null;
};

function GiftPrice({
  pricing,
  firstOrderDiscount,
}: Pick<ProductCardProps, "pricing" | "firstOrderDiscount">) {
  const appliedDiscount = pricing.discount || firstOrderDiscount;
  const finalPriceCents = pricing.discount
    ? pricing.finalPriceCents
    : firstOrderDiscount
      ? applyPercentDiscount(pricing.originalPriceCents, firstOrderDiscount.percent)
      : pricing.originalPriceCents;

  if (!appliedDiscount) {
    return (
      <p className="text-xl font-semibold leading-none text-stone-900 sm:text-2xl">
        {formatMoney(pricing.originalPriceCents)}
      </p>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
      <p className="text-xl font-semibold leading-none text-[color:var(--brand)] sm:text-2xl">
        {formatMoney(finalPriceCents)}
      </p>
      <span className="text-sm text-stone-400 line-through">
        {formatMoney(pricing.originalPriceCents)}
      </span>
      <span className="rounded-full bg-[color:var(--brand)]/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[color:var(--brand)]">
        -{appliedDiscount.percent}%
      </span>
    </div>
  );
}

/**
 * Large editorial card used by the Gifts and Event Space catalogs. It shares
 * the existing gallery/lightbox, cart controls, button language, and modal
 * instead of introducing a separate interaction system.
 */
export default function ProductCard({
  product,
  kind,
  pricing,
  firstOrderDiscount = null,
}: ProductCardProps) {
  const isEvent = kind === "event";
  const galleryImages = getBouquetGalleryImages(product);
  const tiers = product.tiers || [];
  const eyebrow = isEvent ? "Event space" : "Gift";

  return (
    <article className="glass overflow-hidden rounded-[28px] border border-white/80 p-3 shadow-sm sm:p-5 lg:p-6">
      <div className="grid min-w-0 gap-5 lg:grid-cols-[minmax(0,1.02fr)_minmax(0,0.98fr)] lg:gap-8">
        <MosaicGallery
          images={galleryImages}
          alt={`${product.name} gallery`}
          visibleLimit={6}
          className="lg:sticky lg:top-24 lg:self-start"
        />
        <div className="flex min-w-0 flex-col gap-5 py-1 sm:gap-6 sm:py-2">
          <div className="min-w-0 space-y-3">
            <p className="text-xs uppercase tracking-[0.3em] text-stone-500">
              {eyebrow}
            </p>
            <h2 className="break-words text-2xl font-semibold leading-tight text-stone-900 sm:text-3xl lg:text-4xl">
              {product.name}
            </h2>
            <p className="whitespace-pre-line break-words text-sm leading-relaxed text-stone-600 sm:text-base">
              {product.description}
            </p>
          </div>

          {product.videoUrl ? (
            <YouTubeVideoModal
              videoUrl={product.videoUrl}
              title={`${product.name} video`}
              label="Watch video"
              className="self-start"
            />
          ) : null}

          {isEvent ? (
            <div className="space-y-3 border-t border-stone-200/80 pt-5">
              <p className="text-xs uppercase tracking-[0.28em] text-stone-500">
                Event tiers
              </p>
              {tiers.length ? (
                <ul className="space-y-2.5">
                  {tiers.map((tier, index) => (
                    <li
                      key={tier.id || `${product.id}-tier-${index}`}
                      className="grid min-w-0 gap-2 rounded-[20px] border border-stone-200/80 bg-white/55 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start sm:gap-4"
                    >
                      <p className="min-w-0 break-words text-sm leading-relaxed text-stone-600">
                        {tier.description}
                      </p>
                      <p className="text-base font-semibold text-stone-900 sm:text-right">
                        {formatMoney(tier.priceCents)}
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm leading-relaxed text-stone-600">
                  Contact our studio for current event options.
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-4 border-t border-stone-200/80 pt-5">
              <GiftPrice
                pricing={pricing}
                firstOrderDiscount={firstOrderDiscount}
              />
              {product.isSoldOut ? (
                <div className="w-full rounded-full border border-stone-200 bg-stone-100 px-4 py-2.5 text-center text-xs uppercase tracking-[0.24em] text-stone-500">
                  Sold out
                </div>
              ) : (
                <AddToCartControls
                  item={{
                    id: product.id,
                    name: product.name,
                    priceCents: product.priceCents,
                    image: product.image,
                    discountPercent: product.discountPercent,
                    discountNote: product.discountNote || undefined,
                    flowerType: product.flowerType,
                    colors: product.colors,
                    isMixed: product.isMixed,
                    bouquetType: product.bouquetType,
                    catalogType: product.catalogType || "GIFTS",
                  }}
                />
              )}
            </div>
          )}

          {isEvent ? (
            product.isSoldOut ? (
              <div className="w-full rounded-full border border-stone-200 bg-stone-100 px-4 py-3 text-center text-xs uppercase tracking-[0.24em] text-stone-500 sm:w-auto sm:self-start">
                Sold out
              </div>
            ) : (
              <a
                href={SITE_INSTAGRAM}
                target="_blank"
                rel="noreferrer"
                className="inline-flex min-h-11 w-full items-center justify-center rounded-full bg-[color:var(--brand)] px-5 py-3 text-center text-xs font-semibold uppercase tracking-[0.24em] text-white transition hover:bg-[color:var(--brand-dark)] sm:w-auto sm:self-start"
              >
                Book now
              </a>
            )
          ) : null}
        </div>
      </div>
    </article>
  );
}
