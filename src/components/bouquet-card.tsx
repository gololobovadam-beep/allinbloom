"use client";

import { useMemo, useState } from "react";
import { formatLabel, formatMoney } from "@/lib/format";
import AddToCartControls from "@/components/add-to-cart-controls";
import BouquetImageCarousel from "@/components/bouquet-image-carousel";
import type { Bouquet, BouquetPricing } from "@/lib/api-types";
import { getVisibleBouquetGalleryImages } from "@/lib/bouquet-images";
import { FLOWER_TYPES } from "@/lib/constants";
import { applyPercentDiscount } from "@/lib/pricing";
import {
  clampFlowerQuantity,
  FLOWER_QUANTITY_MAX,
  FLOWER_QUANTITY_MIN,
  isFlowerQuantityEnabledForBouquet,
} from "@/lib/flower-quantity";

export default function BouquetCard({
  bouquet,
  pricing,
  firstOrderDiscount = null,
  enableFlowerQuantityInput = false,
  splitPriceRows = false,
}: {
  bouquet: Bouquet;
  pricing: BouquetPricing;
  firstOrderDiscount?: {
    percent: number;
    note: string;
  } | null;
  enableFlowerQuantityInput?: boolean;
  splitPriceRows?: boolean;
}) {
  const galleryImages = getVisibleBouquetGalleryImages(bouquet);
  const isBalloon = bouquet.catalogType === "BALOONS";
  const selectableSet = new Set<string>(FLOWER_TYPES);
  const parsedFlowerTypes = String(bouquet.style || "")
    .split(",")
    .map((value) => value.trim().toUpperCase())
    .filter((value) => selectableSet.has(value))
    .filter((value, index, list) => list.indexOf(value) === index)
    .slice(0, 3);

  const flowerTypeLabelParts = parsedFlowerTypes.length
    ? parsedFlowerTypes.map((value) => formatLabel(value))
    : bouquet.flowerType === "MIXED"
    ? ["Assorted blooms"]
    : [formatLabel(bouquet.flowerType)];
  const flowerTypeLabel = flowerTypeLabelParts.join(", ");
  const flowerTypeTextClass =
    flowerTypeLabelParts.length >= 3
      ? "text-[8px] tracking-[0.1em] sm:text-[10px]"
      : flowerTypeLabelParts.length === 2
      ? "text-[9px] tracking-[0.12em] sm:text-[11px]"
      : "text-[10px] tracking-[0.16em] sm:text-xs sm:tracking-[0.24em]";
  const bouquetTypeLabel =
    bouquet.bouquetType ||
    (String(bouquet.style || "").trim().toUpperCase() === "SEASON"
      ? "SEASON"
      : bouquet.isMixed
      ? "MIXED"
      : "MONO");
  const bouquetTypeDisplay =
    bouquetTypeLabel === "SEASON" ? "Seasonal" : formatLabel(bouquetTypeLabel);
  const defaultFlowerQuantity = clampFlowerQuantity(
    Number(bouquet.defaultFlowerQuantity || FLOWER_QUANTITY_MIN)
  );
  const [flowerQuantityState, setFlowerQuantityState] = useState(() => ({
    bouquetId: bouquet.id,
    defaultQuantity: defaultFlowerQuantity,
    value: defaultFlowerQuantity,
  }));
  // Product data can be refreshed in place. Until the shopper changes the
  // input again, display the refreshed default without scheduling a second
  // render solely to copy a prop into state.
  const flowerQuantity =
    flowerQuantityState.bouquetId === bouquet.id &&
    flowerQuantityState.defaultQuantity === defaultFlowerQuantity
      ? flowerQuantityState.value
      : defaultFlowerQuantity;
  const isSoldOut = bouquet.isSoldOut;
  const isFlowerQuantityEnabled = useMemo(
    () =>
      !isSoldOut &&
      enableFlowerQuantityInput &&
      isFlowerQuantityEnabledForBouquet(
        bouquetTypeLabel,
        bouquet.allowFlowerQuantity
      ),
    [
      bouquet.allowFlowerQuantity,
      bouquetTypeLabel,
      enableFlowerQuantityInput,
      isSoldOut,
    ]
  );

  const appliedDiscount = pricing.discount || firstOrderDiscount;
  const discountedUnitPriceCents = pricing.discount
    ? pricing.finalPriceCents
    : firstOrderDiscount
    ? applyPercentDiscount(pricing.originalPriceCents, firstOrderDiscount.percent)
    : pricing.originalPriceCents;
  const effectiveQuantity = isFlowerQuantityEnabled ? flowerQuantity : 1;
  const originalPriceCents = pricing.originalPriceCents * effectiveQuantity;
  const finalPriceCents = discountedUnitPriceCents * effectiveQuantity;
  const perFlowerFromCents = appliedDiscount
    ? discountedUnitPriceCents
    : pricing.originalPriceCents;
  const perStemPriceLabel = formatMoney(perFlowerFromCents).replace(/\.00$/, "");
  const compactFinalPriceClassWithDiscount =
    "text-[clamp(7.54px,2.75vw,11.66px)] font-semibold leading-none text-[color:var(--brand)] sm:text-[clamp(13px,4.7vw,20px)]";
  const compactFinalPriceClassWithoutDiscount =
    "text-[clamp(8.16px,2.8vw,11.66px)] font-semibold leading-none text-stone-900 sm:text-[clamp(14px,4.8vw,20px)]";
  const finalPriceClassWithDiscount =
    "text-[clamp(10.79px,3.94vw,16.68px)] font-semibold leading-none text-[color:var(--brand)] sm:text-[clamp(13px,4.7vw,20px)]";
  const finalPriceClassWithoutDiscount =
    "text-[clamp(11.67px,4vw,16.68px)] font-semibold leading-none text-stone-900 sm:text-[clamp(14px,4.8vw,20px)]";
  const splitOldPriceClass =
    "text-[clamp(7.58px,2.81vw,10.61px)] text-stone-400 line-through sm:text-[clamp(10px,3.7vw,14px)]";
  const splitDiscountBadgeClass =
    "inline-flex shrink-0 items-center rounded-full bg-[color:var(--brand)]/10 px-1.5 py-0.5 text-[clamp(6.06px,2.12vw,9.09px)] font-semibold uppercase tracking-[0.08em] text-[color:var(--brand)] sm:px-2.5 sm:text-[clamp(8px,2.8vw,12px)]";

  return (
    <div className="glass flex h-full flex-col gap-3 rounded-[24px] border border-white/80 p-[9px] sm:gap-4 sm:rounded-[28px] sm:p-5">
      <div className="overflow-hidden rounded-[18px] border border-white/80 bg-white sm:rounded-[22px]">
        <BouquetImageCarousel images={galleryImages} alt={bouquet.name} />
      </div>
      <div className="min-w-0 flex-1 space-y-1.5 sm:space-y-2">
        <div className="flex items-end justify-between gap-2 text-stone-500 uppercase">
          {isBalloon ? (
            <>
              <span className="min-w-0 truncate text-[10px] tracking-[0.16em] sm:text-xs sm:tracking-[0.24em]">
                Balloons
              </span>
              <span className="shrink-0 text-[10px] tracking-[0.16em] sm:text-xs sm:tracking-[0.24em]">
                All
              </span>
            </>
          ) : (
            <>
              <span className={`min-w-0 truncate ${flowerTypeTextClass}`}>
                {flowerTypeLabel}
              </span>
              <span className="shrink-0 text-[10px] tracking-[0.16em] sm:text-xs sm:tracking-[0.24em]">
                {bouquetTypeDisplay}
              </span>
            </>
          )}
        </div>
        <h3 className="break-words text-base font-semibold leading-tight text-stone-900 sm:text-xl">
          {bouquet.name}
        </h3>
        <p className="break-words text-xs leading-snug text-stone-600 sm:text-sm sm:leading-relaxed">
          {bouquet.description}
        </p>
      </div>
      {isFlowerQuantityEnabled ? (
        <label className="flex items-center justify-between gap-2 px-0.5 py-1 text-[9px] uppercase tracking-[0.12em] text-stone-600 max-[410px]:text-[8px] max-[410px]:tracking-[0.06em] sm:gap-3 sm:text-xs sm:tracking-[0.24em]">
          <span className="flex flex-col gap-0.5">
            <span>Flowers</span>
            <span className="text-[8px] normal-case tracking-normal text-stone-500 sm:text-[10px]">
              {perStemPriceLabel}/stem
            </span>
          </span>
          <input
            type="number"
            min={FLOWER_QUANTITY_MIN}
            max={FLOWER_QUANTITY_MAX}
            inputMode="numeric"
            value={flowerQuantity}
            onChange={(event) => {
              const next = Number(event.target.value);
              setFlowerQuantityState({
                bouquetId: bouquet.id,
                defaultQuantity: defaultFlowerQuantity,
                value: clampFlowerQuantity(next),
              });
            }}
            className="h-8 w-16 rounded-xl border border-stone-200 bg-white px-2 text-right text-xs font-semibold text-stone-800 outline-none focus:border-stone-400 max-[410px]:w-14 max-[410px]:px-1.5 max-[410px]:text-[11px] sm:w-20 sm:text-sm"
          />
        </label>
      ) : null}
      <div className="space-y-2">
        {appliedDiscount ? (
          splitPriceRows ? (
            <div className="space-y-1">
              <div className="flex min-w-0 max-w-full items-center gap-1 overflow-hidden whitespace-nowrap sm:gap-2">
                <span className={splitOldPriceClass}>
                  {formatMoney(originalPriceCents)}
                </span>
                <span className={splitDiscountBadgeClass}>
                  -{appliedDiscount.percent}%
                </span>
              </div>
              <div className="flex items-baseline gap-1.5">
                <p className={finalPriceClassWithDiscount}>
                  {formatMoney(finalPriceCents)}
                </p>
              </div>
            </div>
          ) : (
            <div className="flex min-w-0 max-w-full items-center gap-1 overflow-hidden sm:gap-2">
              <div className="flex min-w-0 flex-col items-start gap-0.5 sm:flex-row sm:items-center sm:gap-1">
                <span className={compactFinalPriceClassWithDiscount}>
                  {formatMoney(finalPriceCents)}
                </span>
              </div>
              <span className="text-[clamp(5.83px,2.16vw,8.16px)] text-stone-400 line-through sm:text-[clamp(10px,3.7vw,14px)]">
                {formatMoney(originalPriceCents)}
              </span>
              <span className="inline-flex shrink-0 items-center rounded-full bg-[color:var(--brand)]/10 px-1.5 py-0.5 text-[clamp(4.66px,1.63vw,6.99px)] font-semibold uppercase tracking-[0.08em] text-[color:var(--brand)] sm:px-2.5 sm:text-[clamp(8px,2.8vw,12px)]">
                -{appliedDiscount.percent}%
              </span>
            </div>
          )
        ) : (
          <div className="flex items-baseline gap-1.5">
            <p
              className={
                splitPriceRows
                  ? finalPriceClassWithoutDiscount
                  : compactFinalPriceClassWithoutDiscount
              }
            >
              {formatMoney(originalPriceCents)}
            </p>
          </div>
        )}
      </div>
      {isSoldOut ? (
        <div className="w-full rounded-full border border-stone-200 bg-stone-100 px-3 py-2 text-center text-[10px] uppercase tracking-[0.16em] text-stone-500 sm:px-4 sm:text-xs sm:tracking-[0.3em]">
          Sold out
        </div>
      ) : (
        <AddToCartControls
          selectedQuantity={effectiveQuantity}
          item={{
            id: bouquet.id,
            name: bouquet.name,
            priceCents: bouquet.priceCents,
            image: bouquet.image,
            discountPercent: bouquet.discountPercent,
            discountNote: bouquet.discountNote || undefined,
            flowerType: bouquet.flowerType,
            flowerTypes: parsedFlowerTypes.length
              ? parsedFlowerTypes.join(", ")
              : bouquet.flowerType === "MIXED"
              ? ""
              : bouquet.flowerType,
            colors: bouquet.colors,
            isMixed: bouquet.isMixed,
            bouquetType: bouquet.bouquetType,
            catalogType: bouquet.catalogType || "FLOWERS",
            isFlowerQuantityEnabled,
          }}
        />
      )}
    </div>
  );
}
