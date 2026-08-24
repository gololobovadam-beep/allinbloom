from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
import httpx

from app.api.deps import require_admin
from app.core.config import settings
from app.schemas.upload import UploadResponse

router = APIRouter(prefix="/api/upload", tags=["upload"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_OUTPUT_FORMATS = {"jpg", "png", "webp"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
MAX_MULTIPART_BODY_BYTES = MAX_IMAGE_SIZE_BYTES + 128 * 1024
MAX_IMAGE_DIMENSION = 4096
DEFAULT_IMAGE_DIMENSION = 2048
DEFAULT_IMAGE_FORMAT = "webp"


def _detected_image_content_type(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def _reject_oversized_multipart(request: Request) -> None:
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_MULTIPART_BODY_BYTES:
        raise HTTPException(status_code=413, detail="File is too large")


def _normalized_upload_options(
    *,
    max_width: int | None,
    max_height: int | None,
    fmt: str | None,
) -> dict[str, str]:
    """Constrain the incoming Cloudinary transformation for every upload.

    An incoming transformation is stored as the asset rather than merely
    attached to a delivery URL.  This caps image dimensions and, because the
    asset is transformed, prevents EXIF/location metadata from being delivered.
    """
    width = max_width if max_width is not None else DEFAULT_IMAGE_DIMENSION
    height = max_height if max_height is not None else DEFAULT_IMAGE_DIMENSION
    if not 1 <= width <= MAX_IMAGE_DIMENSION or not 1 <= height <= MAX_IMAGE_DIMENSION:
        raise HTTPException(
            status_code=400,
            detail=f"Image dimensions must be between 1 and {MAX_IMAGE_DIMENSION} pixels.",
        )

    normalized_format = (fmt or DEFAULT_IMAGE_FORMAT).strip().lower()
    if normalized_format == "jpeg":
        normalized_format = "jpg"
    if normalized_format not in ALLOWED_OUTPUT_FORMATS:
        raise HTTPException(status_code=400, detail="Unsupported output image format")

    return {
        "transformation": f"c_limit,w_{width},h_{height},q_auto",
        "format": normalized_format,
    }


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
    data = {
        "upload_preset": settings.cloudinary_upload_preset,
        **_normalized_upload_options(
            max_width=max_width,
            max_height=max_height,
            fmt=fmt,
        ),
    }
    files = {"file": (file.filename, content, file.content_type)}

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, data=data, files=files)

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Upload provider returned an invalid response",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Upload provider returned an invalid response")
    if response.status_code >= 400:
        message = (payload.get("error") or {}).get("message", "Upload failed")
        raise HTTPException(status_code=response.status_code, detail=message)

    raw_url = payload.get("secure_url") or payload.get("url") or ""
    expected_prefix = f"https://res.cloudinary.com/{settings.cloudinary_cloud_name}/image/"
    if not isinstance(raw_url, str) or not raw_url.startswith(expected_prefix):
        raise HTTPException(status_code=502, detail="Upload provider returned an invalid image URL")
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
