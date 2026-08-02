"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useFormStatus } from "react-dom";
import type { Bouquet } from "@/lib/api-types";
import { BOUQUET_TYPES, COLOR_OPTIONS, FLOWER_TYPES } from "@/lib/constants";
import { normalizeColorValue } from "@/lib/colors";
import {
  FLOWER_QUANTITY_MAX,
  FLOWER_QUANTITY_MIN,
} from "@/lib/flower-quantity";
import { formatLabel } from "@/lib/format";
import AdminImageList from "@/components/admin-image-list";
import MultiCheckboxDropdown from "@/components/multi-checkbox-dropdown";
import SingleSelectDropdown from "@/components/single-select-dropdown";
import { getBouquetGalleryImages } from "@/lib/bouquet-images";

type AdminBouquetFormProps = {
  bouquet?: Bouquet;
  action: (formData: FormData) => Promise<void>;
};

const fieldStateClass = (isInvalid: boolean) =>
  isInvalid
    ? "border border-rose-300 focus:border-rose-500"
    : "border border-stone-200 focus:border-stone-400";

const controlFieldClass = (isInvalid: boolean) =>
  `h-11 w-full min-w-0 rounded-2xl bg-white/80 px-4 py-0 text-sm text-stone-800 outline-none ${fieldStateClass(
    isInvalid
  )}`;

const textareaFieldClass = (isInvalid: boolean) =>
  `w-full min-w-0 rounded-2xl bg-white/80 px-4 py-3 text-sm text-stone-800 outline-none ${fieldStateClass(
    isInvalid
  )}`;

const COLOR_OPTIONS_SET = new Set<string>(COLOR_OPTIONS);
const FLOWER_TYPE_SET = new Set<string>(FLOWER_TYPES);

const parsePaletteColors = (value: string | undefined) =>
  String(value || "")
    .split(",")
    .map((item) => normalizeColorValue(item) || item.trim().toLowerCase())
    .filter(Boolean)
    .filter((item, idx, arr) => arr.indexOf(item) === idx);

const sortPaletteColors = (values: string[]) => {
  const known = COLOR_OPTIONS.filter((color) => values.includes(color));
  const unknown = values.filter((value) => !COLOR_OPTIONS_SET.has(value));
  return [...known, ...unknown];
};

const formatPaletteLabel = (value: string) =>
  formatLabel(value);

const parseNumber = (value: FormDataEntryValue | null) => {
  const raw = String(value || "").trim();
  if (!raw) return NaN;
  return Number(raw);
};

const parseSelectedFlowerTypes = (bouquet?: Bouquet) => {
  const fromStyle = String(bouquet?.style || "")
    .split(",")
    .map((item) => item.trim().toUpperCase())
    .filter((item) => FLOWER_TYPE_SET.has(item))
    .filter((item, idx, arr) => arr.indexOf(item) === idx)
    .slice(0, 3);

  if (fromStyle.length) return fromStyle;
  if (bouquet?.flowerType && FLOWER_TYPE_SET.has(bouquet.flowerType)) {
    return [bouquet.flowerType];
  }
  return [FLOWER_TYPES[0]];
};

const resolveDefaultBouquetType = (bouquet?: Bouquet) => {
  const direct = String(bouquet?.bouquetType || "").toUpperCase();
  if ((BOUQUET_TYPES as readonly string[]).includes(direct)) {
    return direct as (typeof BOUQUET_TYPES)[number];
  }
  if (String(bouquet?.style || "").trim().toUpperCase() === "SEASON") {
    return "SEASON";
  }
  return bouquet?.isMixed ? "MIXED" : "MONO";
};

function SubmitButton() {
  const { pending } = useFormStatus();

  return (
    <button
      type="submit"
      disabled={pending}
      className="inline-flex h-11 w-full items-center justify-center rounded-full bg-[color:var(--brand)] px-6 text-xs uppercase tracking-[0.3em] text-white transition hover:bg-[color:var(--brand-dark)] disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
    >
      {pending ? "Saving..." : "Save bouquet"}
    </button>
  );
}

export default function AdminBouquetForm(props: AdminBouquetFormProps) {
  // Editing a different bouquet should start with that bouquet's defaults.
  // A keyed editor resets local form state before paint instead of issuing a
  // second render from an effect after the product has changed.
  return (
    <AdminBouquetFormEditor
      key={props.bouquet?.id ?? "new-bouquet"}
      {...props}
    />
  );
}

function AdminBouquetFormEditor({
  bouquet,
  action,
}: AdminBouquetFormProps) {
  const [errors, setErrors] = useState<string[]>([]);
  const [invalidFields, setInvalidFields] = useState<string[]>([]);
  const [selectedColors, setSelectedColors] = useState<string[]>(() =>
    sortPaletteColors(parsePaletteColors(bouquet?.colors))
  );
  const [selectedFlowerTypes, setSelectedFlowerTypes] = useState<string[]>(() =>
    parseSelectedFlowerTypes(bouquet)
  );
  const [flowerTypeLimitWarning, setFlowerTypeLimitWarning] = useState("");
  const [bouquetTypeWarning, setBouquetTypeWarning] = useState("");
  const [selectedBouquetType, setSelectedBouquetType] = useState<
    (typeof BOUQUET_TYPES)[number]
  >(() => resolveDefaultBouquetType(bouquet));
  const [isFlowerQuantityEnabled, setIsFlowerQuantityEnabled] = useState(
    bouquet ? bouquet.allowFlowerQuantity : true
  );
  const [isColorMenuOpen, setIsColorMenuOpen] = useState(false);
  const colorMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isColorMenuOpen) return;

    const closeOnOutsideClick = (event: PointerEvent) => {
      if (
        colorMenuRef.current &&
        !colorMenuRef.current.contains(event.target as Node)
      ) {
        setIsColorMenuOpen(false);
      }
    };

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsColorMenuOpen(false);
      }
    };

    window.addEventListener("pointerdown", closeOnOutsideClick);
    window.addEventListener("keydown", closeOnEscape);

    return () => {
      window.removeEventListener("pointerdown", closeOnOutsideClick);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [isColorMenuOpen]);

  const invalidSet = useMemo(() => new Set(invalidFields), [invalidFields]);
  const selectedColorsValue = useMemo(
    () => selectedColors.join(", "),
    [selectedColors]
  );
  const selectedFlowerTypesValue = useMemo(
    () => selectedFlowerTypes.join(", "),
    [selectedFlowerTypes]
  );
  const selectedColorsLabel = useMemo(() => {
    if (!selectedColors.length) return "Select colors";
    const preview = selectedColors.slice(0, 3).map(formatPaletteLabel).join(", ");
    const hiddenCount = selectedColors.length - 3;
    return hiddenCount > 0 ? `${preview} +${hiddenCount}` : preview;
  }, [selectedColors]);
  const flowerTypeOptions = useMemo(
    () =>
      FLOWER_TYPES.map((type) => ({
        value: type,
        label: formatLabel(type),
      })),
    []
  );
  const bouquetTypeOptions = useMemo(
    () =>
      BOUQUET_TYPES.map((type) => ({
        value: type,
        label: type === "SEASON" ? "Seasonal" : formatLabel(type),
      })),
    []
  );

  const toggleColorOption = (color: string) => {
    setSelectedColors((current) => {
      if (current.includes(color)) {
        return current.filter((value) => value !== color);
      }
      return sortPaletteColors([...current, color]);
    });
  };

  const toggleFlowerTypeOption = (flowerType: string) => {
    setSelectedFlowerTypes((current) => {
      if (current.includes(flowerType)) {
        const next = current.filter((value) => value !== flowerType);
        setFlowerTypeLimitWarning("");
        setBouquetTypeWarning("");
        return next.length ? next : [flowerType];
      }
      if (current.length >= 3) {
        setFlowerTypeLimitWarning("You can select up to 3 flower types.");
        return current;
      }
      setFlowerTypeLimitWarning("");
      const next = [...current, flowerType];
      if (next.length > 1 && selectedBouquetType !== "MIXED") {
        setSelectedBouquetType("MIXED");
      }
      return next;
    });
  };

  const handleBouquetTypeChange = (
    nextType: (typeof BOUQUET_TYPES)[number]
  ) => {
    if (selectedFlowerTypes.length > 1 && nextType !== "MIXED") {
      setBouquetTypeWarning("For multiple flower types choose mixed bouquet type.");
      return;
    }
    setBouquetTypeWarning("");
    setSelectedBouquetType(nextType);
  };

  const onSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    const formData = new FormData(event.currentTarget);
    const nextErrors: string[] = [];
    const nextInvalid = new Set<string>();

    const name = String(formData.get("name") || "").trim();
    const description = String(formData.get("description") || "").trim();
    const galleryImages = formData
      .getAll("galleryImages")
      .map((value) => String(value || "").trim())
      .filter(Boolean);
    const price = parseNumber(formData.get("price"));
    const discountPercent = Math.max(
      0,
      Math.min(90, Math.round(parseNumber(formData.get("discountPercent")) || 0))
    );
    const discountNote = String(formData.get("discountNote") || "").trim();
    const allowFlowerQuantity = formData.get("allowFlowerQuantity") === "on";
    const defaultFlowerQuantity = parseNumber(
      formData.get("defaultFlowerQuantity")
    );

    if (!name) {
      nextErrors.push("Bouquet name is required.");
      nextInvalid.add("name");
    }

    if (!description) {
      nextErrors.push("Bouquet description is required.");
      nextInvalid.add("description");
    }

    if (!Number.isFinite(price) || price <= 0) {
      nextErrors.push("Price must be greater than 0.");
      nextInvalid.add("price");
    }

    if (!galleryImages.length) {
      nextErrors.push("Image URL is required.");
      nextInvalid.add("galleryImages");
    }

    if (discountPercent > 0 && !discountNote) {
      nextErrors.push("Discount comment is required when discount percent is greater than 0.");
      nextInvalid.add("discountNote");
    }

    if (
      allowFlowerQuantity &&
      (!Number.isFinite(defaultFlowerQuantity) ||
        defaultFlowerQuantity < FLOWER_QUANTITY_MIN ||
        defaultFlowerQuantity > FLOWER_QUANTITY_MAX)
    ) {
      nextErrors.push(
        `Default flowers quantity must be between ${FLOWER_QUANTITY_MIN} and ${FLOWER_QUANTITY_MAX}.`
      );
      nextInvalid.add("defaultFlowerQuantity");
    }

    if (!selectedFlowerTypes.length) {
      nextErrors.push("At least one flower type is required.");
      nextInvalid.add("flowerTypes");
    }

    if (selectedFlowerTypes.length > 1 && selectedBouquetType !== "MIXED") {
      nextErrors.push("Multiple flower types require mixed bouquet type.");
      nextInvalid.add("bouquetType");
      setBouquetTypeWarning("For multiple flower types choose mixed bouquet type.");
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
      {bouquet ? <input type="hidden" name="id" value={bouquet.id} /> : null}

      <div className="grid gap-6 lg:grid-cols-2 lg:items-start xl:gap-8">
        <div className="min-w-0 grid auto-rows-max gap-4">
          <label className="flex flex-col gap-2 text-sm text-stone-700">
            Name
            <input
              name="name"
              defaultValue={bouquet?.name}
              required
              className={controlFieldClass(invalidSet.has("name"))}
            />
          </label>
          <label className="flex flex-col gap-2 text-sm text-stone-700">
            Description
            <textarea
              name="description"
              defaultValue={bouquet?.description}
              rows={4}
              required
              className={textareaFieldClass(invalidSet.has("description"))}
            />
          </label>
          <div className="grid gap-4 sm:grid-cols-2 sm:items-end">
            <label className="flex flex-col gap-2 text-sm text-stone-700">
              Price (USD)
              <input
                name="price"
                type="number"
                step="0.01"
                min="0"
                defaultValue={
                  bouquet ? (bouquet.priceCents / 100).toFixed(2) : ""
                }
                required
                className={controlFieldClass(invalidSet.has("price"))}
              />
            </label>
            <label className="flex flex-col gap-2 text-sm text-stone-700">
              Default quantity
              <input
                name="defaultFlowerQuantity"
                type="number"
                min={FLOWER_QUANTITY_MIN}
                max={FLOWER_QUANTITY_MAX}
                step="1"
                defaultValue={bouquet?.defaultFlowerQuantity ?? FLOWER_QUANTITY_MIN}
                disabled={!isFlowerQuantityEnabled}
                className={`${controlFieldClass(
                  invalidSet.has("defaultFlowerQuantity")
                )} disabled:cursor-not-allowed disabled:bg-stone-100 disabled:text-stone-400`}
              />
            </label>
            <label className="flex flex-col gap-2 text-sm text-stone-700">
              Discount percent
              <input
                name="discountPercent"
                type="number"
                min="0"
                max="90"
                defaultValue={bouquet?.discountPercent ?? 0}
                className={controlFieldClass(false)}
              />
            </label>
            <label className="flex flex-col gap-2 text-sm text-stone-700 sm:col-span-2">
              Discount comment
              <input
                name="discountNote"
                defaultValue={bouquet?.discountNote || ""}
                placeholder="Reason for discount"
                className={controlFieldClass(invalidSet.has("discountNote"))}
              />
            </label>
          </div>
          <div
            ref={colorMenuRef}
            className="relative z-20 flex flex-col gap-2 text-sm text-stone-700"
          >
            <span>Color palette</span>
            <input type="hidden" name="colors" value={selectedColorsValue} />
            <button
              type="button"
              onClick={() => setIsColorMenuOpen((current) => !current)}
              aria-haspopup="true"
              aria-expanded={isColorMenuOpen}
              className="flex h-11 w-full items-center justify-between rounded-2xl border border-stone-200 bg-white/80 px-4 text-sm text-stone-800 outline-none transition hover:border-stone-300 focus:border-stone-400"
            >
              <span
                className={`truncate text-left ${
                  selectedColors.length ? "text-stone-800" : "text-stone-500"
                }`}
              >
                {selectedColorsLabel}
              </span>
              <svg
                aria-hidden="true"
                viewBox="0 0 20 20"
                fill="none"
                className={`h-4 w-4 text-stone-500 transition-transform ${
                  isColorMenuOpen ? "rotate-180" : ""
                }`}
              >
                <path
                  d="m5 7 5 6 5-6"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
            {isColorMenuOpen ? (
              <div className="absolute left-0 right-0 top-full z-30 mt-2 rounded-2xl border border-stone-200 bg-white p-2 shadow-[0_14px_28px_rgba(28,21,18,0.14)]">
                <div className="max-h-56 space-y-1 overflow-auto pr-1">
                  {COLOR_OPTIONS.map((color) => (
                    <label
                      key={color}
                      className="flex cursor-pointer items-center gap-2 rounded-xl px-2 py-1.5 text-sm text-stone-700 transition hover:bg-stone-50"
                    >
                      <input
                        type="checkbox"
                        checked={selectedColors.includes(color)}
                        onChange={() => toggleColorOption(color)}
                        className="h-4 w-4 accent-[color:var(--brand)]"
                      />
                      <span>{formatPaletteLabel(color)}</span>
                    </label>
                  ))}
                </div>
                <div className="mt-2 flex items-center justify-between border-t border-stone-100 px-1 pt-2">
                  <button
                    type="button"
                    onClick={() => setSelectedColors([])}
                    className="text-[10px] uppercase tracking-[0.2em] text-stone-500 transition hover:text-stone-700"
                  >
                    Clear
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsColorMenuOpen(false)}
                    className="text-[10px] uppercase tracking-[0.2em] text-[color:var(--brand)] transition hover:text-[color:var(--brand-dark)]"
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
        <div className="min-w-0 grid auto-rows-max gap-4">
          <AdminImageList
            name="galleryImages"
            initialImages={bouquet ? getBouquetGalleryImages(bouquet) : []}
            title="Bouquet gallery images"
            description="Add as many photos as needed. Their order is kept, and the first six are used in the public gallery."
            previewAlt="Bouquet gallery image"
            recommendedSize="1000x1000"
          />
          <div className={invalidSet.has("flowerTypes") ? "rounded-2xl border border-rose-300 p-2" : ""}>
            <input type="hidden" name="style" value={selectedFlowerTypesValue} />
            <input
              type="hidden"
              name="flowerType"
              value={selectedFlowerTypes[0] || FLOWER_TYPES[0]}
            />
            {selectedFlowerTypes.map((value) => (
              <input key={value} type="hidden" name="flowerTypes" value={value} />
            ))}
            <MultiCheckboxDropdown
              label="Flower type (up to 3)"
              controlId="admin-bouquet-flower-types"
              options={flowerTypeOptions}
              values={selectedFlowerTypes}
              onToggle={toggleFlowerTypeOption}
              maxSelections={3}
              emptyLabel="Select flower types"
            />
            {flowerTypeLimitWarning ? (
              <p className="text-[11px] uppercase tracking-[0.18em] text-rose-500">
                {flowerTypeLimitWarning}
              </p>
            ) : null}
          </div>
          <div className="relative z-10">
            <SingleSelectDropdown
              label="Bouquet type"
              controlId="admin-bouquet-type"
              name="bouquetType"
              value={selectedBouquetType}
              options={bouquetTypeOptions}
              onChange={(value) =>
                handleBouquetTypeChange(
                  value as (typeof BOUQUET_TYPES)[number]
                )
              }
              invalid={invalidSet.has("bouquetType")}
            />
            {bouquetTypeWarning ? (
              <p className="text-[11px] uppercase tracking-[0.18em] text-rose-500">
                {bouquetTypeWarning}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <label className="flex items-center gap-2 text-sm text-stone-700">
              <input
                type="checkbox"
                name="isFeatured"
                defaultChecked={bouquet?.isFeatured}
              />
              Featured on homepage
            </label>
            <label className="flex items-center gap-2 text-sm text-stone-700">
              <input
                type="checkbox"
                name="isActive"
                defaultChecked={bouquet ? bouquet.isActive : true}
              />
              Visible in catalog
            </label>
            <label className="flex items-center gap-2 text-sm text-stone-700">
              <input
                type="checkbox"
                name="isSoldOut"
                defaultChecked={bouquet?.isSoldOut}
              />
              Sold out
            </label>
            <label className="flex items-center gap-2 text-sm text-stone-700">
              <input
                type="checkbox"
                name="allowFlowerQuantity"
                checked={isFlowerQuantityEnabled}
                onChange={(event) =>
                  setIsFlowerQuantityEnabled(event.target.checked)
                }
              />
              Enable flower quantity input (MONO/SEASON)
            </label>
          </div>
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
          Changes apply instantly
        </p>
      </div>
    </form>
  );
}

