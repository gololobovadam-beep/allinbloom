"use client";

import { useMemo } from "react";
import GalleryImageLightbox from "@/components/gallery-image-lightbox";

type MosaicGalleryProps = {
  images: string[];
  alt: string;
  visibleLimit?: number;
  className?: string;
};

const normalizeImages = (images: string[]) =>
  images
    .map((image) => image.trim())
    .filter(Boolean)
    .filter((image, index, all) => all.indexOf(image) === index);

/**
 * The public composition intentionally exposes a maximum of six images. This
 * keeps the admin order meaningful while allowing an unlimited stored gallery.
 */
export default function MosaicGallery({
  images,
  alt,
  visibleLimit = 6,
  className = "",
}: MosaicGalleryProps) {
  const visibleImages = useMemo(
    () => normalizeImages(images).slice(0, Math.max(1, visibleLimit)),
    [images, visibleLimit]
  );
  const lightboxItems = useMemo(
    () =>
      visibleImages.map((src, index) => ({
        src,
        alt: `${alt} ${index + 1}`,
        lightboxWidth: 1600,
        lightboxHeight: 1600,
      })),
    [alt, visibleImages]
  );

  if (!visibleImages.length) return null;

  const mainImage = visibleImages[0];
  const thumbnails = visibleImages.slice(1);

  return (
    <div className={`min-w-0 space-y-2.5 ${className}`}>
      <div className="glass aspect-[5/4] overflow-hidden rounded-[28px] border border-white/80">
        <GalleryImageLightbox
          src={mainImage}
          alt={alt}
          className="block h-full w-full"
          imageClassName="h-full w-full object-cover"
          previewWidth={760}
          previewHeight={600}
          items={lightboxItems}
          startIndex={0}
        />
      </div>
      {thumbnails.length ? (
        <div className="grid grid-cols-5 gap-2 sm:grid-cols-5">
          {thumbnails.map((src, index) => (
            <div
              key={`${src}-${index}`}
              className="glass aspect-square min-w-0 overflow-hidden rounded-[18px] border border-white/80"
            >
              <GalleryImageLightbox
                src={src}
                alt={alt}
                className="block h-full w-full"
                imageClassName="h-full w-full object-cover"
                previewWidth={180}
                previewHeight={180}
                items={lightboxItems}
                startIndex={index + 1}
              />
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
