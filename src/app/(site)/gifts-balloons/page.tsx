import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

const destinations = [
  {
    title: "Gifts",
    description: "Thoughtful objects for occasions worth remembering.",
    href: "/gifts",
    image: "/images/promo-1.webp",
  },
  {
    title: "Balloons",
    description: "A joyful finishing touch for every celebration.",
    href: "/balloons",
    image: "/images/promo-2.webp",
  },
  {
    title: "Flowers",
    description: "Return to our floral collection whenever you need blooms.",
    href: "/catalog",
    image: "/images/hero-bouquet.webp",
  },
] as const;

export const metadata: Metadata = {
  title: "Gifts & Balloons | All in Bloom Floral Studio",
  description: "Explore gifts, balloons, and our floral collection.",
  alternates: { canonical: "/gifts-balloons" },
};

export default function GiftsAndBalloonsPage() {
  return (
    <div className="space-y-8 sm:space-y-10">
      <div className="max-w-2xl space-y-3">
        <p className="text-xs uppercase tracking-[0.32em] text-stone-500">
          Gifts &amp; Balloons
        </p>
        <h1 className="text-3xl font-semibold text-stone-900 sm:text-5xl">
          A little extra for every occasion
        </h1>
        <p className="text-balance text-sm leading-relaxed text-stone-600">
          Pair a bouquet with an elegant gift, choose a joyful balloon design,
          or head back to our flower collection.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 sm:gap-6">
        {destinations.map((destination) => (
          <Link
            key={destination.href}
            href={destination.href}
            className="group glass isolate overflow-hidden rounded-[28px] border border-white/80 p-3 shadow-sm transition duration-300 hover:-translate-y-1 hover:shadow-[0_18px_38px_rgba(var(--brand-rgb),0.2)] sm:p-4"
          >
            <div className="relative aspect-[4/5] overflow-hidden rounded-[22px] bg-stone-100">
              <Image
                src={destination.image}
                alt=""
                fill
                sizes="(max-width: 639px) 100vw, (max-width: 1023px) 50vw, 33vw"
                className="object-cover transition duration-500 group-hover:scale-105"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-[rgba(26,11,8,0.74)] via-[rgba(26,11,8,0.12)] to-transparent" />
              <div className="absolute inset-x-0 bottom-0 p-4 text-white sm:p-5">
                <h2 className="text-2xl font-semibold leading-tight">
                  {destination.title}
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-white/85">
                  {destination.description}
                </p>
                <span className="mt-4 inline-flex rounded-full border border-white/50 bg-white/15 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.2em] backdrop-blur sm:text-xs sm:tracking-[0.24em]">
                  Explore
                </span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
