"""
Public verification endpoint — no auth required.
Vendors open this URL (via QR scan) to confirm a student's membership live.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app import models, schemas
from app.database import get_db

router = APIRouter(tags=["verify"])


@router.get("/verify/{student_id}", response_model=schemas.VerifyOut)
async def verify_student(student_id: int, db: AsyncSession = Depends(get_db)):
    """
    Public endpoint — no authentication needed.
    Returns live membership validity so a vendor can verify by scanning the QR.
    """
    result = await db.execute(
        select(models.Student).where(models.Student.id == student_id)
    )
    student = result.scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    now = datetime.utcnow()
    is_valid = (
        student.subscription_status == "active"
        and student.subscription_end is not None
        and student.subscription_end > now
    )

    return schemas.VerifyOut(
        student_id=student.id,
        name=student.name,
        university=student.university,
        photo_url=student.photo_url,
        subscription_status=student.subscription_status,
        subscription_end=student.subscription_end,
        is_valid=is_valid,
        verified_at=now,
    )
