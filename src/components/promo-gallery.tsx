"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import useEmblaCarousel from "embla-carousel-react";
import Link from "next/link";
import ImageWithFallback from "@/components/image-with-fallback";

type PromoSlide = {
  id: string;
  title?: string | null;
  subtitle?: string | null;
  image: string;
  link?: string | null;
};

type PromoGalleryProps = {
  slides: PromoSlide[];
};

const AUTO_SCROLL_INTERVAL_MS = 5000;
const AUTO_SCROLL_PAUSE_MS = 20000;
const INTERACTION_CLICK_THRESHOLD = 8;

const FALLBACK_SLIDES: PromoSlide[] = [
  {
    id: "fallback-1",
    title: "",
    subtitle: "",
    image: "/images/promo-1.webp",
    link: "",
  },
  {
    id: "fallback-2",
    title: "",
    subtitle: "",
    image: "/images/promo-2.webp",
    link: "",
  },
  {
    id: "fallback-3",
    title: "Gift-ready details",
    subtitle: "Handwritten notes and satin ribbon.",
    image: "/images/promo-3.webp",
    link: "/catalog",
  },
];

export default function PromoGallery({ slides }: PromoGalleryProps) {
  const items = useMemo(
    () => (slides.length ? slides : FALLBACK_SLIDES),
    [slides]
  );
  const shouldCenterSlides = items.length < 3;

  const [activeIndex, setActiveIndex] = useState(0);
  const [pageCount, setPageCount] = useState(1);
  const [isAutoPaused, setIsAutoPaused] = useState(false);
  const [canScrollPrev, setCanScrollPrev] = useState(false);
  const [canScrollNext, setCanScrollNext] = useState(false);

  const [emblaRef, emblaApi] = useEmblaCarousel({
    align: shouldCenterSlides ? "center" : "start",
    loop: false,
    containScroll: shouldCenterSlides ? "keepSnaps" : "trimSnaps",
    slidesToScroll: 1,
    dragFree: false,
    skipSnaps: false,
    dragThreshold: 7,
    duration: 32,
  });

  const directionRef = useRef<1 | -1>(1);
  const activeIndexRef = useRef(0);
  const pageCountRef = useRef(1);
  const pauseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const interactionStartRef = useRef<{ x: number; y: number } | null>(null);
  const blockLinkClickRef = useRef(false);
  const resetLinkBlockTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null
  );

  const hasSlides = items.length > 0;
  const canSlide = pageCount > 1;
  const maxIndex = Math.max(0, pageCount - 1);
  const clampedActiveIndex = Math.min(activeIndex, maxIndex);

  const pauseAutoscroll = useCallback(() => {
    setIsAutoPaused(true);

    if (pauseTimerRef.current) {
      clearTimeout(pauseTimerRef.current);
    }

    pauseTimerRef.current = setTimeout(() => {
      setIsAutoPaused(false);
    }, AUTO_SCROLL_PAUSE_MS);
  }, []);

  const syncCarouselState = useCallback(() => {
    if (!emblaApi) return;

    const nextPageCount = Math.max(1, emblaApi.scrollSnapList().length);
    const nextIndex = Math.max(
      0,
      Math.min(emblaApi.selectedScrollSnap(), nextPageCount - 1)
    );
    const previousIndex = activeIndexRef.current;

    if (nextIndex !== previousIndex) {
      directionRef.current = nextIndex > previousIndex ? 1 : -1;
    }

    activeIndexRef.current = nextIndex;
    pageCountRef.current = nextPageCount;
    setActiveIndex(nextIndex);
    setPageCount(nextPageCount);
    setCanScrollPrev(emblaApi.canScrollPrev());
    setCanScrollNext(emblaApi.canScrollNext());
  }, [emblaApi]);

  const beginInteraction = useCallback(
    (x: number, y: number) => {
      interactionStartRef.current = { x, y };
      blockLinkClickRef.current = false;
      pauseAutoscroll();
    },
    [pauseAutoscroll]
  );

  const moveInteraction = useCallback((x: number, y: number) => {
    const start = interactionStartRef.current;
    if (!start || blockLinkClickRef.current) return;

    const movedFarEnough =
      Math.abs(x - start.x) > INTERACTION_CLICK_THRESHOLD ||
      Math.abs(y - start.y) > INTERACTION_CLICK_THRESHOLD;

    if (movedFarEnough) {
      blockLinkClickRef.current = true;
    }
  }, []);

  const endInteraction = useCallback(() => {
    interactionStartRef.current = null;

    if (!blockLinkClickRef.current) return;

    if (resetLinkBlockTimerRef.current) {
      clearTimeout(resetLinkBlockTimerRef.current);
    }

    resetLinkBlockTimerRef.current = setTimeout(() => {
      blockLinkClickRef.current = false;
    }, 250);
  }, []);

  const goToIndex = useCallback(
    (targetIndex: number) => {
      if (!emblaApi) return;

      const boundedMax = Math.max(0, pageCountRef.current - 1);
      const nextIndex = Math.max(0, Math.min(targetIndex, boundedMax));
      const previousIndex = activeIndexRef.current;
      directionRef.current = nextIndex >= previousIndex ? 1 : -1;

      emblaApi.scrollTo(nextIndex);
      pauseAutoscroll();
    },
    [emblaApi, pauseAutoscroll]
  );

  const handlePrev = useCallback(() => {
    if (!canSlide) return;
    goToIndex(activeIndexRef.current - 1);
  }, [canSlide, goToIndex]);

  const handleNext = useCallback(() => {
    if (!canSlide) return;
    goToIndex(activeIndexRef.current + 1);
  }, [canSlide, goToIndex]);

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

  const handleLinkClick = (event: React.MouseEvent<HTMLAnchorElement>) => {
    if (blockLinkClickRef.current) {
      event.preventDefault();
      return;
    }

    pauseAutoscroll();
  };

  useEffect(() => {
    if (!emblaApi) return;

    emblaApi.on("select", syncCarouselState);
    emblaApi.on("reInit", syncCarouselState);
    emblaApi.on("pointerDown", pauseAutoscroll);

    return () => {
      emblaApi.off("select", syncCarouselState);
      emblaApi.off("reInit", syncCarouselState);
      emblaApi.off("pointerDown", pauseAutoscroll);
    };
  }, [emblaApi, pauseAutoscroll, syncCarouselState]);

  useEffect(() => {
    if (!emblaApi) return;
    emblaApi.reInit();
  }, [emblaApi, items.length]);

  useEffect(() => {
    if (!emblaApi || !canSlide || isAutoPaused) return;

    const interval = setInterval(() => {
      const boundedMax = Math.max(0, pageCountRef.current - 1);
      const currentIndex = Math.min(activeIndexRef.current, boundedMax);
      const nextRaw = currentIndex + directionRef.current;
      let nextIndex = nextRaw;

      if (nextRaw > boundedMax) {
        directionRef.current = -1;
        nextIndex = Math.max(currentIndex - 1, 0);
      } else if (nextRaw < 0) {
        directionRef.current = 1;
        nextIndex = Math.min(currentIndex + 1, boundedMax);
      }

      emblaApi.scrollTo(nextIndex);
    }, AUTO_SCROLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [canSlide, emblaApi, isAutoPaused]);

  useEffect(() => {
    return () => {
      if (pauseTimerRef.current) {
        clearTimeout(pauseTimerRef.current);
      }
      if (resetLinkBlockTimerRef.current) {
        clearTimeout(resetLinkBlockTimerRef.current);
      }
    };
  }, []);

  return (
    <div className="rounded-[28px] border-0 bg-transparent p-0 shadow-none sm:glass sm:rounded-[36px] sm:border sm:border-white/80 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3 sm:gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.32em] text-stone-500">
            Studio offers
          </p>
          <h2 className="text-2xl font-semibold text-stone-900 sm:text-4xl">
            Additional options
          </h2>
        </div>
        <div className="hidden text-xs uppercase tracking-[0.28em] text-stone-500 sm:block">
          Auto-scroll
        </div>
      </div>

      <div className="relative mt-5 sm:mt-6">
        <div
          ref={emblaRef}
          className="touch-pan-y select-none overflow-hidden rounded-[28px] border border-white/80"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          onPointerLeave={endInteraction}
        >
          <div className="flex gap-0 md:gap-4">
            {items.map((slide) => (
              <div
                key={slide.id}
                className="w-full min-w-0 flex-shrink-0 snap-start cursor-grab active:cursor-grabbing md:w-[calc((100%-1rem)/2)] lg:w-[calc((100%-2rem)/3)]"
              >
                <div className="relative w-full overflow-hidden rounded-[24px] border border-white/40 aspect-[9/16] sm:border-white/80 sm:aspect-[9/16] lg:aspect-[9/16]">
                  <ImageWithFallback
                    src={slide.image}
                    alt={slide.title || "Promo slide"}
                    width={900}
                    height={1600}
                    className="pointer-events-none h-full w-full object-cover"
                    draggable={false}
                  />
                  <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-black/50 via-black/10 to-transparent" />
                  {(slide.title || slide.subtitle || slide.link) && (
                    <div className="pointer-events-none absolute left-4 right-4 top-4 text-white sm:left-6 sm:right-auto sm:top-6 sm:max-w-md">
                      {slide.title && (
                        <>
                          <p className="text-xs uppercase tracking-[0.3em] text-white/70">
                            Promotion
                          </p>
                          <h3 className="mt-2 text-xl font-semibold sm:text-3xl">
                            {slide.title}
                          </h3>
                        </>
                      )}
                      {slide.subtitle && (
                        <p className="mt-2 text-xs text-white/80 sm:text-sm">
                          {slide.subtitle}
                        </p>
                      )}
                      {slide.link && (
                        <Link
                          href={slide.link}
                          className="pointer-events-auto mt-3 inline-flex rounded-full border border-white/60 bg-white/10 px-3 py-1.5 text-[10px] uppercase tracking-[0.24em] text-white backdrop-blur sm:mt-4 sm:px-4 sm:py-2 sm:text-xs sm:tracking-[0.3em]"
                          onClick={handleLinkClick}
                        >
                          View details
                        </Link>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="pointer-events-none absolute inset-0 flex items-center justify-between px-2 sm:px-3">
          <button
            type="button"
            onClick={handlePrev}
            disabled={!canScrollPrev}
            className="pointer-events-auto flex h-10 w-10 items-center justify-center rounded-full border border-white/70 bg-white/85 text-stone-700 shadow-sm backdrop-blur transition hover:scale-105 disabled:cursor-not-allowed disabled:opacity-45 sm:h-11 sm:w-11"
            aria-label="Previous promotion"
          >
            <svg
              aria-hidden="true"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="h-4 w-4"
            >
              <path
                fillRule="evenodd"
                d="M12.78 4.22a.75.75 0 0 1 0 1.06L8.06 10l4.72 4.72a.75.75 0 1 1-1.06 1.06l-5.25-5.25a.75.75 0 0 1 0-1.06l5.25-5.25a.75.75 0 0 1 1.06 0Z"
                clipRule="evenodd"
              />
            </svg>
          </button>
          <button
            type="button"
            onClick={handleNext}
            disabled={!canScrollNext}
            className="pointer-events-auto flex h-10 w-10 items-center justify-center rounded-full border border-white/70 bg-white/85 text-stone-700 shadow-sm backdrop-blur transition hover:scale-105 disabled:cursor-not-allowed disabled:opacity-45 sm:h-11 sm:w-11"
            aria-label="Next promotion"
          >
            <svg
              aria-hidden="true"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="h-4 w-4"
            >
              <path
                fillRule="evenodd"
                d="M7.22 15.78a.75.75 0 0 1 0-1.06L11.94 10 7.22 5.28a.75.75 0 1 1 1.06-1.06l5.25 5.25a.75.75 0 0 1 0 1.06l-5.25 5.25a.75.75 0 0 1-1.06 0Z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>
      </div>

      {hasSlides ? (
        <p className="mt-3 text-center text-[10px] uppercase tracking-[0.24em] text-stone-500">
          Swipe to browse
        </p>
      ) : null}

      {hasSlides ? (
        <div className="mt-4 flex justify-center gap-2">
          {Array.from({ length: pageCount }).map((_, idx) => (
            <button
              key={`promo-dot-${idx}`}
              type="button"
              onClick={() => goToIndex(idx)}
              className={`h-2 w-2 rounded-full transition ${
                idx === clampedActiveIndex
                  ? "bg-[color:var(--brand)]"
                  : "bg-stone-300"
              }`}
              aria-label={`Go to page ${idx + 1}`}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
