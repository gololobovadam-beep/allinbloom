"use client";

import { useMemo, useState } from "react";
import Modal from "@/components/modal";

const YOUTUBE_ID = /^[A-Za-z0-9_-]{11}$/;
const YOUTUBE_HOSTS = new Set([
  "youtube.com",
  "www.youtube.com",
  "m.youtube.com",
  "youtube-nocookie.com",
  "www.youtube-nocookie.com",
]);

/**
 * Accept only a known HTTPS YouTube URL and use its ID in a fixed no-cookie
 * embed URL. This keeps the iframe source independent of editable URL input.
 */
export function getYouTubeVideoId(value: string | null | undefined) {
  if (!value) return null;

  try {
    const url = new URL(value);
    if (url.protocol !== "https:") return null;

    const host = url.hostname.toLowerCase();
    let videoId = "";

    if (host === "youtu.be" || host === "www.youtu.be") {
      videoId = url.pathname.split("/").filter(Boolean)[0] || "";
    } else if (YOUTUBE_HOSTS.has(host)) {
      const path = url.pathname.split("/").filter(Boolean);
      if (url.pathname === "/watch") {
        videoId = url.searchParams.get("v") || "";
      } else if (["embed", "shorts", "live"].includes(path[0] || "")) {
        videoId = path[1] || "";
      }
    }

    return YOUTUBE_ID.test(videoId) ? videoId : null;
  } catch {
    return null;
  }
}

type YouTubeVideoModalProps = {
  videoUrl: string | null | undefined;
  title: string;
  label?: string;
  className?: string;
};

export default function YouTubeVideoModal({
  videoUrl,
  title,
  label = "Watch video",
  className = "",
}: YouTubeVideoModalProps) {
  const videoId = useMemo(() => getYouTubeVideoId(videoUrl), [videoUrl]);
  const [open, setOpen] = useState(false);

  if (!videoId) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={`inline-flex min-h-10 items-center justify-center rounded-full border border-[color:var(--brand)]/30 bg-white/80 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-[color:var(--brand)] transition hover:border-[color:var(--brand)]/60 hover:bg-white sm:text-xs sm:tracking-[0.26em] ${className}`}
      >
        {label}
      </button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={title}
        description="Video preview"
        panelClassName="max-w-4xl"
        closeLabel="Close video"
      >
        <div className="overflow-hidden rounded-[20px] border border-stone-200 bg-stone-950 shadow-inner">
          <iframe
            title={title}
            src={`https://www.youtube-nocookie.com/embed/${videoId}?rel=0`}
            className="aspect-video h-auto w-full"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
            referrerPolicy="strict-origin-when-cross-origin"
          />
        </div>
      </Modal>
    </>
  );
}
