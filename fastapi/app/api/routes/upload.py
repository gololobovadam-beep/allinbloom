from __future__ import annotations

from datetime import datetime, timedelta
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
import httpx

from app.api.deps import require_admin
from app.core.config import settings
from app.core.critical_logging import log_critical_event
from app.schemas.upload import UploadResponse

router = APIRouter(prefix="/api/upload", tags=["upload"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
MAX_MULTIPART_BODY_BYTES = MAX_IMAGE_SIZE_BYTES + 128 * 1024
REVIEW_UPLOAD_WINDOW = timedelta(minutes=30)
REVIEW_UPLOAD_LIMIT = 20
review_upload_rate_limit: dict[str, dict[str, object]] = {}


def _get_client_key(request: Request) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
        real_ip = (request.headers.get("x-real-ip") or "").strip()
        if real_ip:
            return real_ip
    return request.client.host if request.client and request.client.host else "unknown"


def _allow_review_upload(key: str) -> bool:
    now = datetime.utcnow()
    entry = review_upload_rate_limit.get(key)
    if not entry or entry["reset_at"] <= now:
        review_upload_rate_limit[key] = {"count": 1, "reset_at": now + REVIEW_UPLOAD_WINDOW}
        return True
    if entry["count"] >= REVIEW_UPLOAD_LIMIT:
        return False
    entry["count"] += 1
    return True


def _detected_image_content_type(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def _reject_oversized_multipart(request: Request) -> None:
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_MULTIPART_BODY_BYTES:
        raise HTTPException(status_code=413, detail="File is too large")


async def _read_and_validate_file(file: UploadFile) -> bytes:
    content_type = (file.content_type or "").lower().strip()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    # Read only one byte beyond the limit.  Do not let a spoofed multipart
    # request allocate an unbounded bytes object before validating it.
    content = await file.read(MAX_IMAGE_SIZE_BYTES + 1)
    if len(content) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File is too large")
    detected_content_type = _detected_image_content_type(content)
    if detected_content_type != content_type:
        raise HTTPException(status_code=400, detail="File contents do not match its image type")

    return content


async def _upload_to_cloudinary(
    file: UploadFile,
    content: bytes,
    *,
    max_width: int | None = None,
    max_height: int | None = None,
    fmt: str | None = None,
) -> UploadResponse:
    if not settings.cloudinary_cloud_name or not settings.cloudinary_upload_preset:
        raise HTTPException(status_code=500, detail="Cloudinary not configured")

    url = f"https://api.cloudinary.com/v1_1/{settings.cloudinary_cloud_name}/image/upload"
    data = {"upload_preset": settings.cloudinary_upload_preset}
    files = {"file": (file.filename, content, file.content_type)}

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, data=data, files=files)

    payload = response.json()
    if response.status_code >= 400:
        message = (payload.get("error") or {}).get("message", "Upload failed")
        raise HTTPException(status_code=response.status_code, detail=message)

    raw_url = payload.get("secure_url") or payload.get("url") or ""
    return UploadResponse(
        url=raw_url,
        public_id=payload.get("public_id"),
    )


@router.post("", response_model=UploadResponse)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    max_width: int | None = Form(None),
    max_height: int | None = Form(None),
    format: str | None = Form(None),
    _admin=Depends(require_admin),
):
    _reject_oversized_multipart(request)
    content = await _read_and_validate_file(file)
    return await _upload_to_cloudinary(
        file, content, max_width=max_width, max_height=max_height, fmt=format
    )


@router.post("/review", response_model=UploadResponse)
async def upload_review_image(
    request: Request,
    file: UploadFile = File(...),
    max_width: int | None = Form(None),
    max_height: int | None = Form(None),
    format: str | None = Form(None),
):
    _reject_oversized_multipart(request)
    key = _get_client_key(request)
    if not _allow_review_upload(key):
        log_critical_event(
            domain="personal_data",
            event="review_image_upload_rate_limited",
            message="Review image upload blocked by rate limit.",
            request=request,
            level=logging.WARNING,
        )
        raise HTTPException(
            status_code=429,
            detail="Too many uploads. Please try again later.",
        )

    content = await _read_and_validate_file(file)
    return await _upload_to_cloudinary(
        file,
        content,
        max_width=max_width,
        max_height=max_height,
        fmt=format,
    )
