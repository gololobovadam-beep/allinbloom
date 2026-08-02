import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import BouquetCard from "@/components/bouquet-card";
import GalleryImageLightbox from "@/components/gallery-image-lightbox";
import FloristChoiceForm from "@/components/florist-choice-form";
import PromoCard from "@/components/promo-card";
import PromoGallery from "@/components/promo-gallery";
import { getFeaturedBouquets } from "@/lib/data/bouquets";
import { getActivePromoSlides } from "@/lib/data/promotions";
import { getStoreSettings } from "@/lib/data/settings";
import { getHomeHeroImage, getVisibleHomeGalleryImages } from "@/lib/home-images";
import { getBouquetPricing } from "@/lib/pricing";
import {
  SITE_CITY,
  SITE_COUNTRY,
  SITE_DESCRIPTION,
  SITE_EMAIL,
  SITE_INSTAGRAM,
  SITE_NAME,
  SITE_ORIGIN,
  SITE_PHONE,
  SITE_REGION,
  SITE_TAGLINE,
} from "@/lib/site";

export const metadata: Metadata = {
  title: "Chicago Flower Delivery & Luxury Bouquets",
  description: SITE_DESCRIPTION,
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "Chicago Flower Delivery & Luxury Bouquets",
    description: SITE_DESCRIPTION,
    url: "/",
    images: [
      {
        url: "/images/hero-bouquet.webp",
        alt: SITE_TAGLINE,
      },
    ],
  },
};

export default async function HomePage() {
  const featured = await getFeaturedBouquets();
  const promoSlides = await getActivePromoSlides();
  const settings = await getStoreSettings();
  const heroImage = getHomeHeroImage(settings);
  // Administrators can store any number of images; the public home mosaic and
  // its lightbox intentionally expose only the first six in that order.
  const galleryImages = getVisibleHomeGalleryImages(settings);
  const [mainGalleryImage, ...compactGalleryImages] = galleryImages;
  const atelierGalleryItems = galleryImages.map((src, idx) => ({
    src,
    alt: `Atelier gallery image ${idx + 1}`,
    lightboxWidth: 1600,
    lightboxHeight: 1600,
  }));
  const localBusinessImage = heroImage.startsWith("http")
    ? heroImage
    : `${SITE_ORIGIN}${heroImage.startsWith("/") ? heroImage : `/${heroImage}`}`;

  const localBusinessSchema = {
    "@context": "https://schema.org",
    "@type": "Florist",
    name: SITE_NAME,
    url: SITE_ORIGIN,
    image: localBusinessImage,
    description: SITE_DESCRIPTION,
    telephone: SITE_PHONE,
    email: SITE_EMAIL,
    priceRange: "$$",
    address: {
      "@type": "PostalAddress",
      addressLocality: SITE_CITY,
      addressRegion: SITE_REGION,
      addressCountry: SITE_COUNTRY,
    },
    areaServed: `${SITE_CITY}, ${SITE_REGION}`,
    sameAs: [SITE_INSTAGRAM],
    openingHours: ["Mo-Sa 09:00-19:00"],
  };

  return (
    <div className="flex flex-col gap-14 sm:gap-20 lg:gap-[4.5rem]">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(localBusinessSchema),
        }}
      />
      <section className="grid gap-10 lg:grid-cols-[1.15fr_0.85fr] lg:items-center animate-rise">
        <div className="space-y-6">
          <div className="relative lg:hidden">
            <div className="pointer-events-none absolute -inset-x-3 -top-6 h-[340px] rounded-[40px] bg-[radial-gradient(circle_at_20%_20%,rgba(var(--cream-rgb),0.86),transparent_58%),radial-gradient(circle_at_85%_15%,rgba(var(--accent-rgb),0.36),transparent_45%)] blur-2xl" />
            <div className="relative overflow-hidden rounded-[34px] border border-white/80 bg-[linear-gradient(140deg,rgba(255,255,255,0.9),rgba(var(--cream-rgb),0.72))] p-3 shadow-[0_26px_70px_rgba(var(--brand-rgb),0.22)]">
              <div className="relative overflow-hidden rounded-[26px] border border-white/70">
                <Image
                  src={heroImage}
                  alt="Elegant floral bouquet"
                  width={760}
                  height={940}
                  className="h-[420px] w-full object-cover object-center"
                  priority
                  fetchPriority="high"
                />
                <div className="absolute inset-0 bg-[linear-gradient(175deg,rgba(22,10,7,0.06),rgba(22,10,7,0.7))]" />
                <div className="absolute left-4 top-4 rounded-full border border-white/50 bg-white/20 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.24em] text-white backdrop-blur">
                  Same-day delivery
                </div>
                <div className="absolute bottom-0 left-0 right-0 p-4 text-white">
                  <p className="text-[11px] uppercase tracking-[0.3em] text-white/75">
                    Floral atelier
                  </p>
                  <p className="mt-1 text-2xl font-semibold leading-tight text-balance">
                    Modern bouquets for your most special moments
                  </p>
                </div>
              </div>
              <Link
                href="/catalog"
                className="mt-3 inline-flex w-full items-center justify-center rounded-2xl bg-[color:var(--brand)] px-4 py-3 text-sm font-semibold uppercase tracking-[0.2em] text-white transition hover:bg-[color:var(--brand-dark)]"
              >
                Shop all
              </Link>
            </div>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full bg-white/70 px-4 py-2 text-xs uppercase tracking-[0.24em] text-stone-700 shadow-sm">
            Chicago delivery in 2-4 hours
          </div>
          <div className="lg:hidden animate-rise [animation-delay:80ms]">
            <PromoGallery slides={promoSlides} />
          </div>
          <h1 className="text-3xl font-semibold text-stone-900 text-balance sm:text-5xl lg:text-6xl">
            All in Bloom Floral Studio
          </h1>
          <p className="max-w-xl text-balance text-lg text-stone-700">
            A modern floral atelier for soft, romantic bouquets and effortless
            gifting. Curated by artisan florists, designed for every elegant
            moment in your life.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:gap-4">
            <Link
              href="/catalog"
              className="hidden items-center justify-center rounded-full bg-[color:var(--brand)] px-6 py-3 text-center text-sm font-semibold uppercase tracking-[0.2em] text-white transition hover:bg-[color:var(--brand-dark)] lg:inline-flex"
            >
              Shop all
            </Link>
            <Link
              href="/catalog?filter=featured"
              className="rounded-full border border-[color:var(--brand)]/30 bg-white/70 px-6 py-3 text-center text-sm font-semibold uppercase tracking-[0.2em] text-[color:var(--brand)] transition hover:border-[color:var(--brand)]/60"
            >
              Explore signature sets
            </Link>
          </div>
          <a
            href="https://www.instagram.com/all_in_bloom_studio"
            target="_blank"
            rel="noreferrer"
            className="inline-flex w-full items-center justify-center gap-3 rounded-full bg-[color:var(--brand)] px-6 py-3 text-sm font-semibold uppercase tracking-[0.2em] text-white shadow-[0_12px_28px_rgba(var(--brand-rgb),0.28)] transition hover:-translate-y-0.5 hover:bg-[color:var(--brand-dark)] sm:w-auto"
          >
            Instagram
            <Image
              src="/instagram.png"
              alt=""
              aria-hidden
              width={16}
              height={16}
              className="h-4 w-4 object-contain"
            />
          </a>
        </div>
        <div className="relative animate-float hidden lg:block">
          <div className="glass absolute right-6 top-6 z-10 hidden h-14 min-w-[10rem] rounded-full border border-white/80 px-4 text-center text-xs font-semibold uppercase tracking-[0.24em] text-stone-700 sm:flex items-center justify-center">
            New arrivals
          </div>
          <div className="glass overflow-hidden rounded-[32px] border border-white/80 p-4">
            <Image
              src={heroImage}
              alt="Elegant floral bouquet"
              width={520}
              height={640}
              className="h-auto w-full rounded-[26px] object-cover"
              priority
              fetchPriority="high"
            />
          </div>
        </div>
      </section>

      <section className="hidden lg:block animate-rise [animation-delay:80ms]">
        <PromoGallery slides={promoSlides} />
      </section>

      <section className="space-y-6 animate-rise [animation-delay:200ms]">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.32em] text-stone-500">
              Signature bouquets
            </p>
            <h2 className="text-2xl font-semibold text-stone-900 sm:text-4xl">
              Our curated favorites
            </h2>
          </div>
          <Link
            href="/catalog?filter=featured"
            className="w-full rounded-full border border-stone-300 bg-white/80 px-5 py-2 text-center text-xs uppercase tracking-[0.3em] text-stone-600 transition hover:border-stone-400 sm:w-auto sm:shrink-0 sm:whitespace-nowrap"
          >
            View all
          </Link>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:gap-6 md:grid-cols-2 lg:grid-cols-3">
          {featured.map((bouquet) => (
            <BouquetCard
              key={bouquet.id}
              bouquet={bouquet}
              pricing={getBouquetPricing(bouquet, settings)}
            />
          ))}
        </div>
      </section>

      <section className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center animate-rise [animation-delay:280ms]">
        <div className="space-y-4">
          <p className="text-xs uppercase tracking-[0.32em] text-stone-500">
            About the atelier
          </p>
          <h2 className="text-3xl font-semibold text-stone-900 sm:text-4xl">
            A poetic studio of blooms, fragrance, and quiet luxury
          </h2>
          <p className="text-sm leading-relaxed text-stone-600">
            All in Bloom Floral Studio blends old-world floral artistry with
            contemporary styling. Our designers source premium stems from local
            growers across the Chicago area, then compose each bouquet with a
            signature airy silhouette, tactile textures, and a soft palette that
            feels both timeless and modern.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <PromoCard
              title="Each bouquet comes in exclusive packaging with branded ribbons and stickers."
              description="We can also add a card and a festive photo to make your gift truly unforgettable."
            />
          </div>
        </div>
        <div className="space-y-4">
          <div>
            <p className="text-xs uppercase tracking-[0.32em] text-stone-500">
              Atelier gallery
            </p>
            <h3 className="mt-2 text-2xl font-semibold text-stone-900 sm:text-3xl">
              Wrapped bouquet moments
            </h3>
          </div>
          <div className="space-y-2.5 sm:hidden">
            <div className="glass overflow-hidden rounded-[28px] border border-white/80 aspect-[5/4]">
              <GalleryImageLightbox
                src={mainGalleryImage}
                alt="Bouquet gallery preview"
                className="block h-full w-full"
                imageClassName="h-full w-full object-cover"
                previewWidth={520}
                previewHeight={420}
                items={atelierGalleryItems}
                startIndex={0}
              />
            </div>
            <div className="grid grid-cols-5 gap-2">
              {compactGalleryImages.map((src, idx) => (
                <div
                  key={`home-gallery-mobile-${idx + 1}`}
                  className="glass overflow-hidden rounded-[18px] border border-white/80 aspect-square"
                >
                  <GalleryImageLightbox
                    src={src}
                    alt="Bouquet gallery preview"
                    className="block h-full w-full"
                    imageClassName="h-full w-full object-cover"
                    previewWidth={180}
                    previewHeight={180}
                    items={atelierGalleryItems}
                    startIndex={idx + 1}
                  />
                </div>
              ))}
            </div>
          </div>
          <div className="hidden gap-4 sm:grid sm:grid-cols-2">
            {galleryImages.map((src, idx) => (
              <div
                key={`home-gallery-desktop-${idx}`}
                className="glass overflow-hidden rounded-[28px] border border-white/80 aspect-square"
              >
                <GalleryImageLightbox
                  src={src}
                  alt="Bouquet gallery preview"
                  className="block h-full w-full"
                  imageClassName="h-full w-full object-cover"
                  previewWidth={400}
                  previewHeight={400}
                  items={atelierGalleryItems}
                  startIndex={idx}
                />
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-2 animate-rise [animation-delay:360ms]">
        <PromoCard
          title="First Order Offer"
          description="Enjoy 10% off your first order."
          tone="rose"
        />
        <PromoCard
          title="Bridal Atelier"
          description="Reserve a bespoke wedding consultation with our senior florist team."
          tone="leaf"
        />
      </section>

      <section className="grid gap-8 rounded-none border-0 bg-transparent p-0 shadow-none sm:gap-10 sm:rounded-[36px] sm:border sm:border-white/80 sm:bg-white/70 sm:p-8 sm:shadow-sm lg:grid-cols-[1fr_1.1fr] animate-rise [animation-delay:480ms]">
        <div className="space-y-5">
          <p className="text-xs uppercase tracking-[0.32em] text-stone-500">
            Build your own bouquet
          </p>
          <h2 className="text-3xl font-semibold text-stone-900 sm:text-4xl">
            Let our florists craft a bouquet just for you
          </h2>
          <p className="text-sm leading-relaxed text-stone-600">
            Choose your mood, palette, and price point. We will hand-pick the
            freshest stems and design a one-of-a-kind bouquet with a personal
            note from our atelier.
          </p>
          <ul className="flex flex-wrap gap-3 text-xs uppercase tracking-[0.22em] text-stone-500">
            <li className="rounded-full border border-stone-200 bg-white/70 px-3 py-1">
              same-day delivery
            </li>
            <li className="rounded-full border border-stone-200 bg-white/70 px-3 py-1">
              seasonal selection
            </li>
            <li className="rounded-full border border-stone-200 bg-white/70 px-3 py-1">
              handwritten note
            </li>
          </ul>
        </div>
        <FloristChoiceForm />
      </section>

      <section className="grid gap-6 rounded-none border-0 bg-transparent p-0 shadow-none sm:rounded-[36px] sm:border sm:border-white/80 sm:bg-white/70 sm:p-8 sm:shadow-sm lg:grid-cols-[0.9fr_1.1fr] animate-rise [animation-delay:520ms]">
        <div className="space-y-4">
          <p className="text-xs uppercase tracking-[0.32em] text-stone-500">
            Visit our studio
          </p>
          <h2 className="text-3xl font-semibold text-stone-900 sm:text-4xl">
            Find All in Bloom Floral Studio in Chicago
          </h2>
          <p className="text-sm leading-relaxed text-stone-600">
            Stop by our studio for same-day bouquets, custom arrangements, and
            in-person consultations. We are open six days a week and always
            happy to help you choose the perfect stems.
          </p>
        </div>
        <div className="overflow-hidden rounded-[28px] border border-white/80 bg-white">
          <iframe
            title="All in Bloom Floral Studio map"
            src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d184.91590065921062!2d-87.9050852153543!3d42.136281087564285!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x880fb9328ddb551b%3A0xe419f6ce282a69!2zMjI0IFMgTWlsd2F1a2VlIEF2ZSwgV2hlZWxpbmcsIElMIDYwMDkwLCDQodCo0JA!5e0!3m2!1sru!2sru!4v1777579957452!5m2!1sru!2sru"
            className="h-[280px] w-full sm:h-[360px]"
            style={{ border: 0 }}
            allowFullScreen
            loading="lazy"
            referrerPolicy="no-referrer-when-downgrade"
          />
        </div>
      </section>
    </div>
  );
}


