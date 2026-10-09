from typing import List, Optional
"""
Payment submission (student-facing) — receipt upload, status check.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app import models, schemas
from app.auth import get_current_student
from app.database import get_db
from app.image_utils import compress_image
from app.storage import upload_image
from app.config import SUBSCRIPTION_PRICE_DZD

router = APIRouter(prefix="/api/payments", tags=["payments"])


# ── POST /api/payments/upload ─────────────────────────────────

@router.post("/upload", response_model=schemas.PaymentOut, status_code=201)
async def upload_receipt(
    file: UploadFile = File(...),
    amount: int = Form(2000),
    referral_code: Optional[str] = Form(None),
    student: models.Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    # Only allow if not already active or pending
    if student.subscription_status == "active":
        raise HTTPException(status_code=400, detail="اشتراكك نشط بالفعل")
    if student.subscription_status == "pending":
        raise HTTPException(
            status_code=400,
            detail="طلبك قيد المراجعة — يرجى الانتظار حتى يتم البت فيه"
        )

    # Validate file type
    allowed = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=422,
            detail="نوع الملف غير مدعوم — يُقبل فقط: JPG، PNG، WebP"
        )

    # Read, compress, upload
    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=422, detail="الملف فارغ")

    compressed, mime = compress_image(raw, file.content_type)
    receipt_url = await upload_image(compressed, mime, folder="receipts")

    # If no referral code passed, check if student was referred by an ambassador
    ref_code = referral_code.strip() if referral_code and referral_code.strip() else None
    if not ref_code and student.referred_by:
        ref_stu = await db.execute(select(models.Student).where(models.Student.id == student.referred_by))
        r_owner = ref_stu.scalar_one_or_none()
        if r_owner:
            ref_code = r_owner.referral_code

    # Create payment record
    payment = models.Payment(
        student_id=student.id,
        amount=amount,
        receipt_image_url=receipt_url,
        status="pending",
        referral_code=ref_code,
    )
    db.add(payment)

    # Update student status to pending
    student.subscription_status = "pending"

    await db.commit()
    await db.refresh(payment)
    await db.refresh(student)

    out = schemas.PaymentOut.model_validate(payment)
    out.student_name = student.name
    out.student_phone = student.phone
    return out


# ── GET /api/payments/my ────────────────────────────────────

@router.get("/my", response_model=List[schemas.PaymentOut])
async def my_payments(
    student: models.Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.Payment)
        .where(models.Payment.student_id == student.id)
        .order_by(models.Payment.submitted_at.desc())
    )
    payments = result.scalars().all()
    out = []
    for p in payments:
        row = schemas.PaymentOut.model_validate(p)
        row.student_name = student.name
        row.student_phone = student.phone
        out.append(row)
    return out


# ── POST /api/payments/cash ───────────────────────────────────

@router.post("/cash", response_model=schemas.PaymentOut, status_code=201)
async def submit_cash_payment(
    body: schemas.CashPaymentIn,
    student: models.Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    if student.subscription_status == "active":
        raise HTTPException(status_code=400, detail="اشتراكك نشط بالفعل")
    if student.subscription_status == "pending":
        raise HTTPException(
            status_code=400,
            detail="لديك طلب اشتراك قيد المراجعة بالفعل — يرجى انتظار التحقق أو زيارة المقر"
        )

    ref_code = body.referral_code.strip() if body.referral_code and body.referral_code.strip() else None
    if not ref_code and student.referred_by:
        ref_stu = await db.execute(select(models.Student).where(models.Student.id == student.referred_by))
        r_owner = ref_stu.scalar_one_or_none()
        if r_owner:
            ref_code = r_owner.referral_code

    payment = models.Payment(
        student_id=student.id,
        amount=body.amount or 2000,
        receipt_image_url="CASH",
        status="pending",
        referral_code=ref_code,
    )
    db.add(payment)

    student.subscription_status = "pending"
    await db.commit()
    await db.refresh(payment)
    await db.refresh(student)

    out = schemas.PaymentOut.model_validate(payment)
    out.student_name = student.name
    out.student_phone = student.phone
    return out


# ── GET /api/payments/settings ──────────────────────────────

@router.get("/settings", response_model=schemas.PublicSettingOut)
async def get_payment_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Setting).limit(1))
    s = result.scalar_one_or_none()
    if not s:
        return schemas.PublicSettingOut(
            baridimob_account="0799 12 34 56",
            ccp_account="",
            account_holder="محمد أمين بوكتاشة",
            payment_note="سيتم تفعيل اشتراكك خلال 24 ساعة من التحقق من وصل الدفع",
            subscription_price=2000,
        )
    return schemas.PublicSettingOut.model_validate(s)
