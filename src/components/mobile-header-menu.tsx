"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { usePathname } from "next/navigation";

type NavigationItem = {
  href: string;
  label: string;
};

type MobileHeaderMenuProps = {
  items: NavigationItem[];
  compact?: boolean;
};

export default function MobileHeaderMenu({
  items,
  compact = false,
}: MobileHeaderMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const pathname = usePathname();
  const menuId = useId();
  const overlayRef = useRef<HTMLDivElement | null>(null);
  const portalRoot =
    typeof document === "undefined"
      ? null
      : document.getElementById("lightbox-root") ?? document.body;

  useEffect(() => {
    if (!isOpen) return;

    const previousBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsOpen(false);
    };

    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      document.body.style.overflow = previousBodyOverflow;
    };
  }, [isOpen]);

  const closeMenu = () => setIsOpen(false);

  const handleOverlayClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (event.target === overlayRef.current) {
      closeMenu();
    }
  };

  return (
    <div className="relative lg:hidden">
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-expanded={isOpen}
        aria-controls={menuId}
        aria-label={isOpen ? "Close navigation menu" : "Open navigation menu"}
        className={`inline-flex items-center justify-center rounded-full border border-stone-200 bg-white/80 text-stone-600 shadow-sm transition hover:border-stone-300 hover:text-stone-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand)] focus-visible:ring-offset-2 ${
          compact ? "h-[29px] w-[29px]" : "h-8 w-8"
        }`}
      >
        {isOpen ? (
          <svg
            aria-hidden="true"
            viewBox="0 0 20 20"
            className="h-4 w-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
          >
            <path d="m5 5 10 10M15 5 5 15" />
          </svg>
        ) : (
          <svg
            aria-hidden="true"
            viewBox="0 0 20 20"
            className="h-4 w-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
          >
            <path d="M3.5 5.5h13M3.5 10h13M3.5 14.5h13" />
          </svg>
        )}
      </button>

      {isOpen && portalRoot
        ? createPortal(
            <div
              ref={overlayRef}
              id={menuId}
              role="dialog"
              aria-modal="true"
              aria-label="Mobile navigation"
              onClick={handleOverlayClick}
              className="fixed inset-0 z-[45] flex items-start justify-center bg-stone-900/55 px-4 pb-6 pt-[calc(4rem+1.5rem)] backdrop-blur-[3px] sm:px-6 sm:pb-8 sm:pt-[calc(5rem+2rem)]"
            >
              <nav
                aria-label="Mobile navigation"
                className="grid w-full max-w-md animate-rise gap-2 rounded-[28px] border border-white/90 bg-white/95 p-3 shadow-[0_22px_60px_rgba(var(--brand-rgb),0.2)] backdrop-blur-xl"
              >
                {items.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={closeMenu}
                    className={`rounded-2xl px-4 py-3 text-xs uppercase tracking-[0.22em] text-stone-600 transition hover:bg-[color:var(--brand)]/10 hover:text-stone-900 ${
                      pathname === item.href
                        ? "bg-[color:var(--brand)]/10 text-stone-900"
                        : ""
                    }`}
                  >
                    {item.label}
                  </Link>
                ))}
              </nav>
            </div>,
            portalRoot
          )
        : null}
    </div>
  );
}
