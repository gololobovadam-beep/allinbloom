from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException

from app.models.bouquet import Bouquet
from app.models.bouquet_gallery_image import BouquetGalleryImage
from app.models.enums import FlowerType
from app.models.event_tier import EventTier
from app.models.home_gallery_image import HomeGalleryImage

MAX_GALLERY_IMAGES = 50
MAX_URL_LENGTH = 2048
MAX_TIER_DESCRIPTION_LENGTH = 1200
_YOUTUBE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
_IMAGE_SCHEMES = {"https"}


def normalize_image_url(value: object) -> str:
    url = str(value or "").strip()
    if not url:
        raise HTTPException(status_code=422, detail="Image URL is required.")
    if len(url) > MAX_URL_LENGTH:
        raise HTTPException(status_code=422, detail="Image URL is too long.")
    if url.startswith("/") and not url.startswith("//"):
        return url

    parsed = urlparse(url)
    if parsed.scheme.lower() not in _IMAGE_SCHEMES or not parsed.netloc:
        raise HTTPException(
            status_code=422,
            detail="Image URL must be an HTTPS URL or a local absolute path.",
        )
    return url


def normalize_gallery_images(values: Iterable[object]) -> list[str]:
    images: list[str] = []
    for value in values:
        raw = str(value or "").strip()
        if not raw:
            continue
        normalized = normalize_image_url(raw)
        if normalized not in images:
            images.append(normalized)
        if len(images) > MAX_GALLERY_IMAGES:
            raise HTTPException(
                status_code=422,
                detail=f"At most {MAX_GALLERY_IMAGES} gallery images are allowed.",
            )
    return images


def normalize_youtube_url(value: object | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if len(raw) > MAX_URL_LENGTH:
        raise HTTPException(status_code=422, detail="Video URL is too long.")

    parsed = urlparse(raw)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise HTTPException(status_code=422, detail="Video URL must be an HTTPS YouTube URL.")

    host = parsed.netloc.lower().split(":", 1)[0]
    video_id: str | None = None
    if host in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif host in {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtube-nocookie.com",
        "www.youtube-nocookie.com",
    }:
        path_parts = [part for part in parsed.path.split("/") if part]
        if parsed.path == "/watch":
            video_id = (parse_qs(parsed.query).get("v") or [""])[0]
        elif len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live"}:
            video_id = path_parts[1]

    if not video_id or not _YOUTUBE_ID_PATTERN.fullmatch(video_id):
        raise HTTPException(status_code=422, detail="Invalid YouTube video URL.")
    # Store a canonical, safe URL; clients can derive a no-cookie embed from it.
    return f"https://www.youtube.com/watch?v={video_id}"


def legacy_gallery_from_bouquet(bouquet: Bouquet, updates: dict | None = None) -> list[object]:
    data = updates or {}
    return [
        data.get("image", bouquet.image),
        data.get("image_2", bouquet.image_2),
        data.get("image_3", bouquet.image_3),
        data.get("image_4", bouquet.image_4),
        data.get("image_5", bouquet.image_5),
        data.get("image_6", bouquet.image_6),
    ]


def replace_bouquet_gallery_images(bouquet: Bouquet, image_values: Iterable[object]) -> list[str]:
    images = normalize_gallery_images(image_values)
    if not images:
        raise HTTPException(status_code=422, detail="At least one image is required.")

    # Update existing rows in place before adding/removing rows.  Replacing the
    # whole collection can make SQLAlchemy insert a new ``position`` before it
    # deletes the old one, which conflicts with the database uniqueness
    # constraint on (bouquetId, position).
    existing_rows = list(bouquet.gallery_image_rows)
    for position, url in enumerate(images):
        if position < len(existing_rows):
            existing_rows[position].url = url
            existing_rows[position].position = position
        else:
            bouquet.gallery_image_rows.append(
                BouquetGalleryImage(url=url, position=position)
            )
    if len(existing_rows) > len(images):
        del bouquet.gallery_image_rows[len(images) :]

    # Keep the six historical columns synchronized until their later removal.
    legacy_values = images[:6] + [None] * max(0, 6 - len(images))
    bouquet.image = legacy_values[0]
    bouquet.image_2 = legacy_values[1]
    bouquet.image_3 = legacy_values[2]
    bouquet.image_4 = legacy_values[3]
    bouquet.image_5 = legacy_values[4]
    bouquet.image_6 = legacy_values[5]
    return images


def replace_home_gallery_images(store_settings, image_values: Iterable[object]) -> list[str]:
    """Replace homepage images atomically while keeping legacy slots in sync."""

    images = normalize_gallery_images(image_values)
    if not images:
        raise HTTPException(status_code=422, detail="At least one homepage image is required.")

    # See ``replace_bouquet_gallery_images`` for why this updates in place.
    existing_rows = list(store_settings.home_gallery_image_rows)
    for position, url in enumerate(images):
        if position < len(existing_rows):
            existing_rows[position].url = url
            existing_rows[position].position = position
        else:
            store_settings.home_gallery_image_rows.append(
                HomeGalleryImage(url=url, position=position)
            )
    if len(existing_rows) > len(images):
        del store_settings.home_gallery_image_rows[len(images) :]
    legacy_values = images[:6] + [None] * max(0, 6 - len(images))
    store_settings.home_gallery_image_1 = legacy_values[0]
    store_settings.home_gallery_image_2 = legacy_values[1]
    store_settings.home_gallery_image_3 = legacy_values[2]
    store_settings.home_gallery_image_4 = legacy_values[3]
    store_settings.home_gallery_image_5 = legacy_values[4]
    store_settings.home_gallery_image_6 = legacy_values[5]
    return images


def replace_event_tiers(bouquet: Bouquet, tiers: Iterable[object]) -> None:
    normalized_rows: list[tuple[int, str | None, str]] = []
    for raw in tiers:
        if isinstance(raw, dict):
            raw_price = raw.get("price_cents", raw.get("priceCents"))
            raw_title = raw.get("title")
            raw_description = raw.get("description")
        else:
            raw_price = getattr(raw, "price_cents", None)
            raw_title = getattr(raw, "title", None)
            raw_description = getattr(raw, "description", None)
        try:
            price_cents = int(raw_price)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Tier price must be an integer.") from exc
        description = str(raw_description or "").strip()
        if price_cents < 0 or price_cents > 100_000_000:
            raise HTTPException(status_code=422, detail="Tier price is out of range.")
        title = str(raw_title or "").strip() or None
        if title and len(title) > 200:
            raise HTTPException(status_code=422, detail="Tier title is invalid.")
        if not description or len(description) > MAX_TIER_DESCRIPTION_LENGTH:
            raise HTTPException(status_code=422, detail="Tier description is invalid.")
        normalized_rows.append((price_cents, title, description))

    if len(normalized_rows) > 50:
        raise HTTPException(status_code=422, detail="At most 50 event tiers are allowed.")

    # Retain rows by ordinal for the same unique-position safety as galleries.
    existing_rows = list(bouquet.event_tiers)
    for position, (price_cents, title, description) in enumerate(normalized_rows):
        if position < len(existing_rows):
            existing_rows[position].price_cents = price_cents
            existing_rows[position].title = title
            existing_rows[position].description = description
            existing_rows[position].position = position
        else:
            bouquet.event_tiers.append(
                EventTier(
                    price_cents=price_cents,
                    title=title,
                    description=description,
                    position=position,
                )
            )
    if len(existing_rows) > len(normalized_rows):
        del bouquet.event_tiers[len(normalized_rows) :]


def apply_non_flower_defaults(data: dict) -> None:
    """Populate legacy non-null flower columns for a non-flower catalog row."""

    data["flower_type"] = FlowerType.MIXED
    data["style"] = ""
    data["bouquet_type"] = "MONO"
    data["colors"] = ""
    data["is_mixed"] = False
    data["allow_flower_quantity"] = False
    data["default_flower_quantity"] = 1
