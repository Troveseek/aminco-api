from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app import models, schemas
from app.database import get_db
from app.auth import get_current_admin

router = APIRouter(tags=["categories"])

@router.get("/api/categories", response_model=List[schemas.CategoryOut])
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Category).order_by(models.Category.created_at))
    return result.scalars().all()

@router.post("/api/admin/categories", response_model=schemas.CategoryOut, status_code=201)
async def create_category(
    cat_in: schemas.CategoryCreate,
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    # Check if category exists
    res = await db.execute(select(models.Category).where(models.Category.label == cat_in.label))
    if res.scalars().first():
        raise HTTPException(status_code=400, detail="هذا التصنيف موجود بالفعل")

    new_cat = models.Category(**cat_in.model_dump())
    db.add(new_cat)
    await db.commit()
    await db.refresh(new_cat)
    return new_cat

@router.put("/api/admin/categories/{cat_id}", response_model=schemas.CategoryOut)
async def update_category(
    cat_id: int,
    cat_in: schemas.CategoryUpdate,
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(models.Category).where(models.Category.id == cat_id))
    cat = res.scalars().first()
    if not cat:
        raise HTTPException(status_code=404, detail="التصنيف غير موجود")

    # check label collision
    dup_res = await db.execute(select(models.Category).where(models.Category.label == cat_in.label, models.Category.id != cat_id))
    if dup_res.scalars().first():
        raise HTTPException(status_code=400, detail="هذا التصنيف موجود بالفعل")

    cat.label = cat_in.label
    cat.icon = cat_in.icon
    await db.commit()
    await db.refresh(cat)
    return cat

@router.delete("/api/admin/categories/{cat_id}")
async def delete_category(
    cat_id: int,
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(models.Category).where(models.Category.id == cat_id))
    cat = res.scalars().first()
    if not cat:
        raise HTTPException(status_code=404, detail="التصنيف غير موجود")

    await db.delete(cat)
    await db.commit()
    return {"message": "تم حذف التصنيف بنجاح"}
