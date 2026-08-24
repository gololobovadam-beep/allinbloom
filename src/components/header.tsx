import Link from "next/link";
import Image from "next/image";
import { getAuthSession } from "@/lib/auth-session";
import CartBadge from "@/components/cart-badge";
import AdminAlertsBadge from "@/components/admin-alerts-badge";
import MobileHeaderMenu from "@/components/mobile-header-menu";

const navigationItems = [
  { href: "/catalog", label: "FLOWERS" },
  { href: "/balloons", label: "BALOONS" },
  { href: "/gifts", label: "GIFTS" },
  { href: "/event-space", label: "EVENT SPACE" },
  { href: "/reviews", label: "REVIEWS" },
  { href: "/contact", label: "CONTACT" },
];

export default async function Header() {
  const { user } = await getAuthSession();
  const isAdmin = user?.role === "ADMIN";
  const isSignedIn = Boolean(user);

  return (
    <header className="site-header sticky top-0 z-50 border-b border-white/60 bg-white/70 backdrop-blur-xl">
      <div className="relative mx-auto w-full max-w-6xl px-4 py-3 sm:px-6 sm:py-4 lg:px-8">
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
                className="h-10 w-auto max-[420px]:h-9 sm:h-12"
              />
            </Link>
            <nav className="hidden items-center gap-3 text-[10px] uppercase tracking-[0.2em] text-stone-500 xl:gap-4 xl:text-xs xl:tracking-[0.24em] lg:flex">
              {navigationItems.map((item) => (
                <Link key={item.href} href={item.href} className="whitespace-nowrap hover:text-stone-700">
                  {item.label}
                </Link>
              ))}
              {isAdmin ? (
                <Link
                  href="/admin"
                  className="relative inline-flex items-center whitespace-nowrap hover:text-stone-700"
                >
                  Admin
                  <AdminAlertsBadge />
                </Link>
              ) : null}
            </nav>
          </div>
          <div className="flex shrink-0 items-center gap-1.5 sm:gap-3">
            {isAdmin ? (
              <Link
                href="/admin"
                className="relative inline-flex rounded-full border border-stone-200 bg-white/80 px-2 py-2 text-[9px] uppercase tracking-[0.15em] text-stone-600 transition hover:border-stone-300 hover:text-stone-900 sm:px-4 sm:text-xs sm:tracking-[0.3em] lg:hidden"
              >
                Admin
                <AdminAlertsBadge />
              </Link>
            ) : null}
            <Link
              href={isSignedIn ? "/account" : "/auth"}
              className="rounded-full border border-stone-200 bg-white/80 px-2 py-2 text-[9px] uppercase tracking-[0.15em] text-stone-600 sm:px-4 sm:text-xs sm:tracking-[0.3em]"
            >
              {isSignedIn ? "Account" : "Sign in"}
            </Link>
            <CartBadge />
            <MobileHeaderMenu items={navigationItems} />
          </div>
        </div>
      </div>
    </header>
  );
}
