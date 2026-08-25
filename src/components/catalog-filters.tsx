"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  BOUQUET_TYPE_FILTERS,
  CATALOG_SORT_VALUES,
  COLOR_OPTIONS,
  FLOWER_TYPES,
  PRICE_LIMITS,
} from "@/lib/constants";
import { normalizeColorValue } from "@/lib/colors";
import MultiCheckboxDropdown from "@/components/multi-checkbox-dropdown";
import FiltersToggleButton from "@/components/filters-toggle-button";

type FilterFormValues = {
  flowers: string[];
  color: string;
  bouquetType: string;
  min: string;
  max: string;
  sort: string;
};

type DropdownField = "color" | "bouquetType" | "sort";

export type FilterOption = {
  value: string;
  label: string;
};

const toUniqueArray = (values: string[]) =>
  values.filter((value, index) => values.indexOf(value) === index);

const resolveBouquetType = (searchParams: { get: (key: string) => string | null }) => {
  const direct = String(searchParams.get("bouquetType") || "")
    .trim()
    .toLowerCase();
  if (direct === "mono" || direct === "mixed" || direct === "season") {
    return direct;
  }
  const legacyMixed = String(searchParams.get("mixed") || "")
    .trim()
    .toLowerCase();
  if (legacyMixed === "mono" || legacyMixed === "mixed") {
    return legacyMixed;
  }
  if (String(searchParams.get("style") || "").trim().toLowerCase() === "season") {
    return "season";
  }
  return "";
};

const readSearchParams = (searchParams: { get: (key: string) => string | null }): FilterFormValues => {
  const selectedFlowers = toUniqueArray(
    String(searchParams.get("flower") || "")
      .split(",")
      .map((value) => value.trim().toUpperCase())
      .filter((value) => (FLOWER_TYPES as readonly string[]).includes(value))
      .map((value) => value.toLowerCase())
  );

  return {
    flowers: selectedFlowers,
    color: normalizeColorValue(searchParams.get("color") || ""),
    bouquetType: resolveBouquetType(searchParams),
    min: searchParams.get("min") || "",
    max: searchParams.get("max") || "",
    sort: searchParams.get("sort") || "",
  };
};

const formatLabel = (value: string) =>
  value
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");

const formatBouquetTypeLabel = (value: string) =>
  value.trim().toLowerCase() === "season" ? "Seasonal" : formatLabel(value);

type FilterDropdownProps = {
  label: string;
  value: string;
  options: FilterOption[];
  isOpen: boolean;
  onToggle: () => void;
  onSelect: (value: string) => void;
  onClose: () => void;
  controlId: string;
  showCurrentLabel?: boolean;
};

export function FilterDropdown({
  label,
  value,
  options,
  isOpen,
  onToggle,
  onSelect,
  onClose,
  controlId,
  showCurrentLabel = true,
}: FilterDropdownProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const selectedLabel = useMemo(
    () => options.find((option) => option.value === value)?.label || options[0]?.label || "",
    [options, value]
  );

  useEffect(() => {
    if (!isOpen) return;

    const closeOnOutsideClick = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (rootRef.current?.contains(target)) return;
      onClose();
    };

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };

    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);

    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [isOpen, onClose]);

  return (
    <div
      ref={rootRef}
      className={`relative flex min-w-0 flex-col gap-2 text-sm text-stone-700 ${
        isOpen ? "z-30" : "z-0"
      }`}
    >
      <span>{label}</span>
      <button
        type="button"
        id={`${controlId}-button`}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={`${controlId}-listbox`}
        onClick={onToggle}
        data-open={isOpen}
        className="custom-select-trigger"
      >
        <span className="pr-8">{selectedLabel}</span>
        <svg
          aria-hidden="true"
          viewBox="0 0 16 16"
          className={`absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[color:var(--brand)] transition-transform ${
            isOpen ? "rotate-180" : ""
          }`}
        >
          <path
            d="M3.5 6.5L8 11l4.5-4.5"
            stroke="currentColor"
            strokeWidth="1.7"
            fill="none"
            strokeLinecap="round"
          />
        </svg>
      </button>
      {isOpen ? (
        <div
          role="listbox"
          id={`${controlId}-listbox`}
          aria-labelledby={`${controlId}-button`}
          className="custom-select-panel"
        >
          {options.map((option) => {
            const active = option.value === value;
            return (
              <button
                key={option.value || "__empty"}
                type="button"
                role="option"
                aria-selected={active}
                data-active={active}
                onClick={() => {
                  onSelect(option.value);
                  onClose();
                }}
                className="custom-select-option"
              >
                <span>{option.label}</span>
                {active && showCurrentLabel ? (
                  <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[color:var(--brand)]">
                    Current
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

export default function CatalogFilters() {
  const searchParams = useSearchParams();
  const values = useMemo(() => readSearchParams(searchParams), [searchParams]);

  return <CatalogFiltersForm key={searchParams.toString()} initialValues={values} />;
}

type CatalogFiltersFormProps = {
  initialValues: FilterFormValues;
};

function CatalogFiltersForm({ initialValues }: CatalogFiltersFormProps) {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement | null>(null);
  const [formValues, setFormValues] = useState<FilterFormValues>(initialValues);
  const [isFiltersOpen, setIsFiltersOpen] = useState(false);
  const [openDropdown, setOpenDropdown] = useState<DropdownField | null>(null);
  const priceFieldClass =
    "h-11 w-full min-w-0 rounded-2xl border border-stone-200 bg-white/80 px-4 py-0 text-[0.93rem] leading-[1.35] text-stone-800 outline-none focus:border-[color:var(--brand)]";

  const dropdownOptions = useMemo(
    () => ({
      flower: FLOWER_TYPES.map((option) => ({
        value: option.toLowerCase(),
        label: formatLabel(option),
      })),
      color: [
        { value: "", label: "Any color" },
        ...COLOR_OPTIONS.map((option) => ({ value: option, label: formatLabel(option) })),
      ],
      bouquetType: [
        { value: "", label: "All bouquets" },
        ...BOUQUET_TYPE_FILTERS.filter((value) => value !== "all").map((value) => ({
          value,
          label: `${formatBouquetTypeLabel(value)} bouquet`,
        })),
      ],
      sort: [
        { value: "", label: "Default order" },
        ...CATALOG_SORT_VALUES.map((value) => {
          if (value === "name_asc") {
            return { value, label: "Name (A-Z)" };
          }
          if (value === "name_desc") {
            return { value, label: "Name (Z-A)" };
          }
          if (value === "price_asc") {
            return { value, label: "Price (low-high)" };
          }
          return { value, label: "Price (high-low)" };
        }),
      ],
    }),
    []
  );

  const setDropdownValue = (field: DropdownField, value: string) => {
    setFormValues((current) => ({ ...current, [field]: value }));
  };

  const toggleFlower = (value: string) => {
    setFormValues((current) => {
      const exists = current.flowers.includes(value);
      const nextFlowers = exists
        ? current.flowers.filter((entry) => entry !== value)
        : [...current.flowers, value];
      return { ...current, flowers: toUniqueArray(nextFlowers) };
    });
  };

  const hasFilters = useMemo(
    () =>
      [
        formValues.flowers.length > 0,
        formValues.color,
        formValues.bouquetType,
        formValues.min,
        formValues.max,
        formValues.sort,
      ].some(Boolean),
    [formValues]
  );

  const applyFilters = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const { flowers, color, bouquetType, min, max, sort } = formValues;

    const params = new URLSearchParams();
    params.set("entry", "1");
    if (flowers.length) {
      params.set("flower", flowers.join(","));
    }
    if (color) params.set("color", color);
    if (bouquetType) params.set("bouquetType", bouquetType);
    if (min) params.set("min", min);
    if (max) params.set("max", max);
    if (sort) params.set("sort", sort);
    const query = params.toString();
    router.push(query ? `/catalog?${query}` : "/catalog");
  };

  return (
    <div className="glass relative z-20 max-w-full rounded-[28px] border border-white/80 p-4 sm:p-6">
      <FiltersToggleButton
        isOpen={isFiltersOpen}
        onClick={() => {
          setOpenDropdown(null);
          setIsFiltersOpen((current) => !current);
        }}
        className="w-full"
      />
      {isFiltersOpen ? (
        <>
          <form
            ref={formRef}
            onSubmit={applyFilters}
            className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3"
          >
            <MultiCheckboxDropdown
              label="Flower type"
              controlId="catalog-filter-flowers"
              options={dropdownOptions.flower}
              values={formValues.flowers}
              onToggle={toggleFlower}
              onClear={() => setFormValues((current) => ({ ...current, flowers: [] }))}
              emptyLabel="All flowers"
            />
            <FilterDropdown
              label="Palette"
              controlId="catalog-filter-color"
              value={formValues.color}
              options={dropdownOptions.color}
              isOpen={openDropdown === "color"}
              onToggle={() => setOpenDropdown((current) => (current === "color" ? null : "color"))}
              onClose={() => setOpenDropdown(null)}
              onSelect={(value) => setDropdownValue("color", value)}
            />
            <FilterDropdown
              label="Bouquet type"
              controlId="catalog-filter-bouquet-type"
              value={formValues.bouquetType}
              options={dropdownOptions.bouquetType}
              isOpen={openDropdown === "bouquetType"}
              onToggle={() =>
                setOpenDropdown((current) => (current === "bouquetType" ? null : "bouquetType"))
              }
              onClose={() => setOpenDropdown(null)}
              onSelect={(value) => setDropdownValue("bouquetType", value)}
            />
            <label className="flex flex-col gap-2 text-sm text-stone-700">
              Min price (${PRICE_LIMITS.min})
              <input
                type="number"
                name="min"
                value={formValues.min}
                onChange={(event) =>
                  setFormValues((current) => ({ ...current, min: event.target.value }))
                }
                min={PRICE_LIMITS.min}
                placeholder="45"
                className={priceFieldClass}
              />
            </label>
            <label className="flex flex-col gap-2 text-sm text-stone-700">
              Max price (${PRICE_LIMITS.max})
              <input
                type="number"
                name="max"
                value={formValues.max}
                onChange={(event) =>
                  setFormValues((current) => ({ ...current, max: event.target.value }))
                }
                max={PRICE_LIMITS.max}
                placeholder="200"
                className={priceFieldClass}
              />
            </label>
            <FilterDropdown
              label="Sort by"
              controlId="catalog-filter-sort"
              value={formValues.sort}
              options={dropdownOptions.sort}
              isOpen={openDropdown === "sort"}
              onToggle={() => setOpenDropdown((current) => (current === "sort" ? null : "sort"))}
              onClose={() => setOpenDropdown(null)}
              onSelect={(value) => setDropdownValue("sort", value)}
            />
          </form>
          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => formRef.current?.requestSubmit()}
              className="inline-flex h-11 w-full items-center justify-center rounded-full bg-[color:var(--brand)] px-6 text-xs uppercase tracking-[0.3em] text-white transition hover:bg-[color:var(--brand-dark)] sm:w-auto"
            >
              Apply filters
            </button>
            {hasFilters ? (
              <button
                type="button"
                onClick={() => router.push("/catalog?entry=1")}
                className="inline-flex h-11 w-full items-center justify-center rounded-full border border-stone-200 bg-white/80 px-5 text-xs uppercase tracking-[0.3em] text-stone-600 sm:w-auto"
              >
                Clear
              </button>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}
