"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import useEmblaCarousel from "embla-carousel-react";
import GalleryImageLightbox from "@/components/gallery-image-lightbox";

type BouquetImageCarouselProps = {
  images: string[];
  alt: string;
};

const INTERACTION_CLICK_THRESHOLD = 8;

export default function BouquetImageCarousel({
  images,
  alt,
}: BouquetImageCarouselProps) {
  const safeImages = useMemo(
    () => {
      const visibleImages = images.slice(0, 6);
      return visibleImages.length ? visibleImages : ["/images/mock.webp"];
    },
    [images]
  );

  const [activeIndex, setActiveIndex] = useState(0);
  const [pageCount, setPageCount] = useState(1);

  const [emblaRef, emblaApi] = useEmblaCarousel({
    align: "start",
    loop: false,
    containScroll: "trimSnaps",
    slidesToScroll: 1,
    dragFree: false,
    skipSnaps: false,
    dragThreshold: 7,
    duration: 32,
  });

  const pageCountRef = useRef(1);
  const interactionStartRef = useRef<{ x: number; y: number } | null>(null);
  const blockImageOpenRef = useRef(false);
  const resetOpenBlockTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null
  );

  const canSlide = pageCount > 1;
  const maxIndex = Math.max(0, pageCount - 1);
  const clampedActiveIndex = Math.min(activeIndex, maxIndex);

  const syncCarouselState = useCallback(() => {
    if (!emblaApi) return;

    const nextPageCount = Math.max(1, emblaApi.scrollSnapList().length);
    const nextIndex = Math.max(
      0,
      Math.min(emblaApi.selectedScrollSnap(), nextPageCount - 1)
    );

    pageCountRef.current = nextPageCount;
    setActiveIndex(nextIndex);
    setPageCount(nextPageCount);
  }, [emblaApi]);

  const goToIndex = useCallback(
    (targetIndex: number) => {
      if (!emblaApi) return;

      const boundedMax = Math.max(0, pageCountRef.current - 1);
      const nextIndex = Math.max(0, Math.min(targetIndex, boundedMax));
      emblaApi.scrollTo(nextIndex);
    },
    [emblaApi]
  );

  const beginInteraction = useCallback((x: number, y: number) => {
    interactionStartRef.current = { x, y };
    blockImageOpenRef.current = false;
  }, []);

  const moveInteraction = useCallback((x: number, y: number) => {
    const start = interactionStartRef.current;
    if (!start || blockImageOpenRef.current) return;

    const movedFarEnough =
      Math.abs(x - start.x) > INTERACTION_CLICK_THRESHOLD ||
      Math.abs(y - start.y) > INTERACTION_CLICK_THRESHOLD;

    if (movedFarEnough) {
      blockImageOpenRef.current = true;
    }
  }, []);

  const endInteraction = useCallback(() => {
    interactionStartRef.current = null;

    if (!blockImageOpenRef.current) return;

    if (resetOpenBlockTimerRef.current) {
      clearTimeout(resetOpenBlockTimerRef.current);
    }

    resetOpenBlockTimerRef.current = setTimeout(() => {
      blockImageOpenRef.current = false;
    }, 250);
  }, []);

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!event.isPrimary) return;
    beginInteraction(event.clientX, event.clientY);
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!event.isPrimary) return;
    moveInteraction(event.clientX, event.clientY);
  };

  const handlePointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!event.isPrimary) return;
    endInteraction();
  };

  const lightboxItems = useMemo(
    () =>
      safeImages.map((src, index) => ({
        src,
        alt: `${alt} ${index + 1}`,
        lightboxWidth: 1600,
        lightboxHeight: 1600,
      })),
    [alt, safeImages]
  );

  useEffect(() => {
    if (!emblaApi) return;

    emblaApi.on("select", syncCarouselState);
    emblaApi.on("reInit", syncCarouselState);
    // Embla has finished attaching at this point, but let its first layout
    // settle before reading snaps. Subsequent updates arrive through the
    // subscribed Embla events below.
    const initialSyncFrame = window.requestAnimationFrame(() => {
      syncCarouselState();
    });

    return () => {
      window.cancelAnimationFrame(initialSyncFrame);
      emblaApi.off("select", syncCarouselState);
      emblaApi.off("reInit", syncCarouselState);
    };
  }, [emblaApi, syncCarouselState]);

  useEffect(() => {
    if (!emblaApi) return;
    emblaApi.reInit();
  }, [emblaApi, safeImages.length]);

  useEffect(() => {
    return () => {
      if (resetOpenBlockTimerRef.current) {
        clearTimeout(resetOpenBlockTimerRef.current);
      }
    };
  }, []);

  return (
    <div className="relative">
      <div
        ref={emblaRef}
        className="touch-pan-y select-none overflow-hidden"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        onPointerLeave={endInteraction}
      >
        <div className="flex">
          {safeImages.map((src, index) => (
            <div
              key={`${src}-${index}`}
              className="w-full min-w-0 flex-shrink-0 snap-start cursor-grab active:cursor-grabbing"
            >
              <GalleryImageLightbox
                src={src}
                alt={alt}
                className="block w-full"
                imageClassName="aspect-square w-full object-cover"
                previewWidth={520}
                previewHeight={520}
                items={lightboxItems}
                startIndex={index}
                canOpen={() => !blockImageOpenRef.current}
                onOpen={endInteraction}
              />
            </div>
          ))}
        </div>
      </div>

      {canSlide ? (
        <div className="pointer-events-none absolute inset-x-0 bottom-3 z-10 flex justify-center gap-2">
          {Array.from({ length: pageCount }).map((_, index) => (
            <button
              key={`bouquet-dot-${index}`}
              type="button"
              onClick={() => goToIndex(index)}
              className={`pointer-events-auto h-2 w-2 rounded-full transition ${
                index === clampedActiveIndex ? "bg-white" : "bg-white/45"
              }`}
              aria-label={`Go to bouquet photo ${index + 1}`}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
