"use client";

import { useState } from "react";
import AdminImageUpload from "@/components/admin-image-upload";

type AdminImageListProps = {
  name: string;
  initialImages?: string[];
  title: string;
  description?: string;
  previewAlt: string;
  recommendedSize?: string;
  required?: boolean;
  columns?: 1 | 2;
};

const cleanImages = (images: string[] = []) =>
  images.map((image) => image.trim()).filter(Boolean);

type ImageEntry = {
  id: string;
  value: string;
};

const toEntries = (images: string[]) =>
  images.map((value, index) => ({ id: `initial-${index}-${value}`, value }));

/**
 * Ordered image editor shared by home, gifts, and event space.
 * Repeated inputs deliberately use one name so FormData.getAll(name) retains
 * the visual order selected by the administrator.
 */
export default function AdminImageList({
  initialImages,
  ...props
}: AdminImageListProps) {
  // A parent commonly recreates this array while the administrator is typing.
  // Key by its normalized contents, rather than synchronizing it with an
  // effect, so local edits are preserved unless the supplied image set truly
  // changes (for example when opening a different product).
  const initialImagesKey = JSON.stringify(cleanImages(initialImages));

  return (
    <AdminImageListEditor
      key={`${props.name}:${initialImagesKey}`}
      {...props}
      initialImages={initialImages}
    />
  );
}

function AdminImageListEditor({
  name,
  initialImages = [],
  title,
  description,
  previewAlt,
  recommendedSize = "1000x1000",
  required = true,
  columns = 1,
}: AdminImageListProps) {
  const [images, setImages] = useState<ImageEntry[]>(() => {
    const normalized = cleanImages(initialImages);
    return normalized.length ? toEntries(normalized) : [{ id: "empty-0", value: "" }];
  });

  const moveImage = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= images.length) return;
    setImages((current) => {
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const removeImage = (index: number) => {
    setImages((current) => {
      const next = current.filter((_, imageIndex) => imageIndex !== index);
      return next.length ? next : [{ id: `empty-${Date.now()}`, value: "" }];
    });
  };

  return (
    <section className="space-y-3">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold text-stone-900">{title}</h2>
        {description ? (
          <p className="text-sm leading-relaxed text-stone-600">{description}</p>
        ) : null}
      </div>
      <div className={`grid min-w-0 gap-4 ${columns === 2 ? "lg:grid-cols-2" : ""}`}>
        {images.map((image, index) => (
          <div
            key={image.id}
            className="relative min-w-0 rounded-[24px] border border-stone-200/70 bg-white/45 p-3"
          >
            <div className="absolute right-2 top-2 z-10 flex items-center gap-1">
              <button
                type="button"
                onClick={() => moveImage(index, -1)}
                disabled={index === 0}
                className="inline-flex h-7 min-w-7 items-center justify-center rounded-full border border-stone-200 bg-white/90 px-1 text-xs text-stone-600 transition hover:border-stone-300 hover:text-stone-800 disabled:cursor-not-allowed disabled:opacity-40"
                aria-label={`Move photo ${index + 1} earlier`}
              >
                ↑
              </button>
              <button
                type="button"
                onClick={() => moveImage(index, 1)}
                disabled={index === images.length - 1}
                className="inline-flex h-7 min-w-7 items-center justify-center rounded-full border border-stone-200 bg-white/90 px-1 text-xs text-stone-600 transition hover:border-stone-300 hover:text-stone-800 disabled:cursor-not-allowed disabled:opacity-40"
                aria-label={`Move photo ${index + 1} later`}
              >
                ↓
              </button>
              <button
                type="button"
                onClick={() => removeImage(index)}
                className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-stone-200 bg-white/90 text-sm text-stone-600 transition hover:border-stone-300 hover:text-stone-800"
                aria-label={`Remove photo ${index + 1}`}
              >
                ×
              </button>
            </div>
            <p className="mb-3 text-xs uppercase tracking-[0.2em] text-stone-500">
              Photo {index + 1}
            </p>
            <AdminImageUpload
              name={name}
              defaultValue={image.value}
              urlLabel="Image URL"
              previewAlt={`${previewAlt} ${index + 1}`}
              recommendedSize={recommendedSize}
              previewClassName="h-24 w-24"
              required={required && index === 0}
              onValueChange={(value) => {
                setImages((current) =>
                  current.map((entry, entryIndex) =>
                    entryIndex === index ? { ...entry, value } : entry
                  )
                );
              }}
            />
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={() =>
          setImages((current) => [
            ...current,
            { id: `new-${Date.now()}-${current.length}`, value: "" },
          ])
        }
        className="inline-flex h-10 w-full items-center justify-center rounded-full border border-stone-300 bg-white/85 px-4 text-[11px] uppercase tracking-[0.22em] text-stone-700 transition hover:border-stone-400"
      >
        Add photo
      </button>
      <p className="text-xs uppercase tracking-[0.2em] text-stone-500">
        Drag-free order: the first six photos are the public gallery.
      </p>
    </section>
  );
}
