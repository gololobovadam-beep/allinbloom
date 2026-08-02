"use client";

import { useMemo, useState } from "react";
import { useFormStatus } from "react-dom";
import type { StoreSettings } from "@/lib/api-types";
import { COLOR_OPTIONS, FLOWER_TYPES } from "@/lib/constants";
import { normalizeColorValue } from "@/lib/colors";
import SingleSelectDropdown from "@/components/single-select-dropdown";

type AdminDiscountsFormProps = {
  settings: StoreSettings;
  action: (formData: FormData) => Promise<void>;
};

const fieldClass = (isInvalid: boolean) =>
  `h-11 w-full min-w-0 rounded-2xl bg-white/80 px-4 py-0 text-sm text-stone-800 outline-none ${
    isInvalid
      ? "border border-rose-300 focus:border-rose-500"
      : "border border-stone-200 focus:border-stone-400"
  }`;

const parseNumber = (value: FormDataEntryValue | null) => {
  const raw = String(value || "").trim();
  if (!raw) return 0;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : 0;
};

const parsePrice = (value: FormDataEntryValue | null) => {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
};

const formatLabel = (value: string) =>
  value
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");

function SubmitButton() {
  const { pending } = useFormStatus();

  return (
    <button
      type="submit"
      disabled={pending}
      className="inline-flex h-11 w-full items-center justify-center rounded-full bg-[color:var(--brand)] px-6 text-xs uppercase tracking-[0.3em] text-white transition hover:bg-[color:var(--brand-dark)] disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
    >
      {pending ? "Saving..." : "Save discounts"}
    </button>
  );
}

export default function AdminDiscountsForm(props: AdminDiscountsFormProps) {
  // These controls are local, editable selections. Recreate just the form
  // state when their server-provided defaults change instead of synchronizing
  // them in an effect after render.
  const categoryDefaultsKey = JSON.stringify([
    props.settings.categoryFlowerType || "",
    props.settings.categoryMixed || "",
    props.settings.categoryColor || "",
  ]);

  return <AdminDiscountsFormEditor key={categoryDefaultsKey} {...props} />;
}

function AdminDiscountsFormEditor({
  settings,
  action,
}: AdminDiscountsFormProps) {
  const [errors, setErrors] = useState<string[]>([]);
  const [invalidFields, setInvalidFields] = useState<string[]>([]);
  const [categoryFlowerType, setCategoryFlowerType] = useState(
    settings.categoryFlowerType || ""
  );
  const [categoryMixed, setCategoryMixed] = useState(settings.categoryMixed || "");
  const [categoryColor, setCategoryColor] = useState(
    normalizeColorValue(settings.categoryColor || "")
  );

  const invalidSet = useMemo(() => new Set(invalidFields), [invalidFields]);
  const flowerTypeOptions = useMemo(
    () => [
      { value: "", label: "Any" },
      ...FLOWER_TYPES.map((type) => ({ value: type, label: formatLabel(type) })),
    ],
    []
  );
  const bouquetTypeOptions = useMemo(
    () => [
      { value: "", label: "All bouquets" },
      { value: "mixed", label: "Mixed" },
      { value: "mono", label: "Mono" },
      { value: "season", label: "Seasonal" },
    ],
    []
  );
  const colorOptions = useMemo(
    () => [
      { value: "", label: "Any" },
      ...COLOR_OPTIONS.map((color) => ({ value: color, label: formatLabel(color) })),
    ],
    []
  );

  const onSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    const formData = new FormData(event.currentTarget);
    const nextErrors: string[] = [];
    const nextInvalid = new Set<string>();

    const globalPercent = parseNumber(formData.get("globalDiscountPercent"));
    const categoryPercent = parseNumber(formData.get("categoryDiscountPercent"));
    const firstPercent = parseNumber(formData.get("firstOrderDiscountPercent"));

    const globalNote = String(formData.get("globalDiscountNote") || "").trim();
    const categoryNote = String(formData.get("categoryDiscountNote") || "").trim();
    const firstNote = String(formData.get("firstOrderDiscountNote") || "").trim();

    const categoryFlowerType = String(formData.get("categoryFlowerType") || "").trim();
    const categoryMixed = String(formData.get("categoryMixed") || "").trim();
    const categoryColor = normalizeColorValue(String(formData.get("categoryColor") || "").trim());
    const categoryMinPrice = parsePrice(formData.get("categoryMinPrice"));
    const categoryMaxPrice = parsePrice(formData.get("categoryMaxPrice"));

    if (globalPercent > 0 && categoryPercent > 0) {
      nextErrors.push(
        "Global and category discounts cannot be active together. Disable one of them."
      );
      nextInvalid.add("globalDiscountPercent");
      nextInvalid.add("categoryDiscountPercent");
    }

    if (globalPercent > 0 && !globalNote) {
      nextErrors.push("Global discount comment is required when global discount is active.");
      nextInvalid.add("globalDiscountNote");
    }

    const hasCategoryFilter = Boolean(
      categoryFlowerType ||
        categoryMixed ||
        categoryColor ||
        categoryMinPrice !== null ||
        categoryMaxPrice !== null
    );

    if (categoryPercent > 0 && !categoryNote) {
      nextErrors.push("Category discount comment is required when category discount is active.");
      nextInvalid.add("categoryDiscountNote");
    }

    if (categoryPercent > 0 && !hasCategoryFilter) {
      nextErrors.push("Category discount requires at least one filter.");
      nextInvalid.add("categoryFlowerType");
      nextInvalid.add("categoryMixed");
      nextInvalid.add("categoryColor");
      nextInvalid.add("categoryMinPrice");
      nextInvalid.add("categoryMaxPrice");
    }

    if (
      categoryMinPrice !== null &&
      categoryMaxPrice !== null &&
      categoryMinPrice > categoryMaxPrice
    ) {
      nextErrors.push("Category min price must be less than or equal to max price.");
      nextInvalid.add("categoryMinPrice");
      nextInvalid.add("categoryMaxPrice");
    }

    if (firstPercent > 0 && !firstNote) {
      nextErrors.push("First order discount comment is required when first order discount is active.");
      nextInvalid.add("firstOrderDiscountNote");
    }

    if (nextErrors.length) {
      event.preventDefault();
      setErrors(nextErrors);
      setInvalidFields(Array.from(nextInvalid));
      return;
    }

    setErrors([]);
    setInvalidFields([]);
  };

  return (
    <form
      action={action}
      onSubmit={onSubmit}
      className="glass relative z-10 max-w-full space-y-6 rounded-[28px] border border-white/80 p-4 sm:p-6"
    >
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="min-w-0 space-y-4">
          <h2 className="text-lg font-semibold text-stone-900">
            Global discount
          </h2>
          <label className="flex flex-col gap-2 text-sm text-stone-700">
            Discount percent
            <input
              name="globalDiscountPercent"
              type="number"
              min="0"
              max="90"
              defaultValue={settings.globalDiscountPercent}
              className={fieldClass(invalidSet.has("globalDiscountPercent"))}
            />
          </label>
          <label className="flex flex-col gap-2 text-sm text-stone-700">
            Discount comment
            <input
              name="globalDiscountNote"
              defaultValue={settings.globalDiscountNote || ""}
              placeholder="Reason for discount"
              className={fieldClass(invalidSet.has("globalDiscountNote"))}
            />
          </label>
        </div>

        <div className="min-w-0 space-y-4">
          <h2 className="text-lg font-semibold text-stone-900">
            First order discount
          </h2>
          <label className="flex flex-col gap-2 text-sm text-stone-700">
            Discount percent
            <input
              name="firstOrderDiscountPercent"
              type="number"
              min="0"
              max="90"
              defaultValue={settings.firstOrderDiscountPercent}
              className={fieldClass(false)}
            />
          </label>
          <label className="flex flex-col gap-2 text-sm text-stone-700">
            Discount comment
            <input
              name="firstOrderDiscountNote"
              defaultValue={settings.firstOrderDiscountNote || ""}
              placeholder="Reason for discount"
              className={fieldClass(invalidSet.has("firstOrderDiscountNote"))}
            />
          </label>
        </div>
      </div>

      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-stone-900">
          Category discount
        </h2>
        <div className="grid gap-4 lg:grid-cols-2">
          <label className="flex flex-col gap-2 text-sm text-stone-700">
            Discount percent
            <input
              name="categoryDiscountPercent"
              type="number"
              min="0"
              max="90"
              defaultValue={settings.categoryDiscountPercent}
              className={fieldClass(invalidSet.has("categoryDiscountPercent"))}
            />
          </label>
          <SingleSelectDropdown
            label="Flower type"
            controlId="admin-discount-flower-type"
            name="categoryFlowerType"
            value={categoryFlowerType}
            options={flowerTypeOptions}
            onChange={setCategoryFlowerType}
            invalid={invalidSet.has("categoryFlowerType")}
          />
          <label className="flex flex-col gap-2 text-sm text-stone-700">
            Discount comment
            <input
              name="categoryDiscountNote"
              defaultValue={settings.categoryDiscountNote || ""}
              placeholder="Reason for discount"
              className={fieldClass(invalidSet.has("categoryDiscountNote"))}
            />
          </label>
          <SingleSelectDropdown
            label="Bouquet type"
            controlId="admin-discount-bouquet-type"
            name="categoryMixed"
            value={categoryMixed}
            options={bouquetTypeOptions}
            onChange={setCategoryMixed}
            invalid={invalidSet.has("categoryMixed")}
          />
          <SingleSelectDropdown
            label="Color"
            controlId="admin-discount-color"
            name="categoryColor"
            value={categoryColor}
            options={colorOptions}
            onChange={setCategoryColor}
            invalid={invalidSet.has("categoryColor")}
          />
          <label className="flex flex-col gap-2 text-sm text-stone-700">
            Min price (USD)
            <input
              name="categoryMinPrice"
              type="number"
              step="0.01"
              min="0"
              defaultValue={
                settings.categoryMinPriceCents !== null
                  ? (settings.categoryMinPriceCents / 100).toFixed(2)
                  : ""
              }
              className={fieldClass(invalidSet.has("categoryMinPrice"))}
            />
          </label>
          <label className="flex flex-col gap-2 text-sm text-stone-700">
            Max price (USD)
            <input
              name="categoryMaxPrice"
              type="number"
              step="0.01"
              min="0"
              defaultValue={
                settings.categoryMaxPriceCents !== null
                  ? (settings.categoryMaxPriceCents / 100).toFixed(2)
                  : ""
              }
              className={fieldClass(invalidSet.has("categoryMaxPrice"))}
            />
          </label>
        </div>
      </div>

      {errors.length ? (
        <div className="rounded-2xl border border-rose-300 bg-rose-50/80 px-4 py-3 text-sm text-rose-700">
          <p className="font-semibold">Please fix the following before saving:</p>
          <ul className="mt-2 list-disc pl-5">
            {errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-3">
        <SubmitButton />
        <p className="text-xs uppercase tracking-[0.24em] text-stone-500">
          Category and global discounts cannot be active together
        </p>
      </div>
    </form>
  );
}
