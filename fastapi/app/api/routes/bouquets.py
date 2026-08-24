from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, get_optional_user, require_admin
from app.models.bouquet import Bouquet
from app.models.catalog_category import CatalogCategory
from app.models.enums import BouquetType, CatalogType, FlowerType, Role
from app.schemas.bouquet import BouquetCreate, BouquetOut, BouquetUpdate
from app.services.catalog_products import (
    apply_non_flower_defaults,
    legacy_gallery_from_bouquet,
    normalize_gallery_images,
    normalize_youtube_url,
    replace_bouquet_gallery_images,
    replace_event_tiers,
)
from app.services.colors import normalize_color_csv

router = APIRouter(prefix="/api/bouquets", tags=["bouquets"])

FLOWER_TYPE_VALUES = {member.value for member in FlowerType}
FLOWER_QUANTITY_MIN = 1
FLOWER_QUANTITY_MAX = 1001
FLOWER_QUANTITY_ELIGIBLE_TYPES = {BouquetType.MONO, BouquetType.SEASON}
LEGACY_IMAGE_KEYS = ("image", "image_2", "image_3", "image_4", "image_5", "image_6")


def _with_catalog_relations(statement):
    return statement.options(
        selectinload(Bouquet.gallery_image_rows),
        selectinload(Bouquet.event_tiers),
        selectinload(Bouquet.category),
    )


def _is_admin(user) -> bool:
    return bool(user and user.role == Role.ADMIN)


def _require_admin_for_inactive(user) -> None:
    if _is_admin(user):
        return
    # Keep the historic query shape used by the frontend while preventing an
    # unauthenticated caller from enumerating drafts and hidden inventory.
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")


def _normalize_flower_types_csv(value: str | None, fallback: FlowerType | str | None) -> str:
    parts = str(value or "").split(",")
    values: list[str] = []
    for part in parts:
        token = part.strip().upper()
        if token in FLOWER_TYPE_VALUES and token != "MIXED" and token not in values:
            values.append(token)
        if len(values) >= 3:
            break

    if not values:
        fallback_token = str(getattr(fallback, "value", fallback) or "").strip().upper()
        if fallback_token in FLOWER_TYPE_VALUES and fallback_token != "MIXED":
            values.append(fallback_token)

    if not values:
        values.append(FlowerType.ROSE.value)
    return ", ".join(values)


def _resolve_bouquet_type(data: dict, existing: Bouquet | None = None) -> BouquetType:
    raw = data.get("bouquet_type")
    if raw:
        return BouquetType(str(getattr(raw, "value", raw)).upper())

    raw_is_mixed = data.get("is_mixed")
    if raw_is_mixed is not None:
        return BouquetType.MIXED if bool(raw_is_mixed) else BouquetType.MONO

    if existing and existing.bouquet_type:
        try:
            return BouquetType(str(getattr(existing.bouquet_type, "value", existing.bouquet_type)).upper())
        except ValueError:
            pass
    if existing and existing.is_mixed:
        return BouquetType.MIXED
    return BouquetType.MONO


def _normalize_default_flower_quantity(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return FLOWER_QUANTITY_MIN
    return max(FLOWER_QUANTITY_MIN, min(FLOWER_QUANTITY_MAX, parsed))


def _validate_category(
    db: Session,
    *,
    category_id: str | None,
    catalog_type: CatalogType,
) -> str | None:
    normalized_id = str(category_id or "").strip() or None
    if not normalized_id:
        return None
    category = db.get(CatalogCategory, normalized_id)
    if not category:
        raise HTTPException(status_code=422, detail="Invalid category for this catalog.")
    category_catalog_type = str(
        getattr(category.catalog_type, "value", category.catalog_type) or ""
    ).upper()
    if category_catalog_type != catalog_type.value:
        raise HTTPException(status_code=422, detail="Invalid category for this catalog.")
    return normalized_id


def _load_bouquet(
    db: Session,
    bouquet_id: str,
    catalog_type: CatalogType,
) -> Bouquet | None:
    return (
        db.execute(
            _with_catalog_relations(
                select(Bouquet).where(
                    Bouquet.id == bouquet_id,
                    Bouquet.catalog_type == catalog_type.value,
                )
            )
        )
        .scalars()
        .first()
    )


def _prepare_flower_data(data: dict, existing: Bouquet | None = None) -> None:
    if "colors" in data:
        data["colors"] = normalize_color_csv(data.get("colors"))
    if "style" in data or "flower_type" in data or existing is None:
        data["style"] = _normalize_flower_types_csv(
            data.get("style"),
            data.get("flower_type") or (existing.flower_type if existing else None),
        )
        data["flower_type"] = FlowerType(data["style"].split(",")[0].strip())

    bouquet_type = _resolve_bouquet_type(data, existing)
    data["bouquet_type"] = bouquet_type.value
    data["is_mixed"] = bouquet_type == BouquetType.MIXED
    allow_flower_quantity = bool(
        data.get(
            "allow_flower_quantity",
            existing.allow_flower_quantity if existing else True,
        )
    )
    data["allow_flower_quantity"] = allow_flower_quantity
    default_flower_quantity = _normalize_default_flower_quantity(
        data.get(
            "default_flower_quantity",
            existing.default_flower_quantity if existing else FLOWER_QUANTITY_MIN,
        )
    )
    if not allow_flower_quantity or bouquet_type not in FLOWER_QUANTITY_ELIGIBLE_TYPES:
        default_flower_quantity = FLOWER_QUANTITY_MIN
    data["default_flower_quantity"] = default_flower_quantity


def _create_gallery_values(data: dict, incoming_gallery: list[str] | None) -> list[object]:
    if incoming_gallery is not None:
        return incoming_gallery
    return [data.get(key) for key in LEGACY_IMAGE_KEYS]


@router.get("", response_model=list[BouquetOut])
def list_bouquets(
    include_inactive: bool = Query(default=False),
    catalog_type: CatalogType = Query(default=CatalogType.FLOWERS, alias="catalogType"),
    user=Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    if include_inactive:
        _require_admin_for_inactive(user)

    stmt = _with_catalog_relations(
        select(Bouquet).where(Bouquet.catalog_type == catalog_type.value)
    )
    if not include_inactive:
        stmt = stmt.where(Bouquet.is_active.is_(True))
    stmt = stmt.order_by(Bouquet.created_at.desc(), Bouquet.id.desc())
    return db.execute(stmt).scalars().all()


@router.get("/{bouquet_id}", response_model=BouquetOut)
def get_bouquet(
    bouquet_id: str,
    catalog_type: CatalogType = Query(default=CatalogType.FLOWERS, alias="catalogType"),
    user=Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    bouquet = _load_bouquet(db, bouquet_id, catalog_type)
    if not bouquet or (not bouquet.is_active and not _is_admin(user)):
        # Return the same response for a missing ID and a hidden record to
        # avoid revealing unpublished inventory.
        raise HTTPException(status_code=404, detail="Not found")
    return bouquet


@router.post("", response_model=BouquetOut)
def create_bouquet(
    payload: BouquetCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    data = payload.model_dump(exclude={"gallery_images", "tiers"})
    catalog_type = payload.catalog_type
    data["catalog_type"] = catalog_type.value
    data["video_orientation"] = data.get("video_orientation") or "HORIZONTAL"
    incoming_gallery = payload.gallery_images
    incoming_tiers = payload.tiers
    data["category_id"] = _validate_category(
        db, category_id=data.get("category_id"), catalog_type=catalog_type
    )
    data["video_url"] = normalize_youtube_url(data.get("video_url"))
    if data["video_url"] and catalog_type not in {
        CatalogType.GIFTS,
        CatalogType.EVENT_SPACE,
    }:
        raise HTTPException(status_code=422, detail="Video is not supported for this catalog.")

    if catalog_type == CatalogType.FLOWERS:
        _prepare_flower_data(data)
    else:
        apply_non_flower_defaults(data)
        # Event Space is never purchasable, so retain a neutral legacy price
        # for the shared product table whether or not it has optional tiers.
        data["price_cents"] = (
            0
            if catalog_type == CatalogType.EVENT_SPACE
            else int(data.get("price_cents") or 0)
        )

    gallery_values = _create_gallery_values(data, incoming_gallery)
    normalized_gallery = normalize_gallery_images(gallery_values)
    if not normalized_gallery:
        raise HTTPException(status_code=422, detail="At least one image is required.")
    data["image"] = normalized_gallery[0]

    bouquet = Bouquet(**data)
    replace_bouquet_gallery_images(bouquet, normalized_gallery)
    if catalog_type == CatalogType.EVENT_SPACE:
        replace_event_tiers(bouquet, incoming_tiers or [])
    db.add(bouquet)
    db.commit()
    db.refresh(bouquet)
    return bouquet


@router.patch("/{bouquet_id}", response_model=BouquetOut)
def update_bouquet(
    bouquet_id: str,
    payload: BouquetUpdate,
    catalog_type: CatalogType = Query(default=CatalogType.FLOWERS, alias="catalogType"),
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    bouquet = _load_bouquet(db, bouquet_id, catalog_type)
    if not bouquet:
        raise HTTPException(status_code=404, detail="Not found")
    data = payload.model_dump(exclude_unset=True, exclude={"gallery_images", "tiers"})
    incoming_gallery = payload.gallery_images if "gallery_images" in payload.model_fields_set else None
    incoming_tiers = payload.tiers if "tiers" in payload.model_fields_set else None
    requested_catalog_type = data.pop("catalog_type", None)
    if requested_catalog_type and requested_catalog_type != catalog_type:
        raise HTTPException(status_code=422, detail="Catalog type cannot be changed.")

    if "category_id" in data:
        data["category_id"] = _validate_category(
            db, category_id=data.get("category_id"), catalog_type=catalog_type
        )
    if "video_url" in data:
        data["video_url"] = normalize_youtube_url(data.get("video_url"))
        if data["video_url"] and catalog_type not in {
            CatalogType.GIFTS,
            CatalogType.EVENT_SPACE,
        }:
            raise HTTPException(status_code=422, detail="Video is not supported for this catalog.")

    has_legacy_gallery_update = any(key in data for key in LEGACY_IMAGE_KEYS)
    if catalog_type == CatalogType.FLOWERS:
        _prepare_flower_data(data, bouquet)
    else:
        apply_non_flower_defaults(data)

    if catalog_type == CatalogType.EVENT_SPACE:
        submitted_price = data.get("price_cents")
        if submitted_price not in {None, 0}:
            raise HTTPException(
                status_code=422,
                detail="Event Space pricing must be configured through tiers.",
            )
        data["price_cents"] = 0
    elif "price_cents" in data and (data["price_cents"] is None or data["price_cents"] <= 0):
        raise HTTPException(
            status_code=422,
            detail="Price must be greater than 0 for purchasable products.",
        )

    # The shared frontend form serializes an empty ``tiers`` array for products
    # that do not support tiers. Treat that as an omitted field while rejecting
    # attempts to attach actual tiers outside Event Space.
    if incoming_tiers and catalog_type != CatalogType.EVENT_SPACE:
        raise HTTPException(status_code=422, detail="Tiers are only available for Event Space.")

    for key, value in data.items():
        setattr(bouquet, key, value)

    if incoming_gallery is not None:
        replace_bouquet_gallery_images(bouquet, incoming_gallery)
    elif has_legacy_gallery_update:
        replace_bouquet_gallery_images(bouquet, legacy_gallery_from_bouquet(bouquet, data))
    if catalog_type == CatalogType.EVENT_SPACE and incoming_tiers is not None:
        replace_event_tiers(bouquet, incoming_tiers)

    db.commit()
    db.refresh(bouquet)
    return bouquet


@router.delete("/{bouquet_id}")
def delete_bouquet(
    bouquet_id: str,
    catalog_type: CatalogType = Query(default=CatalogType.FLOWERS, alias="catalogType"),
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    bouquet = _load_bouquet(db, bouquet_id, catalog_type)
    if not bouquet:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(bouquet)
    db.commit()
    return {"ok": True}
