"""
Offer and favorite routes — public browsing + authenticated favorites.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app import models, schemas
from app.auth import get_current_student_optional, get_current_student
from app.database import get_db

router = APIRouter(tags=["offers"])


# ── GET /api/offers ──────────────────────────────────────────

@router.get("/api/offers", response_model=List[schemas.OfferOut])
async def list_offers(
    category: Optional[str] = Query(None, description="Filter by category"),
    q: Optional[str] = Query(None, description="Search keyword"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    student: Optional[models.Student] = Depends(get_current_student_optional),
):
    stmt = (
        select(models.Offer)
        .options(selectinload(models.Offer.vendor))
        .where(models.Offer.active == True)
    )
    if category:
        stmt = stmt.where(models.Offer.category.contains(category))
    if q:
        kw = f"%{q}%"
        stmt = stmt.where(
            models.Offer.title.ilike(kw) |
            models.Offer.description.ilike(kw)
        )
    stmt = stmt.offset((page - 1) * limit).limit(limit)
    result = await db.execute(stmt)
    offers = result.scalars().all()

    # Resolve favorite IDs for the current student
    fav_ids: set[int] = set()
    if student:
        fav_result = await db.execute(
            select(models.Favorite.offer_id).where(models.Favorite.student_id == student.id)
        )
        fav_ids = {row[0] for row in fav_result.all()}

    out = []
    for o in offers:
        d = schemas.OfferOut.model_validate(o)
        d.vendor_name = o.vendor.name if o.vendor else ""
        d.vendor_address = o.vendor.address if o.vendor else ""
        d.is_favorited = o.id in fav_ids
        out.append(d)
    return out


# ── GET /api/offers/{id} ─────────────────────────────────────

@router.get("/api/offers/{offer_id}", response_model=schemas.OfferOut)
async def get_offer(
    offer_id: int,
    db: AsyncSession = Depends(get_db),
    student: Optional[models.Student] = Depends(get_current_student_optional),
):
    result = await db.execute(
        select(models.Offer)
        .options(selectinload(models.Offer.vendor))
        .where(models.Offer.id == offer_id)
    )
    o = result.scalar_one_or_none()
    if o is None:
        raise HTTPException(status_code=404, detail="العرض غير موجود")

    fav_ids: set[int] = set()
    if student:
        fav_result = await db.execute(
            select(models.Favorite.offer_id).where(models.Favorite.student_id == student.id)
        )
        fav_ids = {row[0] for row in fav_result.all()}

    d = schemas.OfferOut.model_validate(o)
    d.vendor_name = o.vendor.name if o.vendor else ""
    d.vendor_address = o.vendor.address if o.vendor else ""
    d.is_favorited = o.id in fav_ids
    return d


# ── POST /api/favorites/{offer_id} ───────────────────────────

@router.post("/api/favorites/{offer_id}", status_code=201)
async def add_favorite(
    offer_id: int,
    student: models.Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    # Check offer exists
    result = await db.execute(select(models.Offer).where(models.Offer.id == offer_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="العرض غير موجود")
    # Idempotent: skip if already favorited
    existing = await db.execute(
        select(models.Favorite).where(
            models.Favorite.student_id == student.id,
            models.Favorite.offer_id == offer_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        db.add(models.Favorite(student_id=student.id, offer_id=offer_id))
        await db.commit()
    return {"detail": "تمت الإضافة إلى المفضلة"}


# ── DELETE /api/favorites/{offer_id} ─────────────────────────

@router.delete("/api/favorites/{offer_id}", status_code=200)
async def remove_favorite(
    offer_id: int,
    student: models.Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.Favorite).where(
            models.Favorite.student_id == student.id,
            models.Favorite.offer_id == offer_id,
        )
    )
    fav = result.scalar_one_or_none()
    if fav:
        await db.delete(fav)
        await db.commit()
    return {"detail": "تمت الإزالة من المفضلة"}


# ── GET /api/favorites ───────────────────────────────────────

@router.get("/api/favorites", response_model=List[schemas.OfferOut])
async def list_favorites(
    student: models.Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.Offer)
        .options(selectinload(models.Offer.vendor))
        .join(models.Favorite, models.Favorite.offer_id == models.Offer.id)
        .where(models.Favorite.student_id == student.id)
    )
    offers = result.scalars().all()
    out = []
    for o in offers:
        d = schemas.OfferOut.model_validate(o)
        d.vendor_name = o.vendor.name if o.vendor else ""
        d.vendor_address = o.vendor.address if o.vendor else ""
        d.is_favorited = True
        out.append(d)
    return out
