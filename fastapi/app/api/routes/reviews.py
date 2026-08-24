from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.core.config import settings
from app.core.critical_logging import log_critical_event
from app.core.rate_limit import SlidingWindowRateLimiter, enforce_rate_limit
from app.models.review import Review
from app.schemas.review import (
    ReviewAdminOut,
    ReviewCountOut,
    ReviewCreateAdmin,
    ReviewCreatePublic,
    ReviewDeleteOut,
    ReviewPublicOut,
    ReviewToggleActiveOut,
    ReviewToggleReadOut,
    ReviewUpdateAdmin,
)

router = APIRouter(prefix="/api", tags=["reviews"])

PUBLIC_RATE_WINDOW = timedelta(minutes=30)
PUBLIC_RATE_LIMIT = 8
NAME_MAX_LENGTH = 80
EMAIL_MAX_LENGTH = 254
TEXT_MAX_LENGTH = 1024
IMAGE_URL_MAX_LENGTH = 1200
ADMIN_TIMEZONE = "America/Chicago"

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
public_review_limiter = SlidingWindowRateLimiter(
    limit=PUBLIC_RATE_LIMIT,
    window_seconds=int(PUBLIC_RATE_WINDOW.total_seconds()),
)


def _normalize_name(value: str | None) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Name is required.")
    if len(normalized) > NAME_MAX_LENGTH:
        raise HTTPException(status_code=400, detail="Name is too long.")
    return normalized


def _normalize_email(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="Email is required.")
    if len(normalized) > EMAIL_MAX_LENGTH:
        raise HTTPException(status_code=400, detail="Email is too long.")
    if not EMAIL_PATTERN.match(normalized):
        raise HTTPException(status_code=400, detail="Invalid email format.")
    return normalized


def _normalize_text(value: str | None) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Review text is required.")
    if len(normalized) > TEXT_MAX_LENGTH:
        raise HTTPException(status_code=400, detail="Review text is too long.")
    return normalized


def _is_trusted_review_image_url(value: str) -> bool:
    """Allow only same-origin assets or this deployment's Cloudinary delivery URLs.

    Review images are rendered directly in every visitor's browser.  Accepting
    arbitrary remote URLs would let a public submitter turn the review gallery
    into a tracking or internal-network request surface.
    """
    if value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return True

    cloud_name = (settings.cloudinary_cloud_name or "").strip()
    if not cloud_name:
        return False

    parsed = urlsplit(value)
    expected_prefix = f"/{cloud_name}/image/"
    return (
        parsed.scheme == "https"
        and parsed.hostname == "res.cloudinary.com"
        and parsed.port in {None, 443}
        and not parsed.username
        and not parsed.password
        and parsed.path.startswith(expected_prefix)
    )


def _normalize_image(value: str | None) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    if len(normalized) > IMAGE_URL_MAX_LENGTH:
        raise HTTPException(status_code=400, detail="Image URL is too long.")
    if not _is_trusted_review_image_url(normalized):
        raise HTTPException(
            status_code=400,
            detail="Review images must be an approved Cloudinary or local image URL.",
        )
    return normalized


def _public_review_out(review: Review) -> ReviewPublicOut:
    """Never expose legacy arbitrary remote URLs to public visitors."""
    output = ReviewPublicOut.model_validate(review)
    if output.image and not _is_trusted_review_image_url(output.image):
        return output.model_copy(update={"image": None})
    return output


def _normalize_rating(value: int | None) -> int:
    rating = int(value or 0)
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5.")
    return rating


def _normalize_created_at(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(ADMIN_TIMEZONE))
    return value.astimezone(timezone.utc)


@router.get("/reviews", response_model=list[ReviewPublicOut])
def list_reviews(db: Session = Depends(get_db)):
    reviews = (
        db.execute(
            select(Review)
            .where(Review.is_active.is_(True))
            .order_by(Review.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_public_review_out(review) for review in reviews]


@router.post(
    "/reviews",
    response_model=ReviewPublicOut,
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    payload: ReviewCreatePublic,
    request: Request,
    db: Session = Depends(get_db),
):
    enforce_rate_limit(
        request,
        public_review_limiter,
        detail="Too many requests. Please try again later.",
    )
    # Public submissions are moderated before publication.  Images are added
    # only by staff after moderation through the authenticated upload route.
    if (payload.image or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Photos can be added by staff after review moderation.",
        )

    review = Review(
        name=_normalize_name(payload.name),
        email=_normalize_email(payload.email),
        rating=_normalize_rating(payload.rating),
        text=_normalize_text(payload.text),
        image=None,
        is_active=False,
        is_read=False,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    log_critical_event(
        domain="messaging",
        event="review_submitted_for_moderation",
        message="Public review submitted and queued for moderation.",
        request=request,
        context={"review_id": review.id, "rating": review.rating},
        level=logging.INFO,
    )
    return _public_review_out(review)


@router.get("/admin/reviews", response_model=list[ReviewAdminOut])
def list_admin_reviews(
    include_hidden: bool = Query(default=True),
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    query = select(Review)
    if not include_hidden:
        query = query.where(Review.is_active.is_(True))
    query = query.order_by(Review.created_at.desc())
    return db.execute(query).scalars().all()


@router.get("/admin/reviews/new-count", response_model=ReviewCountOut)
def get_new_reviews_count(
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    count = db.execute(
        select(func.count()).select_from(Review).where(Review.is_read.is_(False))
    ).scalar_one()
    return ReviewCountOut(count=count)


@router.get("/admin/reviews/{review_id}", response_model=ReviewAdminOut)
def get_admin_review(
    review_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    review = db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Not found")
    return review


@router.post(
    "/admin/reviews",
    response_model=ReviewAdminOut,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_review(
    payload: ReviewCreateAdmin,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    created_at = _normalize_created_at(payload.created_at)
    review_data = dict(
        name=_normalize_name(payload.name),
        email=_normalize_email(payload.email),
        rating=_normalize_rating(payload.rating),
        text=_normalize_text(payload.text),
        image=_normalize_image(payload.image),
        is_active=bool(payload.is_active),
        is_read=bool(payload.is_read),
    )
    if created_at is not None:
        review_data["created_at"] = created_at

    review = Review(**review_data)
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.patch("/admin/reviews/{review_id}", response_model=ReviewAdminOut)
def update_admin_review(
    review_id: str,
    payload: ReviewUpdateAdmin,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    review = db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key == "name":
            review.name = _normalize_name(value)
        elif key == "email":
            review.email = _normalize_email(value)
        elif key == "rating":
            review.rating = _normalize_rating(value)
        elif key == "text":
            review.text = _normalize_text(value)
        elif key == "image":
            review.image = _normalize_image(value)
        elif key == "created_at":
            normalized_created_at = _normalize_created_at(value)
            if normalized_created_at is not None:
                review.created_at = normalized_created_at
        elif key == "is_active":
            review.is_active = bool(value)
        elif key == "is_read":
            review.is_read = bool(value)

    db.commit()
    db.refresh(review)
    return review


@router.patch("/admin/reviews/{review_id}/toggle-read", response_model=ReviewToggleReadOut)
def toggle_review_read(
    review_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    review = db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Not found")
    review.is_read = not bool(review.is_read)
    db.commit()
    db.refresh(review)
    return ReviewToggleReadOut(is_read=bool(review.is_read))


@router.patch(
    "/admin/reviews/{review_id}/toggle-active",
    response_model=ReviewToggleActiveOut,
)
def toggle_review_active(
    review_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    review = db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Not found")
    review.is_active = not bool(review.is_active)
    db.commit()
    db.refresh(review)
    return ReviewToggleActiveOut(is_active=bool(review.is_active))


@router.delete("/admin/reviews/{review_id}", response_model=ReviewDeleteOut)
def delete_admin_review(
    review_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    review = db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(review)
    db.commit()
    return ReviewDeleteOut(deleted=True)
