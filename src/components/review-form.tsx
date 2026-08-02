"use client";

import { useId, useState } from "react";
import ImageWithFallback from "@/components/image-with-fallback";
import ReviewStars from "@/components/review-stars";
import { clientFetch } from "@/lib/api-client";

type ReviewFormState = {
  name: string;
  email: string;
  text: string;
  rating: number;
  image: string;
};

const REVIEW_TEXT_MAX_LENGTH = 1024;
const REVIEW_IMAGE_MAX_WIDTH = 1200;
const REVIEW_IMAGE_MAX_HEIGHT = 900;

const initialState: ReviewFormState = {
  name: "",
  email: "",
  text: "",
  rating: 5,
  image: "",
};

export default function ReviewForm() {
  const fileInputId = useId();
  const [formState, setFormState] = useState<ReviewFormState>(initialState);
  const [submitStatus, setSubmitStatus] = useState<
    "idle" | "sending" | "sent" | "error"
  >("idle");
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [selectedFileName, setSelectedFileName] = useState("No file chosen");

  const updateField = <T extends keyof ReviewFormState>(
    key: T,
    value: ReviewFormState[T]
  ) => {
    setFormState((current) => ({ ...current, [key]: value }));
  };
  const textLength = formState.text.length;

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      setSelectedFileName("No file chosen");
      return;
    }

    setSelectedFileName(file.name);

    setUploading(true);
    setUploadStatus("Uploading...");

    const payload = new FormData();
    payload.append("file", file);
    payload.append("max_width", String(REVIEW_IMAGE_MAX_WIDTH));
    payload.append("max_height", String(REVIEW_IMAGE_MAX_HEIGHT));
    payload.append("format", "webp");

    try {
      const response = await clientFetch("/api/upload/review", {
        method: "POST",
        body: payload,
      });
      const data = (await response.json().catch(() => null)) as
        | { url?: string; detail?: string }
        | null;

      if (!response.ok) {
        setUploadStatus(data?.detail || "Upload failed.");
      } else if (data?.url) {
        updateField("image", data.url);
        setUploadStatus("Upload complete.");
      } else {
        setUploadStatus("Upload complete, but no URL returned.");
      }
    } catch {
      setUploadStatus("Upload failed.");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setSubmitStatus("sending");
    const response = await clientFetch("/api/reviews", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: formState.name.trim(),
        email: formState.email.trim(),
        text: formState.text.trim().slice(0, REVIEW_TEXT_MAX_LENGTH),
        rating: formState.rating,
        image: formState.image.trim() || null,
      }),
    });

    if (!response.ok) {
      setSubmitStatus("error");
      return;
    }

    setSubmitStatus("sent");
    setFormState(initialState);
    setSelectedFileName("No file chosen");
    setUploadStatus(null);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="glass max-w-full space-y-6 rounded-[30px] border border-white/85 p-5 shadow-[0_20px_45px_rgba(63,40,36,0.14)] sm:space-y-7 sm:p-8"
    >
      <div className="space-y-1">
        <p className="text-xs uppercase tracking-[0.3em] text-stone-500">
          Leave a review
        </p>
        <h3 className="text-2xl font-semibold text-stone-900 sm:text-3xl">
          Tell us about your bouquet experience
        </h3>
      </div>

      <div className="grid gap-5 lg:grid-cols-[0.92fr_1.08fr]">
        <div className="min-w-0 space-y-4">
          <div className="w-full min-w-0 overflow-hidden rounded-[24px] border border-stone-200/80 bg-white aspect-[4/3]">
            <ImageWithFallback
              src={formState.image}
              alt="Review photo preview"
              width={800}
              height={600}
              className="h-full w-full object-cover object-center"
            />
          </div>
          <label
            className="flex min-w-0 flex-col gap-2 text-sm text-stone-700"
            htmlFor={fileInputId}
          >
            Upload photo (optional)
            <span
              className={`flex h-11 w-full min-w-0 items-center justify-between gap-3 rounded-2xl border border-stone-200 bg-white px-4 text-sm text-stone-700 transition ${
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
          {uploadStatus ? (
            <p className="text-xs uppercase tracking-[0.2em] text-stone-500">
              {uploadStatus}
            </p>
          ) : null}
        </div>

        <div className="min-w-0 space-y-4">
          <label className="flex min-w-0 flex-col gap-2 text-sm text-stone-700">
            Name
            <input
              name="name"
              required
              value={formState.name}
              onChange={(event) => updateField("name", event.target.value)}
              className="h-11 w-full min-w-0 rounded-2xl border border-stone-200 bg-white px-4 text-sm text-stone-800 outline-none focus:border-stone-400"
            />
          </label>
          <label className="flex min-w-0 flex-col gap-2 text-sm text-stone-700">
            Email
            <input
              name="email"
              type="email"
              required
              value={formState.email}
              onChange={(event) => updateField("email", event.target.value)}
              className="h-11 w-full min-w-0 rounded-2xl border border-stone-200 bg-white px-4 text-sm text-stone-800 outline-none focus:border-stone-400"
            />
          </label>
          <div className="w-full min-w-0 rounded-2xl border border-stone-200 bg-white px-4 py-3">
            <p className="text-xs uppercase tracking-[0.24em] text-stone-500">
              Your rating
            </p>
            <ReviewStars
              value={formState.rating}
              onChange={(value) => updateField("rating", value)}
              size="lg"
              className="mt-2"
            />
          </div>
          <label className="flex min-w-0 flex-col gap-2 text-sm text-stone-700">
            Review
            <textarea
              name="text"
              required
              rows={6}
              value={formState.text}
              maxLength={REVIEW_TEXT_MAX_LENGTH}
              onChange={(event) =>
                updateField("text", event.target.value.slice(0, REVIEW_TEXT_MAX_LENGTH))
              }
              className="min-h-[9.5rem] w-full min-w-0 rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm text-stone-800 outline-none focus:border-stone-400"
            />
          </label>
          <p className="text-right text-xs uppercase tracking-[0.18em] text-stone-500">
            {textLength} / {REVIEW_TEXT_MAX_LENGTH}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={submitStatus === "sending"}
          className="inline-flex h-11 w-full items-center justify-center rounded-full bg-[color:var(--brand)] px-6 text-xs uppercase tracking-[0.3em] text-white transition hover:bg-[color:var(--brand-dark)] disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
        >
          {submitStatus === "sending" ? "Sending..." : "Submit review"}
        </button>
        {submitStatus === "sent" ? (
          <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">
            Thank you. Your review was sent.
          </p>
        ) : null}
        {submitStatus === "error" ? (
          <p className="text-xs uppercase tracking-[0.2em] text-rose-700">
            Could not send review. Please try again.
          </p>
        ) : null}
      </div>
    </form>
  );
}
