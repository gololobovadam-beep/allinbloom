from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_optional_user, require_admin
from app.models.enums import Role
from app.models.promo_slide import PromoSlide
from app.schemas.promo_slide import PromoSlideCreate, PromoSlideOut, PromoSlideUpdate

router = APIRouter(prefix="/api/promotions", tags=["promotions"])


@router.get("", response_model=list[PromoSlideOut])
def list_promotions(
    include_inactive: bool = Query(default=False),
    user=Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    if include_inactive and (not user or user.role != Role.ADMIN):
        raise HTTPException(status_code=403, detail="Unauthorized")
    query = select(PromoSlide)
    if not include_inactive:
        query = query.where(PromoSlide.is_active.is_(True))
    query = query.order_by(PromoSlide.position.asc(), PromoSlide.updated_at.desc())
    return db.execute(query).scalars().all()


@router.get("/{slide_id}", response_model=PromoSlideOut)
def get_promo(
    slide_id: str,
    user=Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    slide = db.get(PromoSlide, slide_id)
    if not slide or (not slide.is_active and (not user or user.role != Role.ADMIN)):
        raise HTTPException(status_code=404, detail="Not found")
    return slide


@router.post("", response_model=PromoSlideOut)
def create_promo(
    payload: PromoSlideCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    slide = PromoSlide(**payload.model_dump())
    db.add(slide)
    db.commit()
    db.refresh(slide)
    return slide


@router.patch("/{slide_id}", response_model=PromoSlideOut)
def update_promo(
    slide_id: str,
    payload: PromoSlideUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    slide = db.get(PromoSlide, slide_id)
    if not slide:
        raise HTTPException(status_code=404, detail="Not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(slide, key, value)
    db.commit()
    db.refresh(slide)
    return slide


@router.delete("/{slide_id}")
def delete_promo(
    slide_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    slide = db.get(PromoSlide, slide_id)
    if not slide:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(slide)
    db.commit()
    return {"ok": True}
