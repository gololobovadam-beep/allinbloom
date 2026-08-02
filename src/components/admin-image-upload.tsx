"use client";

import { useEffect, useId, useState } from "react";
import ImageWithFallback from "@/components/image-with-fallback";
import { clientFetch } from "@/lib/api-client";

type AdminImageUploadProps = {
  name?: string;
  urlLabel?: string;
  previewAlt?: string;
  defaultValue: string;
  recommendedSize?: string;
  previewClassName?: string;
  isInvalid?: boolean;
  required?: boolean;
  onValueChange?: (value: string) => void;
};

const parseRecommendedSize = (value?: string) => {
  if (!value) return null;
  const match = value.match(/(\d+)\s*x\s*(\d+)/i);
  if (!match) return null;
  const width = Number.parseInt(match[1], 10);
  const height = Number.parseInt(match[2], 10);
  if (!Number.isFinite(width) || !Number.isFinite(height)) return null;
  return { width, height };
};

export default function AdminImageUpload({
  name = "image",
  urlLabel = "Image URL",
  previewAlt = "Image preview",
  defaultValue,
  recommendedSize = "600x800",
  previewClassName = "h-32 w-32",
  isInvalid = false,
  required = true,
  onValueChange,
}: AdminImageUploadProps) {
  const fileInputId = useId();
  const [imageUrl, setImageUrl] = useState(defaultValue);
  const [status, setStatus] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [selectedFileName, setSelectedFileName] = useState("No file chosen");

  const recommendedTarget = parseRecommendedSize(recommendedSize);

  useEffect(() => {
    setImageUrl(defaultValue);
  }, [defaultValue]);

  const updateImageUrl = (value: string) => {
    setImageUrl(value);
    onValueChange?.(value);
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      setSelectedFileName("No file chosen");
      return;
    }

    setSelectedFileName(file.name);

    setUploading(true);
    setStatus("Uploading...");

    const formData = new FormData();
    formData.append("file", file);
    if (recommendedTarget) {
      formData.append("max_width", String(recommendedTarget.width));
      formData.append("max_height", String(recommendedTarget.height));
      formData.append("format", "webp");
    }

    try {
      const response = await clientFetch("/api/upload", {
        method: "POST",
        body: formData,
      }, true);
      const data = await response.json();

      if (!response.ok) {
        setStatus(data?.detail || data?.error?.message || "Upload failed.");
      } else {
        const url = data.url;
        if (url) {
          updateImageUrl(url);
          setStatus("Upload complete.");
        } else {
          setStatus("Upload complete, but no URL returned.");
        }
      }
    } catch (error) {
      console.error(error);
      setStatus("Upload failed.");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  return (
    <div className="min-w-0 space-y-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div
          className={`${previewClassName} overflow-hidden rounded-[22px] border border-white/80 bg-white`}
        >
          <ImageWithFallback
            src={imageUrl}
            alt={previewAlt}
            width={160}
            height={160}
            className="h-full w-full object-cover"
          />
        </div>
        <div className="min-w-0 space-y-2 text-xs text-stone-600">
          <p>Recommended size: {recommendedSize}.</p>
          <p>Uploads go to Cloudinary and save the URL.</p>
        </div>
      </div>
      <label className="flex flex-col gap-2 text-sm text-stone-700">
        {urlLabel}
        <input
          name={name}
          value={imageUrl}
          onChange={(event) => updateImageUrl(event.target.value)}
          required={required}
          className={`h-11 w-full min-w-0 rounded-2xl bg-white/80 px-4 py-0 text-sm text-stone-800 outline-none ${
            isInvalid
              ? "border border-rose-300 focus:border-rose-500"
              : "border border-stone-200 focus:border-stone-400"
          }`}
        />
      </label>
      <label className="flex flex-col gap-2 text-sm text-stone-700" htmlFor={fileInputId}>
        Upload image
        <span
          className={`flex h-11 w-full min-w-0 items-center justify-between gap-3 rounded-2xl border border-stone-200 bg-white/80 px-4 text-sm text-stone-700 outline-none transition focus-within:border-stone-400 ${
            uploading ? "cursor-not-allowed opacity-70" : "cursor-pointer"
          }`}
        >
          <span className="min-w-0 truncate">{selectedFileName}</span>
          <span className="inline-flex h-7 shrink-0 items-center rounded-full border border-stone-300 bg-white px-3 text-[10px] uppercase tracking-[0.2em] text-stone-600">
            Browse
          </span>
        </span>
        <input
          id={fileInputId}
          type="file"
          accept="image/*"
          onChange={handleFileChange}
          disabled={uploading}
          className="sr-only"
        />
      </label>
      {status ? (
        <p className="text-xs uppercase tracking-[0.24em] text-stone-500">
          {status}
        </p>
      ) : null}
    </div>
  );
}
