import Link from "next/link";
import Image from "next/image";
import { getAuthSession } from "@/lib/auth-session";
import CartBadge from "@/components/cart-badge";
import AdminAlertsBadge from "@/components/admin-alerts-badge";
import MobileHeaderMenu from "@/components/mobile-header-menu";

const navigationItems = [
  { href: "/catalog", label: "SHOP ALL" },
  { href: "/reviews", label: "REVIEWS" },
  { href: "/contact", label: "CONTACT" },
];

const headerActionClass =
  "relative items-center whitespace-nowrap rounded-full border border-stone-200 bg-white/80 uppercase text-stone-600 transition hover:border-stone-300 hover:text-stone-900 sm:px-4 sm:py-2 sm:text-xs sm:tracking-[0.3em]";

export default async function Header() {
  const { user } = await getAuthSession();
  const isAdmin = user?.role === "ADMIN";
  const isSignedIn = Boolean(user);
  const mobileNavigationItems = [
    {
      href: isSignedIn ? "/account" : "/auth",
      label: isSignedIn ? "ACCOUNT" : "SIGN IN",
    },
    ...navigationItems.filter((item) => item.href !== "/catalog"),
  ];
  const mobileActionSize = isAdmin
    ? "px-2.5 py-[7px] text-[10px] tracking-[0.18em]"
    : "px-3 py-2 text-[11px] tracking-[0.22em]";

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
            <Link
              href="/catalog"
              className={`inline-flex ${headerActionClass} ${mobileActionSize} lg:hidden`}
            >
              Shop all
            </Link>
            {isAdmin ? (
              <Link
                href="/admin"
                className={`inline-flex ${headerActionClass} ${mobileActionSize} lg:hidden`}
              >
                Admin
                <AdminAlertsBadge />
              </Link>
            ) : null}
            <Link
              href={isSignedIn ? "/account" : "/auth"}
              className={`${headerActionClass} hidden px-3 py-2 text-[11px] tracking-[0.22em] lg:inline-flex`}
            >
              {isSignedIn ? "Account" : "Sign in"}
            </Link>
            <CartBadge compact={isAdmin} />
            <MobileHeaderMenu items={mobileNavigationItems} compact={isAdmin} />
          </div>
        </div>
      </div>
    </header>
  );
}
