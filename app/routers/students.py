"""
Student-facing routes: register, login, me (get/patch/photo), QR code.
"""
import re

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app import models, schemas
from app.auth import (
    hash_password, verify_password, create_access_token,
    get_current_student
)
from app.database import get_db
from app.image_utils import compress_image
from app.storage import upload_image
from app.qr import generate_verify_qr_png

router = APIRouter(prefix="/api/students", tags=["students"])


def _make_referral_code(name: str, student_id: int) -> str:
    prefix = re.sub(r"[^A-Za-z\u0600-\u06FF]", "", name)[:4].upper()
    return f"AM{prefix}{student_id:04d}"


# ── POST /api/students/register ──────────────────────────────

@router.post("/register", response_model=schemas.Token, status_code=201)
async def register(body: schemas.StudentRegister, db: AsyncSession = Depends(get_db)):
    # Check phone uniqueness
    existing = await db.execute(
        select(models.Student).where(models.Student.phone == body.phone)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="رقم الهاتف مسجل مسبقاً — يرجى تسجيل الدخول"
        )



    # Check for valid referral code if provided
    referred_by_id = None
    if body.referred_by_code:
        clean_code = body.referred_by_code.strip()
        ref_owner = await db.execute(
            select(models.Student).where(func.lower(func.trim(models.Student.referral_code)) == clean_code.lower())
        )
        owner = ref_owner.scalar_one_or_none()
        if not owner:
            ref_match = await db.execute(
                select(models.Referral).where(func.lower(func.trim(models.Referral.code)) == clean_code.lower())
            )
            r_obj = ref_match.scalar_one_or_none()
            if r_obj:
                s_res = await db.execute(select(models.Student).where(models.Student.id == r_obj.student_id))
                owner = s_res.scalar_one_or_none()
        if owner:
            referred_by_id = owner.id

    # Create student (referral_code is a placeholder until we have the real id)
    student = models.Student(
        name=body.name,
        phone=body.phone,
        university=body.university,
        password_hash=hash_password(body.password),
        photo_url=None,
        subscription_status="none",
        referred_by=referred_by_id,
        referral_code="TEMP",   # will update after flush gives us the id
    )
    db.add(student)
    await db.flush()  # Populate student.id without committing

    # Now we can build a proper referral code
    student.referral_code = _make_referral_code(body.name, student.id)

    # Create the student's own referral record
    db.add(models.Referral(
        student_id=student.id,
        code=student.referral_code,
        usage_count=0,
        reward_amount=0,
        reward_status="pending",
    ))

    await db.commit()
    await db.refresh(student)

    token = create_access_token(str(student.id), "student")
    return schemas.Token(
        access_token=token,
        student=schemas.StudentOut.model_validate(student)
    )


# ── POST /api/students/login ─────────────────────────────────

@router.post("/login", response_model=schemas.Token)
async def login(body: schemas.StudentLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Student).where(models.Student.phone == body.phone)
    )
    student = result.scalar_one_or_none()
    if not student or not verify_password(body.password, student.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="رقم الهاتف أو كلمة المرور غير صحيحة"
        )
    token = create_access_token(str(student.id), "student")
    return schemas.Token(
        access_token=token,
        student=schemas.StudentOut.model_validate(student)
    )


# ── POST /api/students/forgot-password ───────────────────────

@router.post("/forgot-password", status_code=200)
async def forgot_password(phone: str, db: AsyncSession = Depends(get_db)):
    """Mocked for demo — logs the request. Admin can manually reset in real use."""
    result = await db.execute(
        select(models.Student).where(models.Student.phone == phone.strip())
    )
    # We deliberately return the same message whether found or not (security best practice)
    _ = result.scalar_one_or_none()
    return {"detail": "إذا كان الرقم مسجلاً، ستتلقى رسالة SMS قريباً"}


# ── GET /api/students/me ─────────────────────────────────────

@router.get("/me", response_model=schemas.StudentOut)
async def get_me(student: models.Student = Depends(get_current_student)):
    return schemas.StudentOut.model_validate(student)


# ── GET /api/students/referral-stats ─────────────────────────

@router.get("/referral-stats", response_model=schemas.ReferralStatsOut)
async def get_referral_stats(
    student: models.Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.Referral).where(models.Referral.student_id == student.id)
    )
    ref = result.scalar_one_or_none()
    if not ref:
        ref = models.Referral(
            student_id=student.id,
            code=student.referral_code,
            usage_count=0,
            reward_amount=0,
            reward_status="pending",
        )
        db.add(ref)
        await db.commit()
        await db.refresh(ref)

    return schemas.ReferralStatsOut(
        referral_code=student.referral_code,
        is_ambassador=student.is_ambassador,
        usage_count=ref.usage_count,
        reward_amount=ref.reward_amount,
        reward_status=ref.reward_status,
    )


# ── PATCH /api/students/me ───────────────────────────────────

@router.patch("/me", response_model=schemas.StudentOut)
async def update_me(
    body: schemas.StudentUpdate,
    student: models.Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    if body.name is not None:
        student.name = body.name
    if body.university is not None:
        student.university = body.university
    await db.commit()
    await db.refresh(student)
    return schemas.StudentOut.model_validate(student)


# ── POST /api/students/me/photo ──────────────────────────────

@router.post("/me/photo", response_model=schemas.StudentOut)
async def upload_photo(
    file: UploadFile = File(...),
    student: models.Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    raw = await file.read()
    compressed, mime = compress_image(raw, file.content_type or "image/jpeg")
    url = await upload_image(compressed, mime, folder="photos")
    student.photo_url = url
    await db.commit()
    await db.refresh(student)
    return schemas.StudentOut.model_validate(student)


# ── GET /api/students/{id}/qr ────────────────────────────────

@router.get("/{student_id}/qr")
async def get_qr(
    student_id: int,
    student: models.Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    # Students can only get their own QR
    if student.id != student_id:
        raise HTTPException(status_code=403, detail="لا يمكنك طلب بطاقة طالب آخر")
    if student.subscription_status != "active":
        raise HTTPException(status_code=403, detail="يجب أن يكون اشتراكك نشطاً للحصول على الرمز")

    png_bytes = generate_verify_qr_png(student_id)
    return Response(content=png_bytes, media_type="image/png")
