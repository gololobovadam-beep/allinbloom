import Link from "next/link";
import Image from "next/image";
import { getAuthSession } from "@/lib/auth-session";
import CartBadge from "@/components/cart-badge";

const navigationItems = [
  { href: "/catalog", label: "FLOWERS" },
  { href: "/balloons", label: "BALOONS" },
  { href: "/gifts-balloons", label: "GIFTS" },
  { href: "/event-space", label: "EVENT SPACE" },
  { href: "/reviews", label: "REVIEWS" },
  { href: "/contact", label: "CONTACT" },
];

export default async function Header() {
  const { user } = await getAuthSession();
  const isSignedIn = Boolean(user);

  return (
    <header className="site-header sticky top-0 z-50 border-b border-white/60 bg-white/70 backdrop-blur-xl">
      <div className="mx-auto w-full max-w-6xl px-4 py-3 sm:px-6 sm:py-4 lg:px-8">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-4 sm:gap-6">
            <Link href="/" className="inline-flex shrink-0 items-center" aria-label="All in Bloom home">
              <Image
                src="/logo.png"
                alt="All in Bloom"
                width={1434}
                height={796}
                priority
                sizes="(max-width: 640px) 80px, 88px"
                className="h-11 w-auto sm:h-12"
              />
            </Link>
            <nav className="hidden items-center gap-3 text-[10px] uppercase tracking-[0.2em] text-stone-500 xl:gap-4 xl:text-xs xl:tracking-[0.24em] lg:flex">
              {navigationItems.map((item) => (
                <Link key={item.href} href={item.href} className="whitespace-nowrap hover:text-stone-700">
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <Link
              href={isSignedIn ? "/account" : "/auth"}
              className="rounded-full border border-stone-200 bg-white/80 px-3 py-2 text-[11px] uppercase tracking-[0.22em] text-stone-600 sm:px-4 sm:text-xs sm:tracking-[0.3em]"
            >
              {isSignedIn ? "Account" : "Sign in"}
            </Link>
            <CartBadge />
          </div>
        </div>
        <nav className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-[10px] uppercase tracking-[0.18em] text-stone-500 sm:text-xs sm:tracking-[0.22em] lg:hidden">
          {navigationItems.map((item) => (
            <Link key={item.href} href={item.href} className="whitespace-nowrap hover:text-stone-700">
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
