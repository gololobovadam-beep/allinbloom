"use client";

import { useState } from "react";
import ReviewStars from "@/components/review-stars";
import { clientFetch } from "@/lib/api-client";

type ReviewFormState = {
  name: string;
  email: string;
  text: string;
  rating: number;
};

const REVIEW_TEXT_MAX_LENGTH = 1024;

const initialState: ReviewFormState = {
  name: "",
  email: "",
  text: "",
  rating: 5,
};

export default function ReviewForm() {
  const [formState, setFormState] = useState<ReviewFormState>(initialState);
  const [submitStatus, setSubmitStatus] = useState<
    "idle" | "sending" | "sent" | "error"
  >("idle");

  const updateField = <T extends keyof ReviewFormState>(
    key: T,
    value: ReviewFormState[T]
  ) => {
    setFormState((current) => ({ ...current, [key]: value }));
  };
  const textLength = formState.text.length;

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
      }),
    });

    if (!response.ok) {
      setSubmitStatus("error");
      return;
    }

    setSubmitStatus("sent");
    setFormState(initialState);
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
        <p className="rounded-2xl border border-stone-200 bg-white/70 px-4 py-3 text-sm text-stone-600">
          Reviews are published after staff moderation. Photos can be added by our team after approval.
        </p>
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
            Thank you. Your review was sent for moderation.
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
