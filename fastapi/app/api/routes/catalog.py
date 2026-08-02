from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db
from app.models.bouquet import Bouquet
# Import relation models so this router can be imported in isolation (for
# example in focused tests) before SQLAlchemy resolves Bouquet's string-based
# relationship targets.
from app.models.bouquet_gallery_image import BouquetGalleryImage  # noqa: F401
from app.models.catalog_category import CatalogCategory  # noqa: F401
from app.models.enums import BouquetType, CatalogType, FlowerType
from app.models.event_tier import EventTier  # noqa: F401
from app.schemas.catalog import CatalogResponse
from app.schemas.bouquet import BouquetOut
from app.services.colors import color_filter_candidates
from app.services.pricing import get_bouquet_pricing
from app.services.settings import get_store_settings

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def _normalize_enum(value: str | None, enum_cls):
    if not value:
        return None
    upper = value.upper()
    try:
        return enum_cls(upper)
    except Exception:
        return None


def _parse_flower_filters(value: str | None) -> list[FlowerType]:
    if not value:
        return []

    parsed: list[FlowerType] = []
    for raw in value.split(","):
        enum_value = _normalize_enum(raw.strip(), FlowerType)
        if not enum_value or enum_value in parsed or enum_value == FlowerType.MIXED:
            continue
        parsed.append(enum_value)
    return parsed


def _resolve_bouquet_type_filter(
    bouquet_type: str | None,
    mixed: str | None,
    style: str | None,
) -> str | None:
    primary = (bouquet_type or "").strip().lower()
    legacy_mixed = (mixed or "").strip().lower()
    legacy_style = (style or "").strip().lower()

    if primary in {"mono", "mixed", "season"}:
        return primary
    if legacy_mixed in {"mono", "mixed"}:
        return legacy_mixed
    if legacy_style == "season":
        return "season"
    return None


def _normalize_sort(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"name_asc", "name_desc", "price_asc", "price_desc"}:
        return normalized
    return "created_desc"


@router.get("", response_model=CatalogResponse)
def list_catalog(
    catalog_type: CatalogType = Query(default=CatalogType.FLOWERS, alias="catalogType"),
    flower: str | None = None,
    color: str | None = None,
    bouquet_type: str | None = Query(default=None, alias="bouquetType"),
    style: str | None = None,
    mixed: str | None = None,
    min: float | None = Query(default=None, alias="min"),
    max: float | None = Query(default=None, alias="max"),
    sort: str | None = None,
    filter: str | None = None,
    cursor: str | None = None,
    take: int = Query(default=12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    filters = [
        Bouquet.is_active.is_(True),
        Bouquet.catalog_type == catalog_type.value,
    ]
    if filter == "featured":
        filters.append(Bouquet.is_featured.is_(True))

    selected_flowers = _parse_flower_filters(flower) if catalog_type == CatalogType.FLOWERS else []
    if selected_flowers:
        flower_filters = []
        for flower_enum in selected_flowers:
            token = flower_enum.value.lower()
            flower_filters.append(Bouquet.flower_type == flower_enum)
            flower_filters.append(func.lower(Bouquet.style).contains(token))
        filters.append(or_(*flower_filters))

    normalized_bouquet_type = (
        _resolve_bouquet_type_filter(bouquet_type, mixed, style)
        if catalog_type == CatalogType.FLOWERS
        else None
    )
    if normalized_bouquet_type == "mono":
        filters.append(
            or_(
                Bouquet.bouquet_type == BouquetType.MONO.value,
                and_(
                    Bouquet.bouquet_type.is_(None),
                    Bouquet.is_mixed.is_(False),
                    func.lower(Bouquet.style) != "season",
                ),
            )
        )
    if normalized_bouquet_type == "mixed":
        filters.append(
            or_(
                Bouquet.bouquet_type == BouquetType.MIXED.value,
                and_(Bouquet.bouquet_type.is_(None), Bouquet.is_mixed.is_(True)),
            )
        )
    if normalized_bouquet_type == "season":
        filters.append(
            or_(
                Bouquet.bouquet_type == BouquetType.SEASON.value,
                and_(
                    Bouquet.bouquet_type.is_(None),
                    func.lower(Bouquet.style) == "season",
                ),
            )
        )

    if min is not None or max is not None:
        min_cents = int(min * 100) if min is not None else None
        max_cents = int(max * 100) if max is not None else None
        if min_cents is not None:
            filters.append(Bouquet.price_cents >= min_cents)
        if max_cents is not None:
            filters.append(Bouquet.price_cents <= max_cents)

    if color and catalog_type == CatalogType.FLOWERS:
        candidates = color_filter_candidates(color)
        if candidates:
            filters.append(
                or_(*[func.lower(Bouquet.colors).contains(candidate) for candidate in candidates])
            )

    base_query = (
        select(Bouquet)
        .options(
            selectinload(Bouquet.gallery_image_rows),
            selectinload(Bouquet.event_tiers),
            selectinload(Bouquet.category),
        )
        .where(and_(*filters))
    )
    normalized_sort = _normalize_sort(sort)
    name_sort_expr = func.lower(func.coalesce(Bouquet.name, ""))

    if cursor:
        cursor_row = (
            db.execute(
                select(Bouquet).where(
                    Bouquet.id == cursor,
                    Bouquet.catalog_type == catalog_type.value,
                )
            )
            .scalars()
            .first()
        )
        if not cursor_row:
            raise HTTPException(status_code=400, detail="Invalid cursor.")

        if normalized_sort == "name_asc":
            cursor_name = (cursor_row.name or "").lower()
            base_query = base_query.where(
                or_(
                    name_sort_expr > cursor_name,
                    and_(name_sort_expr == cursor_name, Bouquet.id > cursor_row.id),
                )
            )
        elif normalized_sort == "name_desc":
            cursor_name = (cursor_row.name or "").lower()
            base_query = base_query.where(
                or_(
                    name_sort_expr < cursor_name,
                    and_(name_sort_expr == cursor_name, Bouquet.id < cursor_row.id),
                )
            )
        elif normalized_sort == "price_asc":
            cursor_price = cursor_row.price_cents or 0
            base_query = base_query.where(
                or_(
                    Bouquet.price_cents > cursor_price,
                    and_(Bouquet.price_cents == cursor_price, Bouquet.id > cursor_row.id),
                )
            )
        elif normalized_sort == "price_desc":
            cursor_price = cursor_row.price_cents or 0
            base_query = base_query.where(
                or_(
                    Bouquet.price_cents < cursor_price,
                    and_(Bouquet.price_cents == cursor_price, Bouquet.id < cursor_row.id),
                )
            )
        else:
            base_query = base_query.where(
                or_(
                    Bouquet.created_at < cursor_row.created_at,
                    and_(
                        Bouquet.created_at == cursor_row.created_at,
                        Bouquet.id < cursor_row.id,
                    ),
                )
            )

    if normalized_sort == "name_asc":
        query = base_query.order_by(name_sort_expr.asc(), Bouquet.id.asc()).limit(take + 1)
    elif normalized_sort == "name_desc":
        query = base_query.order_by(name_sort_expr.desc(), Bouquet.id.desc()).limit(take + 1)
    elif normalized_sort == "price_asc":
        query = base_query.order_by(Bouquet.price_cents.asc(), Bouquet.id.asc()).limit(take + 1)
    elif normalized_sort == "price_desc":
        query = base_query.order_by(Bouquet.price_cents.desc(), Bouquet.id.desc()).limit(take + 1)
    else:
        query = base_query.order_by(Bouquet.created_at.desc(), Bouquet.id.desc()).limit(take + 1)
    results = db.execute(query).scalars().all()

    has_more = len(results) > take
    page = results[:take]
    next_cursor = page[-1].id if has_more and page else None

    settings = get_store_settings(db)
    items = [
        {
            "bouquet": BouquetOut.model_validate(bouquet),
            "pricing": get_bouquet_pricing(bouquet, settings),
        }
        for bouquet in page
    ]
    return CatalogResponse(items=items, next_cursor=next_cursor)
