"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import AddToCartControls from "@/components/add-to-cart-controls";
import MosaicGallery from "@/components/mosaic-gallery";
import { getYouTubeVideoId } from "@/components/youtube-video-modal";
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
      <p className="text-left text-xl font-semibold leading-none text-stone-900 sm:text-2xl">
        {formatMoney(pricing.originalPriceCents)}
      </p>
    );
  }

  return (
    <div className="flex flex-wrap items-center justify-start gap-x-2 gap-y-1">
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

function EventBookingAction({ isSoldOut }: { isSoldOut: boolean }) {
  if (isSoldOut) {
    return (
      <div className="w-full rounded-full border border-stone-200 bg-stone-100 px-4 py-3 text-center text-xs uppercase tracking-[0.24em] text-stone-500 sm:w-auto">
        Sold out
      </div>
    );
  }

  return (
    <a
      href={SITE_INSTAGRAM}
      target="_blank"
      rel="noreferrer"
      className="inline-flex min-h-11 w-full items-center justify-center rounded-full bg-[color:var(--brand)] px-5 py-3 text-center text-xs font-semibold uppercase tracking-[0.24em] text-white transition hover:bg-[color:var(--brand-dark)] sm:w-auto"
    >
      Book now
    </a>
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
  const videoId = getYouTubeVideoId(product.videoUrl);
  const tiers = product.tiers || [];
  const hasSingleEventTier = isEvent && tiers.length === 1;
  const hasInlineEventAction = isEvent && tiers.length < 2;
  const tierWidthClass =
    tiers.length === 1
      ? "w-full max-w-xl sm:max-w-[70%] lg:max-w-[33.333%]"
      : tiers.length === 2
        ? "w-full sm:w-[calc(50%-0.3125rem)] lg:w-[calc(33.333%-0.4167rem)]"
        : tiers.length === 3
          ? "w-full sm:w-[calc(50%-0.3125rem)] lg:w-[calc(33.333%-0.4167rem)]"
          : "w-full sm:w-[calc(50%-0.3125rem)] lg:w-[calc(33.333%-0.4167rem)] xl:w-[calc(25%-0.46875rem)]";
  const mediaRef = useRef<HTMLDivElement | null>(null);
  const [mediaHeight, setMediaHeight] = useState(0);

  useEffect(() => {
    const media = mediaRef.current;
    if (!media) return;

    const updateHeight = () => {
      const nextHeight = Math.round(media.getBoundingClientRect().height);
      setMediaHeight((currentHeight) =>
        currentHeight === nextHeight ? currentHeight : nextHeight
      );
    };

    updateHeight();
    const observer = new ResizeObserver(updateHeight);
    observer.observe(media);
    return () => observer.disconnect();
  }, [videoId]);

  const mediaHeightStyle = mediaHeight
    ? ({ "--editorial-media-height": `${mediaHeight}px` } as CSSProperties)
    : undefined;
  const renderTier = (
    tier: (typeof tiers)[number],
    index: number,
    widthClass: string
  ) => (
    <li
      key={tier.id || `${product.id}-tier-${index}`}
      className={`flex min-w-0 flex-col gap-3 rounded-[20px] border border-stone-200/80 bg-white/55 px-4 py-3 ${widthClass}`}
    >
      {tier.title ? (
        <h3 className="break-words text-base font-semibold text-stone-900">
          {tier.title}
        </h3>
      ) : null}
      <p className="min-w-0 break-words text-sm leading-relaxed text-stone-600">
        {tier.description}
      </p>
      <p className="mt-auto text-left text-base font-semibold text-stone-900">
        {formatMoney(tier.priceCents)}
      </p>
    </li>
  );

  return (
    <article className="glass space-y-5 overflow-hidden rounded-[28px] border border-white/80 p-3 shadow-sm sm:space-y-6 sm:p-5 lg:p-6">
      <h2 className="break-words text-left text-2xl font-semibold leading-tight text-stone-900 sm:text-3xl lg:text-4xl">
        {product.name}
      </h2>
      <div
        className="grid min-w-0 gap-5 lg:grid-cols-[minmax(0,1.02fr)_minmax(0,0.98fr)] lg:gap-8"
        style={mediaHeightStyle}
      >
        <div
          ref={mediaRef}
          className="min-w-0 space-y-5 lg:sticky lg:top-24 lg:self-start"
        >
          <MosaicGallery
            images={galleryImages}
            alt={`${product.name} gallery`}
            showAll
            className="[&>div:first-child]:aspect-[3/2]"
          />
          {videoId ? (
            <div className="glass aspect-[3/2] overflow-hidden rounded-[28px] border border-white/80 bg-stone-950 shadow-inner">
              <iframe
                title={`${product.name} video`}
                src={`https://www.youtube-nocookie.com/embed/${videoId}?rel=0`}
                className="h-full w-full"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                allowFullScreen
                referrerPolicy="strict-origin-when-cross-origin"
              />
            </div>
          ) : null}
        </div>
        <div
          className={
            isEvent && !hasInlineEventAction
              ? "min-w-0 py-1 sm:py-2 lg:max-h-[var(--editorial-media-height)] lg:overflow-y-auto lg:pr-2"
              : "flex min-w-0 flex-col gap-5 py-1 sm:gap-6 sm:py-2 lg:h-[var(--editorial-media-height)]"
          }
        >
          <div
            className={
              isEvent && !hasInlineEventAction
                ? ""
                : "min-h-0 flex-1 lg:overflow-y-auto lg:pr-2"
            }
          >
            <p className="whitespace-pre-line break-words text-sm leading-relaxed text-stone-600 sm:text-base">
              {product.description}
            </p>
          </div>
          {!isEvent ? (
            <div className="w-full max-w-[18rem] shrink-0 space-y-4">
              <GiftPrice pricing={pricing} firstOrderDiscount={firstOrderDiscount} />
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
          ) : null}
          {hasSingleEventTier ? (
            <div className="shrink-0 space-y-4 border-t border-stone-200/80 pt-5">
              <ul>{renderTier(tiers[0], 0, "w-full")}</ul>
              <div className="flex justify-start">
                <EventBookingAction isSoldOut={product.isSoldOut} />
              </div>
            </div>
          ) : null}
          {isEvent && !tiers.length ? (
            <div className="flex shrink-0 justify-start">
              <EventBookingAction isSoldOut={product.isSoldOut} />
            </div>
          ) : null}
        </div>
      </div>

      {isEvent && tiers.length > 1 ? (
        <div className={tiers.length ? "space-y-4 border-t border-stone-200/80 pt-5" : ""}>
          {tiers.length ? (
            <div className="space-y-3">
              <p className="text-xs uppercase tracking-[0.28em] text-stone-500">
                Event tiers
              </p>
              <ul className="flex flex-wrap justify-center gap-2.5">
                {tiers.map((tier, index) => renderTier(tier, index, tierWidthClass))}
              </ul>
            </div>
          ) : null}
          <div className="flex justify-center">
            <EventBookingAction isSoldOut={product.isSoldOut} />
          </div>
        </div>
      ) : null}
    </article>
  );
}
